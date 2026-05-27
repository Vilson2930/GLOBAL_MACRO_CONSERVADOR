"""
engine/allocation.py

Alocação dinâmica institucional.

Fluxo:

Indicadores Macro
        ↓
Asset Factors
        ↓
Score Individual
        ↓
Risk Budget / Defensive Budget
        ↓
Limites Estruturais
        ↓
Alocação Final
"""

from __future__ import annotations

from typing import Dict

from settings import (
    RISK_ASSETS,
    DEFENSIVE_ASSETS,
)

from engine.asset_factors import ASSET_FACTORS


# ==========================================================
# LIMITES ESTRUTURAIS
# ==========================================================

ASSET_LIMITS = {

    "BTC-USD": {"min": 0.00, "max": 0.25},

    "VOO": {"min": 0.05, "max": 0.40},

    "BOTZ": {"min": 0.00, "max": 0.10},

    "INDA": {"min": 0.00, "max": 0.10},

    "TLT": {"min": 0.05, "max": 0.40},

    "GLD": {"min": 0.05, "max": 0.30},

    "USDT": {"min": 0.05, "max": 0.40},
}


# ==========================================================
# HELPERS
# ==========================================================

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize(weights: Dict[str, float]) -> Dict[str, float]:

    total = sum(weights.values())

    if total <= 0:

        n = len(weights)

        return {
            k: 1.0 / n
            for k in weights
        }

    return {
        k: v / total
        for k, v in weights.items()
    }


def score_to_positive(score: float) -> float:

    return clamp(
        1.0 + score,
        0.05,
        3.0
    )


# ==========================================================
# LIMITES
# ==========================================================

def apply_limits(
    weights: Dict[str, float]
) -> Dict[str, float]:

    limited = {}

    for asset, weight in weights.items():

        limits = ASSET_LIMITS.get(
            asset,
            {"min": 0.0, "max": 1.0}
        )

        limited[asset] = clamp(
            weight,
            limits["min"],
            limits["max"]
        )

    return normalize(limited)


# ==========================================================
# SCORE POR ATIVO
# ==========================================================

def calculate_asset_scores(
    regime_result
) -> Dict[str, float]:

    i = regime_result.indicators

    liquidity = (
        0.60 * i.liquidez_hoje
        + 0.40 * i.liquidez_t_100
    )

    growth = (
        0.55 * i.global_pmi
        + 0.45 * i.oecd_cli
    )

    credit = (
        0.60 * i.hy_spread
        + 0.40 * i.nfci
    )

    real_yield = i.real_yield_10y

    filter_score = i.filtro_composto

    macro_factors = {

        "growth": growth,

        "liquidity": liquidity,

        "credit": credit,

        "real_yield": real_yield,

        "filter": filter_score,
    }

    scores = {}

    for asset, factors in ASSET_FACTORS.items():

        raw_score = 0.0

        for factor, factor_weight in factors.items():

            raw_score += (
                macro_factors.get(factor, 0.0)
                * factor_weight
            )

        # penalização automática
        # para satélites em desaceleração

        if regime_result.macro_score < 50:

            if asset in ["BOTZ", "INDA"]:

                raw_score *= 0.75

        if regime_result.macro_score < 40:

            if asset in ["BTC-USD", "BOTZ", "INDA"]:

                raw_score *= 0.70

        scores[asset] = score_to_positive(
            raw_score
        )

    return scores


# ==========================================================
# ALOCAÇÃO
# ==========================================================

def calculate_dynamic_allocation(
    regime_result
) -> Dict[str, float]:

    risk_budget = float(
        regime_result.risk_budget
    )

    defensive_budget = float(
        regime_result.defensive_budget
    )

    scores = calculate_asset_scores(
        regime_result
    )

    risk_scores = {

        asset: scores[asset]

        for asset in RISK_ASSETS

        if asset in scores
    }

    defensive_scores = {

        asset: scores[asset]

        for asset in DEFENSIVE_ASSETS

        if asset in scores
    }

    risk_internal = normalize(
        risk_scores
    )

    defensive_internal = normalize(
        defensive_scores
    )

    allocation = {}

    for asset, weight in risk_internal.items():

        allocation[asset] = (
            risk_budget * weight
        )

    for asset, weight in defensive_internal.items():

        allocation[asset] = (
            defensive_budget * weight
        )

    allocation = apply_limits(
        allocation
    )

    return allocation


# ==========================================================
# EXPLICAÇÃO
# ==========================================================

def explain_allocation(
    regime_result,
    allocation: Dict[str, float],
) -> str:

    scores = calculate_asset_scores(
        regime_result
    )

    lines = []

    lines.append(
        f"Regime: {regime_result.regime}"
    )

    lines.append(
        f"Macro Score: {regime_result.macro_score:.2f}"
    )

    lines.append(
        f"Risk Budget: {regime_result.risk_budget:.2%}"
    )

    lines.append(
        f"Defensive Budget: {regime_result.defensive_budget:.2%}"
    )

    lines.append("")
    lines.append("SCORES")

    for asset, score in scores.items():

        lines.append(
            f"{asset}: {score:.4f}"
        )

    lines.append("")
    lines.append("ALOCAÇÃO FINAL")

    for asset, weight in allocation.items():

        lines.append(
            f"{asset}: {weight:.2%}"
        )

    return "\n".join(lines)
