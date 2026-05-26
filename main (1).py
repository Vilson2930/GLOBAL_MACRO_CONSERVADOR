"""
main.py — Robô Macro de Alocação v1

Objetivo:
- NÃO executa ordens.
- Busca parte dos dados no FRED.
- Calcula regime atual e regime projetado usando liquidez com defasagem de 100 dias.
- Define pesos-alvo por regime.
- Compara com a carteira atual.
- Emite sugestão de rebalanceamento.

Arquitetura fixa:
- Liquidez: 40%
- Crescimento: 35%
- Crédito/Risco: 25%

Lógica de liquidez:
- Liquidez de T-100 dias ajuda a determinar o regime de hoje.
- Liquidez de hoje ajuda a projetar o regime dos próximos ~100 dias.

Requisitos:
    pip install pandas numpy requests python-dotenv yfinance

Arquivo .env:
    FRED_API_KEY=sua_chave_fred_aqui

Opcional: portfolio.csv
    Ativo,Classe,Quantidade
    BTC,Cripto,0.692
    VT,ETF,4.286
    VOO,ETF,25.09
    SHY,Renda_Fixa,142.73
    USDT,Caixa,23404.88758
    DEFI,Cripto,1320
    OURO,Commodities,12
"""

from __future__ import annotations

import os
import math
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

try:
    import yfinance as yf
except ImportError:
    yf = None

warnings.filterwarnings("ignore")

load_dotenv()
FRED_API_KEY = os.getenv("FRED_API_KEY")
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

LAG_LIQUIDEZ_DIAS = 100
BANDA_TATICA = 0.05
BANDA_OBRIGATORIA = 0.10

PESO_LIQUIDEZ = 0.40
PESO_CRESCIMENTO = 0.35
PESO_CREDITO = 0.25

FRED_SERIES = {
    "real_yield_10y": "DFII10",
    "hy_spread": "BAMLH0A0HYM2",
    "nfci": "NFCI",
    "yield_curve_10y_3m": "T10Y3M",
    "dxy_proxy": "DTWEXBGS",
    "vix": "VIXCLS",
    "fed_assets": "WALCL",
}

YFINANCE_TICKERS = {
    "BTC": "BTC-USD",
    "VT": "VT",
    "VOO": "VOO",
    "SHY": "SHY",
    "USDT": "USDT-USD",
    "DEFI": "DEFI-USD",
    "OURO": "GC=F",
}

DEFAULT_PORTFOLIO = pd.DataFrame([
    {"Ativo": "BTC", "Classe": "Cripto", "Quantidade": 0.692},
    {"Ativo": "VT", "Classe": "ETF", "Quantidade": 4.286},
    {"Ativo": "VOO", "Classe": "ETF", "Quantidade": 25.09},
    {"Ativo": "SHY", "Classe": "Renda_Fixa", "Quantidade": 142.73},
    {"Ativo": "USDT", "Classe": "Caixa", "Quantidade": 23404.88758},
    {"Ativo": "DEFI", "Classe": "Cripto", "Quantidade": 1320.0},
    {"Ativo": "OURO", "Classe": "Commodities", "Quantidade": 12.0},
])

TARGET_WEIGHTS_BY_REGIME = {
    "BULL": {
        "VOO": 0.35, "VT": 0.15, "BTC": 0.22, "DEFI": 0.08,
        "SHY": 0.10, "USDT": 0.05, "OURO": 0.05,
    },
    "EXPANSAO": {
        "VOO": 0.32, "VT": 0.13, "BTC": 0.15, "DEFI": 0.05,
        "SHY": 0.20, "USDT": 0.10, "OURO": 0.05,
    },
    "NEUTRO": {
        "VOO": 0.25, "VT": 0.10, "BTC": 0.09, "DEFI": 0.03,
        "SHY": 0.30, "USDT": 0.15, "OURO": 0.08,
    },
    "DESACELERACAO": {
        "VOO": 0.15, "VT": 0.05, "BTC": 0.04, "DEFI": 0.01,
        "SHY": 0.45, "USDT": 0.20, "OURO": 0.10,
    },
    "STRESS": {
        "VOO": 0.04, "VT": 0.01, "BTC": 0.02, "DEFI": 0.00,
        "SHY": 0.55, "USDT": 0.30, "OURO": 0.08,
    },
}


@dataclass
class BlockScores:
    liquidez_t_menos_100: float
    liquidez_hoje: float
    crescimento: float
    credito: float


@dataclass
class RegimeResult:
    score_atual: float
    score_futuro: float
    delta: float
    regime_atual: str
    regime_futuro: str
    regime_operacional: str
    block_scores: BlockScores


def fetch_fred_series(series_id: str, start_date: str = "2010-01-01") -> pd.Series:
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY não encontrada. Crie um .env com FRED_API_KEY=sua_chave.")

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
    }

    response = requests.get(FRED_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json().get("observations", [])

    df = pd.DataFrame(data)
    if df.empty:
        raise ValueError(f"Série FRED vazia: {series_id}")

    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"].replace(".", np.nan), errors="coerce")
    df = df.dropna(subset=["value"])

    return df.set_index("date")["value"].sort_index()


def fetch_all_fred() -> Dict[str, pd.Series]:
    output = {}
    for name, sid in FRED_SERIES.items():
        print(f"Buscando FRED: {name} ({sid})")
        output[name] = fetch_fred_series(sid)
    return output


def get_latest_value(series: pd.Series, date: Optional[pd.Timestamp] = None) -> float:
    if date is None:
        date = pd.Timestamp.today()
    valid = series.loc[series.index <= date]
    if valid.empty:
        raise ValueError("Não há dado disponível para a data solicitada.")
    return float(valid.iloc[-1])


def slope_score(series: pd.Series, lookback: int = 90, higher_is_better: bool = True) -> float:
    s = series.dropna()
    if len(s) < lookback + 5:
        return 0.0

    recent = float(s.iloc[-1])
    past = float(s.iloc[-lookback])

    raw = recent - past if past == 0 else (recent - past) / abs(past)
    if not higher_is_better:
        raw *= -1

    return float(np.clip(raw * 10, -1, 1))


def level_score(
    value: float,
    positive_threshold: float,
    negative_threshold: float,
    lower_is_better: bool = False,
) -> float:
    if lower_is_better:
        if value <= positive_threshold:
            return 1.0
        if value >= negative_threshold:
            return -1.0
        return 0.0

    if value >= positive_threshold:
        return 1.0
    if value <= negative_threshold:
        return -1.0
    return 0.0


def calculate_liquidity_score(fred: Dict[str, pd.Series], as_of: Optional[pd.Timestamp] = None) -> float:
    """
    Bloco Liquidez:
    - Proxy de liquidez: Fed Assets (WALCL).
    - Taxa real 10Y: DFII10.

    Versão institucional futura:
    substituir WALCL por liquidez global composta:
    Fed + ECB + BoJ + PBoC convertidos para USD.
    """
    if as_of is None:
        as_of = pd.Timestamp.today()

    fed_assets = fred["fed_assets"].loc[fred["fed_assets"].index <= as_of]
    real_yield = fred["real_yield_10y"].loc[fred["real_yield_10y"].index <= as_of]

    if len(fed_assets) < 120 or len(real_yield) < 120:
        return 0.0

    liq_trend = slope_score(fed_assets, lookback=100, higher_is_better=True)
    real_yield_trend = slope_score(real_yield, lookback=60, higher_is_better=False)
    real_yield_level = level_score(
        get_latest_value(real_yield),
        positive_threshold=0.50,
        negative_threshold=2.00,
        lower_is_better=True,
    )

    score = 0.65 * liq_trend + 0.20 * real_yield_trend + 0.15 * real_yield_level
    return float(np.clip(score, -1, 1))


def calculate_growth_score_manual(
    global_pmi: Optional[float] = None,
    oecd_cli: Optional[float] = None,
    oecd_cli_slope: Optional[float] = None,
) -> float:
    """
    v1 usa entrada manual para PMI e OECD CLI.
    Se não informado, crescimento fica neutro para não contaminar o modelo.
    """
    scores = []

    if global_pmi is not None:
        if global_pmi >= 52:
            scores.append(1.0)
        elif global_pmi <= 49:
            scores.append(-1.0)
        else:
            scores.append(0.0)

    if oecd_cli is not None:
        if oecd_cli >= 100.5:
            scores.append(1.0)
        elif oecd_cli <= 99.5:
            scores.append(-1.0)
        else:
            scores.append(0.0)

    if oecd_cli_slope is not None:
        if oecd_cli_slope > 0:
            scores.append(0.5)
        elif oecd_cli_slope < 0:
            scores.append(-0.5)
        else:
            scores.append(0.0)

    if not scores:
        return 0.0

    return float(np.clip(np.mean(scores), -1, 1))


def calculate_credit_score(fred: Dict[str, pd.Series]) -> float:
    hy = fred["hy_spread"]
    nfci = fred["nfci"]

    hy_level = level_score(get_latest_value(hy), positive_threshold=3.50, negative_threshold=5.50, lower_is_better=True)
    hy_trend = slope_score(hy, lookback=60, higher_is_better=False)

    nfci_level = level_score(get_latest_value(nfci), positive_threshold=-0.25, negative_threshold=0.25, lower_is_better=True)
    nfci_trend = slope_score(nfci, lookback=60, higher_is_better=False)

    score = 0.40 * hy_level + 0.25 * hy_trend + 0.25 * nfci_level + 0.10 * nfci_trend
    return float(np.clip(score, -1, 1))


def calculate_filters(fred: Dict[str, pd.Series]) -> Dict[str, float]:
    curve = get_latest_value(fred["yield_curve_10y_3m"])
    vix = get_latest_value(fred["vix"])
    dxy_trend = slope_score(fred["dxy_proxy"], lookback=60, higher_is_better=False)

    return {
        "curva_10y_3m": level_score(curve, positive_threshold=0.50, negative_threshold=-0.50),
        "vix": level_score(vix, positive_threshold=18.0, negative_threshold=28.0, lower_is_better=True),
        "dolar": dxy_trend,
    }


def classify_regime(score: float) -> str:
    if score > 0.60:
        return "BULL"
    if score > 0.25:
        return "EXPANSAO"
    if score >= -0.25:
        return "NEUTRO"
    if score >= -0.60:
        return "DESACELERACAO"
    return "STRESS"


def choose_operational_regime(regime_atual: str, delta: float) -> str:
    """
    O regime atual define a base.
    O delta da liquidez futura ajusta a agressividade.
    """
    order = ["STRESS", "DESACELERACAO", "NEUTRO", "EXPANSAO", "BULL"]
    idx = order.index(regime_atual)

    if delta <= -0.30:
        idx = max(0, idx - 1)
    elif delta >= 0.30:
        idx = min(len(order) - 1, idx + 1)

    return order[idx]


def calculate_regime(
    fred: Dict[str, pd.Series],
    global_pmi: Optional[float] = None,
    oecd_cli: Optional[float] = None,
    oecd_cli_slope: Optional[float] = None,
) -> RegimeResult:
    today_ts = pd.Timestamp.today()
    lag_ts = today_ts - pd.Timedelta(days=LAG_LIQUIDEZ_DIAS)

    liquidez_t_menos_100 = calculate_liquidity_score(fred, as_of=lag_ts)
    liquidez_hoje = calculate_liquidity_score(fred, as_of=today_ts)
    crescimento = calculate_growth_score_manual(global_pmi, oecd_cli, oecd_cli_slope)
    credito = calculate_credit_score(fred)

    score_atual = (
        PESO_LIQUIDEZ * liquidez_t_menos_100
        + PESO_CRESCIMENTO * crescimento
        + PESO_CREDITO * credito
    )

    score_futuro = (
        PESO_LIQUIDEZ * liquidez_hoje
        + PESO_CRESCIMENTO * crescimento
        + PESO_CREDITO * credito
    )

    score_atual = float(np.clip(score_atual, -1, 1))
    score_futuro = float(np.clip(score_futuro, -1, 1))
    delta = score_futuro - score_atual

    regime_atual = classify_regime(score_atual)
    regime_futuro = classify_regime(score_futuro)
    regime_operacional = choose_operational_regime(regime_atual, delta)

    return RegimeResult(
        score_atual=score_atual,
        score_futuro=score_futuro,
        delta=delta,
        regime_atual=regime_atual,
        regime_futuro=regime_futuro,
        regime_operacional=regime_operacional,
        block_scores=BlockScores(
            liquidez_t_menos_100=liquidez_t_menos_100,
            liquidez_hoje=liquidez_hoje,
            crescimento=crescimento,
            credito=credito,
        ),
    )


def load_portfolio(path: str = "portfolio.csv") -> pd.DataFrame:
    if os.path.exists(path):
        df = pd.read_csv(path)
    else:
        df = DEFAULT_PORTFOLIO.copy()

    required = {"Ativo", "Classe", "Quantidade"}
    if not required.issubset(df.columns):
        raise ValueError("portfolio.csv precisa ter colunas: Ativo, Classe, Quantidade")

    df["Ativo"] = df["Ativo"].astype(str).str.upper().str.strip()
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce")
    return df.dropna(subset=["Quantidade"])


def get_prices_yfinance(assets: List[str]) -> Dict[str, float]:
    prices = {}

    if yf is None:
        print("AVISO: yfinance não instalado. Usando preços vazios.")
        return {asset: np.nan for asset in assets}

    for asset in assets:
        if asset == "USDT":
            prices[asset] = 1.0
            continue

        ticker = YFINANCE_TICKERS.get(asset)
        if not ticker:
            prices[asset] = np.nan
            continue

        try:
            data = yf.download(ticker, period="10d", progress=False, auto_adjust=True)
            if data.empty:
                prices[asset] = np.nan
            else:
                prices[asset] = float(data["Close"].dropna().iloc[-1])
        except Exception:
            prices[asset] = np.nan

    return prices


def calculate_portfolio_values(portfolio: pd.DataFrame, prices: Dict[str, float]) -> pd.DataFrame:
    df = portfolio.copy()
    df["Preco"] = df["Ativo"].map(prices)

    missing = df[df["Preco"].isna()]["Ativo"].tolist()
    if missing:
        print(f"AVISO: preço não encontrado para {missing}. Valor tratado como 0 até ajuste manual.")
        df["Preco"] = df["Preco"].fillna(0.0)

    df["Valor_USD"] = df["Quantidade"] * df["Preco"]
    total = df["Valor_USD"].sum()

    if total <= 0:
        raise ValueError("Valor total da carteira é zero. Verifique preços e quantidades.")

    df["Peso_Atual"] = df["Valor_USD"] / total
    return df


def rebalance_suggestions(portfolio_values: pd.DataFrame, target_weights: Dict[str, float]) -> pd.DataFrame:
    df = portfolio_values.copy()
    total = df["Valor_USD"].sum()

    df["Peso_Alvo"] = df["Ativo"].map(target_weights).fillna(0.0)
    df["Valor_Alvo_USD"] = df["Peso_Alvo"] * total
    df["Diferenca_USD"] = df["Valor_Alvo_USD"] - df["Valor_USD"]
    df["Diferenca_Peso"] = df["Peso_Alvo"] - df["Peso_Atual"]

    def action(row):
        diff = abs(row["Diferenca_Peso"])
        if diff < BANDA_TATICA:
            return "MANTER"
        if diff < BANDA_OBRIGATORIA:
            return "AJUSTE_TATICO"
        return "REBALANCEAR_OBRIGATORIO"

    df["Acao"] = df.apply(action, axis=1)
    df["Comprar_Vender"] = np.where(df["Diferenca_USD"] > 0, "COMPRAR", "VENDER")
    df.loc[df["Acao"] == "MANTER", "Comprar_Vender"] = "MANTER"

    return df[[
        "Ativo", "Classe", "Quantidade", "Preco", "Valor_USD",
        "Peso_Atual", "Peso_Alvo", "Diferenca_Peso",
        "Diferenca_USD", "Comprar_Vender", "Acao"
    ]].sort_values("Diferenca_USD", ascending=False)


def print_report(regime: RegimeResult, filters: Dict[str, float], rebalance: pd.DataFrame) -> None:
    print("\n" + "=" * 90)
    print("ROBÔ MACRO DE ALOCAÇÃO — RELATÓRIO")
    print("=" * 90)
    print(f"Data UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n1) REGIME")
    print(f"Score Atual:        {regime.score_atual:.3f} | Regime Atual:        {regime.regime_atual}")
    print(f"Score Futuro:       {regime.score_futuro:.3f} | Regime Futuro:       {regime.regime_futuro}")
    print(f"Delta Futuro-Atual: {regime.delta:.3f}")
    print(f"Regime Operacional: {regime.regime_operacional}")

    print("\n2) BLOCOS")
    print(f"Liquidez T-100, usada para hoje: {regime.block_scores.liquidez_t_menos_100:.3f}")
    print(f"Liquidez hoje, usada para T+100: {regime.block_scores.liquidez_hoje:.3f}")
    print(f"Crescimento hoje:                 {regime.block_scores.crescimento:.3f}")
    print(f"Crédito/Risco hoje:               {regime.block_scores.credito:.3f}")

    print("\n3) FILTROS")
    for name, value in filters.items():
        print(f"{name}: {value:.3f}")

    print("\n4) REBALANCEAMENTO SUGERIDO")
    show = rebalance.copy()
    for col in ["Preco", "Valor_USD", "Diferenca_USD"]:
        show[col] = show[col].map(lambda x: f"{x:,.2f}")
    for col in ["Peso_Atual", "Peso_Alvo", "Diferenca_Peso"]:
        show[col] = show[col].map(lambda x: f"{x:.2%}")
    print(show.to_string(index=False))

    print("\n5) NOTA OPERACIONAL")
    print("- O robô NÃO executa ordens.")
    print("- Liquidez T-100 determina o regime atual; liquidez hoje projeta ~100 dias.")
    print("- Crescimento está manual na v1: informe PMI/CLI se quiser ativar o bloco.")
    print("- Fed WALCL é proxy parcial; versão institucional deve usar liquidez global composta.")
    print("=" * 90)


def main() -> None:
    # Entradas manuais opcionais para o bloco de crescimento.
    # Use None para deixar neutro.
    GLOBAL_PMI = None
    OECD_CLI = None
    OECD_CLI_SLOPE = None

    fred = fetch_all_fred()

    regime = calculate_regime(
        fred=fred,
        global_pmi=GLOBAL_PMI,
        oecd_cli=OECD_CLI,
        oecd_cli_slope=OECD_CLI_SLOPE,
    )

    filters = calculate_filters(fred)

    portfolio = load_portfolio("portfolio.csv")
    prices = get_prices_yfinance(portfolio["Ativo"].tolist())
    portfolio_values = calculate_portfolio_values(portfolio, prices)

    target_weights = TARGET_WEIGHTS_BY_REGIME[regime.regime_operacional]
    rebalance = rebalance_suggestions(portfolio_values, target_weights)

    rebalance.to_csv("rebalance_output.csv", index=False)
    print_report(regime, filters, rebalance)
    print("\nArquivo gerado: rebalance_output.csv")


if __name__ == "__main__":
    main()
