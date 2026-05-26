
"""
main.py — GLOBAL_ATIVOS_LOBAO
Robô Macro de Alocação — Main monolítico v2 dinâmico

LÓGICA CORRETA:
- NÃO usa tabela fixa de pesos por regime.
- Os 8 indicadores determinam dinamicamente o orçamento de risco.
- A carteira real informa apenas o peso atual.
- O robô NÃO executa ordens; apenas calcula compra/venda sugerida.

Arquitetura conceitual:
1) Coleta dados macro e preços.
2) Calcula 8 indicadores ponderados.
3) Calcula Macro Score 0–100.
4) Converte Macro Score em orçamento de risco.
5) Distribui orçamento entre ativos da carteira real.
6) Compara peso atual vs peso recomendado.
7) Gera relatório e rebalance_output.csv.

Indicadores:
1. Liquidez T-100         20%
2. Liquidez Hoje          15%
3. Taxa Real 10Y           5%
4. Global PMI             20%
5. OECD CLI               15%
6. HY Spread              15%
7. NFCI                   10%
8. Filtro composto         freio, não soma no score

Blocos:
- Liquidez total: 40%
- Crescimento: 35%
- Crédito/Risco: 25%
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    yf = None


# ============================================================
# CONFIGURAÇÕES
# ============================================================

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

LAG_LIQUIDEZ_DIAS = 100

BANDA_TATICA = 0.05
BANDA_OBRIGATORIA = 0.10

# Pesos dos 7 indicadores pontuáveis.
# O filtro composto não soma; ele limita o orçamento de risco.
INDICATOR_WEIGHTS = {
    "liquidez_t_100": 0.20,
    "liquidez_hoje": 0.15,
    "real_yield_10y": 0.05,
    "global_pmi": 0.20,
    "oecd_cli": 0.15,
    "hy_spread": 0.15,
    "nfci": 0.10,
}

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
    "BTC-USD": "BTC-USD",
    "USDT": "USDT-USD",
    "GLD": "GLD",
    "VOO": "VOO",
    "TLT": "TLT",
    "BOTZ": "BOTZ",
    "INDA": "INDA",
    "ACWI": "ACWI",
}

DEFAULT_PORTFOLIO = pd.DataFrame([
    {"Ativo": "BTC-USD", "Classe": "Cripto", "Quantidade": 0.6020509176},
    {"Ativo": "USDT", "Classe": "Caixa", "Quantidade": 24000.0},
    {"Ativo": "GLD", "Classe": "Commodities", "Quantidade": 13.0},
    {"Ativo": "VOO", "Classe": "ETF", "Quantidade": 23.0},
    {"Ativo": "TLT", "Classe": "Renda_Fixa", "Quantidade": 130.0},
    {"Ativo": "BOTZ", "Classe": "Acoes", "Quantidade": 10.0},
    {"Ativo": "INDA", "Classe": "ETF", "Quantidade": 10.0},
])

# Grupos de ativos para alocação dinâmica.
RISK_ASSETS = ["BTC-USD", "VOO", "BOTZ", "INDA"]
DEFENSIVE_ASSETS = ["TLT", "USDT", "GLD"]

# Peso relativo dentro do bloco de risco.
# Estes pesos não são alvos fixos finais; são a distribuição interna do orçamento de risco.
RISK_INTERNAL_WEIGHTS = {
    "VOO": 0.45,
    "BTC-USD": 0.35,
    "INDA": 0.12,
    "BOTZ": 0.08,
}

# Peso relativo dentro do bloco defensivo.
DEFENSIVE_INTERNAL_WEIGHTS = {
    "TLT": 0.50,
    "USDT": 0.30,
    "GLD": 0.20,
}

# Limites de governança para evitar concentração extrema.
ASSET_LIMITS = {
    "BTC-USD": {"min": 0.02, "max": 0.35},
    "VOO": {"min": 0.04, "max": 0.45},
    "BOTZ": {"min": 0.00, "max": 0.10},
    "INDA": {"min": 0.00, "max": 0.12},
    "TLT": {"min": 0.05, "max": 0.55},
    "USDT": {"min": 0.05, "max": 0.35},
    "GLD": {"min": 0.05, "max": 0.20},
}


# ============================================================
# CHAVE FRED
# ============================================================

def get_fred_api_key() -> str:
    key = os.getenv("FRED_API_KEY")

    if not key:
        try:
            from google.colab import userdata
            key = userdata.get("FRED_API_KEY")
        except Exception:
            key = None

    if not key:
        key = input("Digite sua FRED_API_KEY: ").strip()

    if not key:
        raise RuntimeError("FRED_API_KEY não fornecida.")

    return key


FRED_API_KEY = get_fred_api_key()


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class IndicatorScores:
    liquidez_t_100: float
    liquidez_hoje: float
    real_yield_10y: float
    global_pmi: float
    oecd_cli: float
    hy_spread: float
    nfci: float
    filtro_composto: float


@dataclass
class MacroResult:
    macro_score: float
    raw_score: float
    risk_budget: float
    defensive_budget: float
    regime: str
    indicators: IndicatorScores


# ============================================================
# DADOS
# ============================================================

def fetch_fred_series(series_id: str, start_date: str = "2010-01-01") -> pd.Series:
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
    }

    try:
        response = requests.get(FRED_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if "observations" not in data:
            raise ValueError(f"Resposta inválida do FRED: {data}")

        df = pd.DataFrame(data["observations"])
        if df.empty:
            raise ValueError(f"Série vazia: {series_id}")

        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])

        if df.empty:
            raise ValueError(f"Série sem valores numéricos válidos: {series_id}")

        return df.set_index("date")["value"].sort_index()

    except Exception as e:
        raise RuntimeError(f"Erro ao buscar série FRED {series_id}: {e}")


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


def get_price_series_yfinance(ticker: str, period: str = "260d") -> pd.Series:
    if yf is None:
        return pd.Series(dtype=float)

    try:
        data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if data.empty:
            return pd.Series(dtype=float)
        return data["Close"].dropna()
    except Exception:
        return pd.Series(dtype=float)


def get_prices_yfinance(assets: List[str]) -> Dict[str, float]:
    prices = {}

    if yf is None:
        print("AVISO: yfinance não instalado.")
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


# ============================================================
# SCORES
# ============================================================

def clamp(x: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(np.clip(x, low, high))


def slope_score(series: pd.Series, lookback: int = 90, higher_is_better: bool = True) -> float:
    s = series.dropna()
    if len(s) < lookback + 5:
        return 0.0

    recent = float(s.iloc[-1])
    past = float(s.iloc[-lookback])

    raw = recent - past if past == 0 else (recent - past) / abs(past)

    if not higher_is_better:
        raw *= -1

    return clamp(raw * 10)


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


def liquidity_trend_score(fred: Dict[str, pd.Series], as_of: pd.Timestamp) -> float:
    fed_assets = fred["fed_assets"].loc[fred["fed_assets"].index <= as_of]

    if len(fed_assets) < 120:
        return 0.0

    # Proxy atual: WALCL. Em versão institucional substituir por liquidez global composta.
    return slope_score(fed_assets, lookback=100, higher_is_better=True)


def real_yield_score(fred: Dict[str, pd.Series]) -> float:
    real_yield = fred["real_yield_10y"]

    trend = slope_score(real_yield, lookback=60, higher_is_better=False)
    level = level_score(
        get_latest_value(real_yield),
        positive_threshold=0.50,
        negative_threshold=2.00,
        lower_is_better=True,
    )

    return clamp(0.60 * trend + 0.40 * level)


def global_pmi_score(global_pmi: Optional[float]) -> float:
    if global_pmi is None:
        return 0.0
    if global_pmi >= 52:
        return 1.0
    if global_pmi <= 49:
        return -1.0
    return 0.0


def oecd_cli_score(oecd_cli: Optional[float], oecd_cli_slope: Optional[float]) -> float:
    scores = []

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

    return clamp(float(np.mean(scores)))


def hy_spread_score(fred: Dict[str, pd.Series]) -> float:
    hy = fred["hy_spread"]

    level = level_score(
        get_latest_value(hy),
        positive_threshold=3.50,
        negative_threshold=5.50,
        lower_is_better=True,
    )

    trend = slope_score(hy, lookback=60, higher_is_better=False)

    return clamp(0.60 * level + 0.40 * trend)


def nfci_score(fred: Dict[str, pd.Series]) -> float:
    nfci = fred["nfci"]

    level = level_score(
        get_latest_value(nfci),
        positive_threshold=-0.25,
        negative_threshold=0.25,
        lower_is_better=True,
    )

    trend = slope_score(nfci, lookback=60, higher_is_better=False)

    return clamp(0.70 * level + 0.30 * trend)


def calculate_filter_composite(fred: Dict[str, pd.Series]) -> float:
    """
    Filtro composto não entra no score bruto.
    Ele limita o orçamento de risco:
    +1 = filtro favorável
     0 = neutro
    -1 = freio defensivo
    """
    curve = get_latest_value(fred["yield_curve_10y_3m"])
    vix = get_latest_value(fred["vix"])

    curve_s = level_score(
        curve,
        positive_threshold=0.50,
        negative_threshold=-0.50,
        lower_is_better=False,
    )

    vix_s = level_score(
        vix,
        positive_threshold=18.0,
        negative_threshold=28.0,
        lower_is_better=True,
    )

    dxy_s = slope_score(
        fred["dxy_proxy"],
        lookback=60,
        higher_is_better=False,
    )

    # ACWI vs MM200
    acwi_close = get_price_series_yfinance("ACWI", period="300d")
    if len(acwi_close) >= 210:
        acwi_s = 1.0 if float(acwi_close.iloc[-1]) > float(acwi_close.rolling(200).mean().iloc[-1]) else -1.0
    else:
        acwi_s = 0.0

    return clamp(float(np.mean([curve_s, vix_s, dxy_s, acwi_s])))


def calculate_macro_result(
    fred: Dict[str, pd.Series],
    global_pmi: Optional[float] = None,
    oecd_cli: Optional[float] = None,
    oecd_cli_slope: Optional[float] = None,
) -> MacroResult:
    today = pd.Timestamp.today()
    lag_date = today - pd.Timedelta(days=LAG_LIQUIDEZ_DIAS)

    indicators = IndicatorScores(
        liquidez_t_100=liquidity_trend_score(fred, lag_date),
        liquidez_hoje=liquidity_trend_score(fred, today),
        real_yield_10y=real_yield_score(fred),
        global_pmi=global_pmi_score(global_pmi),
        oecd_cli=oecd_cli_score(oecd_cli, oecd_cli_slope),
        hy_spread=hy_spread_score(fred),
        nfci=nfci_score(fred),
        filtro_composto=calculate_filter_composite(fred),
    )

    raw_score = (
        INDICATOR_WEIGHTS["liquidez_t_100"] * indicators.liquidez_t_100
        + INDICATOR_WEIGHTS["liquidez_hoje"] * indicators.liquidez_hoje
        + INDICATOR_WEIGHTS["real_yield_10y"] * indicators.real_yield_10y
        + INDICATOR_WEIGHTS["global_pmi"] * indicators.global_pmi
        + INDICATOR_WEIGHTS["oecd_cli"] * indicators.oecd_cli
        + INDICATOR_WEIGHTS["hy_spread"] * indicators.hy_spread
        + INDICATOR_WEIGHTS["nfci"] * indicators.nfci
    )

    raw_score = clamp(raw_score)

    # Converte -1..+1 para 0..100
    macro_score = (raw_score + 1.0) * 50.0

    # Macro Score vira orçamento de risco antes dos filtros.
    base_risk_budget = macro_score / 100.0

    # Limites institucionais de risco: nunca 0%, nunca 100%.
    base_risk_budget = float(np.clip(base_risk_budget, 0.15, 0.85))

    # Filtro composto funciona como freio/validador.
    filtro = indicators.filtro_composto

    if filtro <= -0.50:
        base_risk_budget -= 0.20
    elif filtro < 0:
        base_risk_budget -= 0.10
    elif filtro >= 0.50:
        base_risk_budget += 0.05

    risk_budget = float(np.clip(base_risk_budget, 0.10, 0.85))
    defensive_budget = 1.0 - risk_budget

    regime = classify_by_risk_budget(risk_budget)

    return MacroResult(
        macro_score=float(macro_score),
        raw_score=float(raw_score),
        risk_budget=risk_budget,
        defensive_budget=defensive_budget,
        regime=regime,
        indicators=indicators,
    )


def classify_by_risk_budget(risk_budget: float) -> str:
    if risk_budget >= 0.75:
        return "BULL"
    if risk_budget >= 0.60:
        return "EXPANSAO"
    if risk_budget >= 0.40:
        return "NEUTRO"
    if risk_budget >= 0.25:
        return "DESACELERACAO"
    return "STRESS"


# ============================================================
# ALOCAÇÃO DINÂMICA
# ============================================================

def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(v, 0.0) for v in weights.values())
    if total <= 0:
        raise ValueError("Soma de pesos inválida.")
    return {k: max(v, 0.0) / total for k, v in weights.items()}


def apply_asset_limits(weights: Dict[str, float]) -> Dict[str, float]:
    adjusted = weights.copy()

    for asset, lim in ASSET_LIMITS.items():
        if asset in adjusted:
            adjusted[asset] = float(np.clip(adjusted[asset], lim["min"], lim["max"]))

    return normalize_weights(adjusted)


def calculate_dynamic_recommended_weights(macro: MacroResult) -> Dict[str, float]:
    """
    Esta é a função central:
    os indicadores determinam risk_budget e defensive_budget.
    Depois o orçamento é distribuído entre os ativos existentes.
    """
    risk_budget = macro.risk_budget
    defensive_budget = macro.defensive_budget

    weights = {}

    for asset, internal_weight in RISK_INTERNAL_WEIGHTS.items():
        weights[asset] = risk_budget * internal_weight

    for asset, internal_weight in DEFENSIVE_INTERNAL_WEIGHTS.items():
        weights[asset] = defensive_budget * internal_weight

    weights = apply_asset_limits(weights)
    return weights


# ============================================================
# CARTEIRA E REBALANCEAMENTO
# ============================================================

def calculate_portfolio_values(portfolio: pd.DataFrame, prices: Dict[str, float]) -> pd.DataFrame:
    df = portfolio.copy()
    df["Preco"] = df["Ativo"].map(prices)

    missing = df[df["Preco"].isna()]["Ativo"].tolist()
    if missing:
        print(f"AVISO: preço não encontrado para {missing}. Valor tratado como 0.")
        df["Preco"] = df["Preco"].fillna(0.0)

    df["Valor_USD"] = df["Quantidade"] * df["Preco"]
    total = df["Valor_USD"].sum()

    if total <= 0:
        raise ValueError("Valor total da carteira é zero.")

    df["Peso_Atual"] = df["Valor_USD"] / total
    return df


def rebalance_suggestions(
    portfolio_values: pd.DataFrame,
    recommended_weights: Dict[str, float],
) -> pd.DataFrame:
    df = portfolio_values.copy()
    total = df["Valor_USD"].sum()

    df["Peso_Recomendado"] = df["Ativo"].map(recommended_weights).fillna(0.0)
    df["Valor_Recomendado_USD"] = df["Peso_Recomendado"] * total
    df["Diferenca_USD"] = df["Valor_Recomendado_USD"] - df["Valor_USD"]
    df["Diferenca_Peso"] = df["Peso_Recomendado"] - df["Peso_Atual"]

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
        "Ativo",
        "Classe",
        "Quantidade",
        "Preco",
        "Valor_USD",
        "Peso_Atual",
        "Peso_Recomendado",
        "Valor_Recomendado_USD",
        "Diferenca_Peso",
        "Diferenca_USD",
        "Comprar_Vender",
        "Acao",
    ]].sort_values("Diferenca_USD", ascending=False)


# ============================================================
# RELATÓRIO
# ============================================================

def print_report(macro: MacroResult, rebalance: pd.DataFrame) -> None:
    print("\n" + "=" * 100)
    print("GLOBAL_ATIVOS_LOBAO — ROBÔ MACRO DINÂMICO")
    print("=" * 100)
    print(f"Data UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n1) REGIME DINÂMICO")
    print(f"Macro Score:        {macro.macro_score:.2f}/100")
    print(f"Raw Score:          {macro.raw_score:.3f}")
    print(f"Risk Budget:        {macro.risk_budget:.2%}")
    print(f"Defensive Budget:   {macro.defensive_budget:.2%}")
    print(f"Regime:             {macro.regime}")

    print("\n2) INDICADORES")
    print(f"Liquidez T-100:     {macro.indicators.liquidez_t_100:.3f} | peso 20%")
    print(f"Liquidez Hoje:      {macro.indicators.liquidez_hoje:.3f} | peso 15%")
    print(f"Taxa Real 10Y:      {macro.indicators.real_yield_10y:.3f} | peso 5%")
    print(f"Global PMI:         {macro.indicators.global_pmi:.3f} | peso 20%")
    print(f"OECD CLI:           {macro.indicators.oecd_cli:.3f} | peso 15%")
    print(f"HY Spread:          {macro.indicators.hy_spread:.3f} | peso 15%")
    print(f"NFCI:               {macro.indicators.nfci:.3f} | peso 10%")
    print(f"Filtro composto:    {macro.indicators.filtro_composto:.3f} | freio")

    print("\n3) REBALANCEAMENTO SUGERIDO")
    show = rebalance.copy()

    for col in ["Preco", "Valor_USD", "Valor_Recomendado_USD", "Diferenca_USD"]:
        show[col] = show[col].map(lambda x: f"{x:,.2f}")

    for col in ["Peso_Atual", "Peso_Recomendado", "Diferenca_Peso"]:
        show[col] = show[col].map(lambda x: f"{x:.2%}")

    print(show.to_string(index=False))

    print("\n4) NOTA OPERACIONAL")
    print("- O robô NÃO executa ordens.")
    print("- Não há tabela fixa de peso por regime.")
    print("- Os indicadores determinam o orçamento de risco.")
    print("- A carteira real determina apenas o peso atual.")
    print("- PMI/OECD estão manuais nesta versão; se ficarem None, entram como neutros.")
    print("- WALCL é proxy parcial; versão institucional deve usar liquidez global composta.")
    print("=" * 100)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Entradas manuais opcionais até automatizar PMI/OECD.
    Deixe None para neutro.
    """
    GLOBAL_PMI = None
    OECD_CLI = None
    OECD_CLI_SLOPE = None

    print("Testando FRED...")
    test_series = fetch_fred_series("DFII10")
    print(test_series.tail())
    print("FRED OK\n")

    fred = fetch_all_fred()

    macro = calculate_macro_result(
        fred=fred,
        global_pmi=GLOBAL_PMI,
        oecd_cli=OECD_CLI,
        oecd_cli_slope=OECD_CLI_SLOPE,
    )

    portfolio = load_portfolio("portfolio.csv")
    prices = get_prices_yfinance(portfolio["Ativo"].tolist())
    portfolio_values = calculate_portfolio_values(portfolio, prices)

    recommended_weights = calculate_dynamic_recommended_weights(macro)
    rebalance = rebalance_suggestions(portfolio_values, recommended_weights)

    rebalance.to_csv("rebalance_output.csv", index=False)

    print_report(macro, rebalance)

    print("\nArquivo gerado: rebalance_output.csv")


if __name__ == "__main__":
    main()
