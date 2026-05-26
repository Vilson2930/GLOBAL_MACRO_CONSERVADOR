"""
engine/regime.py

Motor de regime macro do GLOBAL_MACRO_ENGINE.

Responsável por:
- Calcular os 8 indicadores ponderados
- Aplicar liquidez T-100 e liquidez hoje
- Gerar Macro Score 0–100
- Gerar Risk Budget e Defensive Budget
- Classificar regime
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from settings import (
    LAG_LIQUIDEZ_DIAS,
    INDICATOR_WEIGHTS,
    BULL_THRESHOLD,
    EXPANSAO_THRESHOLD,
    NEUTRO_THRESHOLD,
    DESACELERACAO_THRESHOLD,
)


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
class RegimeResult:
    macro_score: float
    raw_score: float
    risk_budget: float
    defensive_budget: float
    regime: str
    indicators: IndicatorScores


def get_latest_value(
    series: pd.Series,
    date: Optional[pd.Timestamp] = None,
) -> float:
    if date is None:
        date = pd.Timestamp.today()

    valid = series.loc[series.index <= date]

    if valid.empty:
        raise ValueError("Sem dado disponível até a data solicitada.")

    return float(valid.iloc[-1])


def slope_score(
    series: pd.Series,
    lookback: int = 90,
    higher_is_better: bool = True,
) -> float:
    s = series.dropna()

    if len(s) < lookback + 5:
        return 0.0

    recent = float(s.iloc[-1])
    past = float(s.iloc[-lookback])

    if past == 0:
        raw = recent - past
    else:
        raw = (recent - past) / abs(past)

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


# ==========================================================
# INDICADOR 1 E 2 — LIQUIDEZ
# ==========================================================

def calculate_liquidity_score(
    fred: Dict[str, pd.Series],
    as_of: pd.Timestamp,
) -> float:
    """
    Liquidez proxy v1: WALCL.

    Regra:
    - expansão do balanço = positivo
    - contração do balanço = negativo

    Versão institucional futura:
    substituir WALCL por liquidez global composta:
    Fed + ECB + BoJ + PBoC em USD.
    """

    fed_assets = fred["fed_assets"].loc[
        fred["fed_assets"].index <= as_of
    ]

    if len(fed_assets) < 120:
        return 0.0

    return slope_score(
        fed_assets,
        lookback=100,
        higher_is_better=True,
    )


# ==========================================================
# INDICADOR 3 — TAXA REAL 10Y
# ==========================================================

def calculate_real_yield_score(
    fred: Dict[str, pd.Series],
) -> float:
    """
    Taxa real 10Y.

    Regra:
    - taxa real caindo = positivo
    - taxa real baixa = positivo
    - taxa real alta/subindo = negativo
    """

    real_yield = fred["real_yield_10y"]

    trend = slope_score(
        real_yield,
        lookback=60,
        higher_is_better=False,
    )

    level = level_score(
        get_latest_value(real_yield),
        positive_threshold=0.50,
        negative_threshold=2.00,
        lower_is_better=True,
    )

    return float(np.clip(0.60 * trend + 0.40 * level, -1, 1))


# ==========================================================
# INDICADORES 4 E 5 — CRESCIMENTO
# ==========================================================

def calculate_pmi_score(
    global_pmi: Optional[float],
) -> float:
    if global_pmi is None:
        return 0.0

    if global_pmi >= 52:
        return 1.0

    if global_pmi <= 49:
        return -1.0

    return 0.0


def calculate_oecd_cli_score(
    oecd_cli: Optional[float],
) -> float:
    if oecd_cli is None:
        return 0.0

    if oecd_cli >= 100.5:
        return 1.0

    if oecd_cli <= 99.5:
        return -1.0

    return 0.0


# ==========================================================
# INDICADORES 6 E 7 — CRÉDITO
# ==========================================================

def calculate_hy_spread_score(
    fred: Dict[str, pd.Series],
) -> float:
    hy = fred["hy_spread"]

    level = level_score(
        get_latest_value(hy),
        positive_threshold=3.50,
        negative_threshold=5.50,
        lower_is_better=True,
    )

    trend = slope_score(
        hy,
        lookback=60,
        higher_is_better=False,
    )

    return float(np.clip(0.60 * level + 0.40 * trend, -1, 1))


def calculate_nfci_score(
    fred: Dict[str, pd.Series],
) -> float:
    nfci = fred["nfci"]

    level = level_score(
        get_latest_value(nfci),
        positive_threshold=-0.25,
        negative_threshold=0.25,
        lower_is_better=True,
    )

    trend = slope_score(
        nfci,
        lookback=60,
        higher_is_better=False,
    )

    return float(np.clip(0.60 * level + 0.40 * trend, -1, 1))


# ==========================================================
# INDICADOR 8 — FILTRO COMPOSTO
# ==========================================================

def calculate_filter_score(
    fred: Dict[str, pd.Series],
) -> float:
    """
    Filtro composto:
    - Curva 10Y–3M
    - VIX
    - DXY proxy

    O filtro não entra nos 100% dos pesos principais.
    Ele atua como freio quando negativo.
    """

    curve = get_latest_value(
        fred["yield_curve_10y_3m"]
    )

    vix = get_latest_value(
        fred["vix"]
    )

    curve_score = level_score(
        curve,
        positive_threshold=0.50,
        negative_threshold=-0.50,
    )

    vix_score = level_score(
        vix,
        positive_threshold=18.0,
        negative_threshold=28.0,
        lower_is_better=True,
    )

    dxy_score = slope_score(
        fred["dxy_proxy"],
        lookback=60,
        higher_is_better=False,
    )

    return float(
        np.clip(
            np.mean([
                curve_score,
                vix_score,
                dxy_score,
            ]),
            -1,
            1,
        )
    )


# ==========================================================
# SCORE FINAL
# ==========================================================

def classify_regime(
    macro_score: float,
) -> str:
    if macro_score >= BULL_THRESHOLD:
        return "BULL"

    if macro_score >= EXPANSAO_THRESHOLD:
        return "EXPANSAO"

    if macro_score >= NEUTRO_THRESHOLD:
        return "NEUTRO"

    if macro_score >= DESACELERACAO_THRESHOLD:
        return "DESACELERACAO"

    return "STRESS"


def calculate_macro_score(
    indicators: IndicatorScores,
) -> tuple[float, float]:
    raw_score = (
        INDICATOR_WEIGHTS["liquidez_t_100"] * indicators.liquidez_t_100
        + INDICATOR_WEIGHTS["liquidez_hoje"] * indicators.liquidez_hoje
        + INDICATOR_WEIGHTS["real_yield_10y"] * indicators.real_yield_10y
        + INDICATOR_WEIGHTS["global_pmi"] * indicators.global_pmi
        + INDICATOR_WEIGHTS["oecd_cli"] * indicators.oecd_cli
        + INDICATOR_WEIGHTS["hy_spread"] * indicators.hy_spread
        + INDICATOR_WEIGHTS["nfci"] * indicators.nfci
    )

    raw_score = float(np.clip(raw_score, -1, 1))

    macro_score = 50 + (raw_score * 50)

    # filtro atua como freio se negativo
    if indicators.filtro_composto < 0:
        macro_score += indicators.filtro_composto * 10

    macro_score = float(np.clip(macro_score, 0, 100))

    return macro_score, raw_score


def calculate_risk_budget(
    macro_score: float,
) -> tuple[float, float]:
    """
    Converte Macro Score em orçamento de risco.

    0   = 0% risco
    50  = 50% risco
    100 = 100% risco

    Limites de segurança podem ser aplicados futuramente em risk.py.
    """

    risk_budget = macro_score / 100
    defensive_budget = 1.0 - risk_budget

    return risk_budget, defensive_budget


def calculate_regime(
    fred: Dict[str, pd.Series],
    global_pmi: Optional[float] = None,
    oecd_cli: Optional[float] = None,
) -> RegimeResult:
    """
    Função principal do regime.py.

    Entrada:
    - fred: dicionário de séries vindas do market_data.fetch_all_fred()
    - global_pmi: manual/automático futuramente
    - oecd_cli: manual/automático futuramente

    Saída:
    - Macro Score
    - Risk Budget
    - Defensive Budget
    - Regime
    - Scores individuais
    """

    today = pd.Timestamp.today()
    lag_date = today - pd.Timedelta(days=LAG_LIQUIDEZ_DIAS)

    indicators = IndicatorScores(
        liquidez_t_100=calculate_liquidity_score(
            fred,
            as_of=lag_date,
        ),
        liquidez_hoje=calculate_liquidity_score(
            fred,
            as_of=today,
        ),
        real_yield_10y=calculate_real_yield_score(
            fred,
        ),
        global_pmi=calculate_pmi_score(
            global_pmi,
        ),
        oecd_cli=calculate_oecd_cli_score(
            oecd_cli,
        ),
        hy_spread=calculate_hy_spread_score(
            fred,
        ),
        nfci=calculate_nfci_score(
            fred,
        ),
        filtro_composto=calculate_filter_score(
            fred,
        ),
    )

    macro_score, raw_score = calculate_macro_score(
        indicators
    )

    risk_budget, defensive_budget = calculate_risk_budget(
        macro_score
    )

    regime = classify_regime(
        macro_score
    )

    return RegimeResult(
        macro_score=macro_score,
        raw_score=raw_score,
        risk_budget=risk_budget,
        defensive_budget=defensive_budget,
        regime=regime,
        indicators=indicators,
    )
