# ============================================================
# engine/regime.py CORRIGIDO
# ============================================================

from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# DATACLASS DOS INDICADORES
# ============================================================

@dataclass
class IndicatorScores:

    liquidez_hoje: float
    liquidez_t_100: float

    global_pmi: float
    oecd_cli: float

    hy_spread: float
    nfci: float

    real_yield_10y: float
    yield_curve_10y_3m: float

    dxy_proxy: float
    vix: float

    filtro_composto: float


# ============================================================
# RESULTADO FINAL DO REGIME
# ============================================================

@dataclass
class RegimeResult:

    macro_score: float
    raw_score: float

    risk_budget: float
    defensive_budget: float

    regime: str

    indicators: IndicatorScores


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def clamp(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


# ============================================================
# SCORES INDIVIDUAIS
# ============================================================

def calculate_liquidity_score(fred) -> float:

    val = fred["fed_assets"]["zscore"]

    return clamp(val, -2.0, 2.0)


def calculate_growth_score(fred) -> tuple[float, float]:

    pmi = fred["global_pmi"]["zscore"]
    cli = fred["oecd_cli"]["zscore"]

    return (
        clamp(pmi, -2.0, 2.0),
        clamp(cli, -2.0, 2.0),
    )


def calculate_credit_score(fred) -> tuple[float, float]:

    hy = -fred["hy_spread"]["zscore"]
    nfci = -fred["nfci"]["zscore"]

    return (
        clamp(hy, -2.0, 2.0),
        clamp(nfci, -2.0, 2.0),
    )


def calculate_real_yield_score(fred) -> float:

    val = -fred["real_yield_10y"]["zscore"]

    return clamp(val, -2.0, 2.0)


def calculate_curve_score(fred) -> float:

    val = fred["yield_curve_10y_3m"]["zscore"]

    return clamp(val, -2.0, 2.0)


def calculate_dxy_score(fred) -> float:

    val = -fred["dxy_proxy"]["zscore"]

    return clamp(val, -2.0, 2.0)


def calculate_vix_score(fred) -> float:

    val = -fred["vix"]["zscore"]

    return clamp(val, -2.0, 2.0)


def calculate_filter_score(
    liquidity: float,
    growth: float,
    credit: float,
    real_yield: float,
    curve: float,
    dxy: float,
    vix: float,
) -> float:

    score = (
        0.25 * liquidity
        + 0.20 * growth
        + 0.20 * credit
        + 0.15 * real_yield
        + 0.10 * curve
        + 0.05 * dxy
        + 0.05 * vix
    )

    return clamp(score, -2.0, 2.0)


# ============================================================
# REGIME ENGINE
# ============================================================

def calculate_regime(fred) -> RegimeResult:

    liquidez_hoje = calculate_liquidity_score(fred)
    liquidez_t_100 = liquidez_hoje

    global_pmi, oecd_cli = calculate_growth_score(fred)

    hy_spread, nfci = calculate_credit_score(fred)

    real_yield_10y = calculate_real_yield_score(fred)

    yield_curve_10y_3m = calculate_curve_score(fred)

    dxy_proxy = calculate_dxy_score(fred)

    vix = calculate_vix_score(fred)

    filtro_composto = calculate_filter_score(
        liquidity=liquidez_hoje,
        growth=(global_pmi + oecd_cli) / 2,
        credit=(hy_spread + nfci) / 2,
        real_yield=real_yield_10y,
        curve=yield_curve_10y_3m,
        dxy=dxy_proxy,
        vix=vix,
    )

    raw_score = filtro_composto

    macro_score = 50 + (raw_score * 25)

    macro_score = clamp(macro_score, 0, 100)

    risk_budget = clamp(macro_score / 100, 0.10, 0.90)

    defensive_budget = 1.0 - risk_budget

    # ========================================================
    # CLASSIFICAÇÃO
    # ========================================================

    if macro_score >= 70:
        regime = "EXPANSAO"

    elif macro_score >= 55:
        regime = "RECUPERACAO"

    elif macro_score >= 40:
        regime = "DESACELERACAO"

    else:
        regime = "CONTRACAO"

    indicators = IndicatorScores(

        liquidez_hoje=liquidez_hoje,
        liquidez_t_100=liquidez_t_100,

        global_pmi=global_pmi,
        oecd_cli=oecd_cli,

        hy_spread=hy_spread,
        nfci=nfci,

        real_yield_10y=real_yield_10y,
        yield_curve_10y_3m=yield_curve_10y_3m,

        dxy_proxy=dxy_proxy,
        vix=vix,

        filtro_composto=filtro_composto,
    )

    return RegimeResult(

        macro_score=macro_score,
        raw_score=raw_score,

        risk_budget=risk_budget,
        defensive_budget=defensive_budget,

        regime=regime,

        indicators=indicators,
    )
