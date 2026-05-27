"""
engine/allocation.py

Alocação dinâmica institucional:

Macro Score
    ↓
Risk Budget / Defensive Budget
    ↓
Score individual por ativo
    ↓
Limites estruturais
    ↓
Pesos finais
"""

from __future__ import annotations

from typing import Dict

from settings import (
    RISK_ASSETS,
    DEFENSIVE_ASSETS,
)


# ==========================================================
# LIMITES ESTRUTURAIS
# ==========================================================

ASSET_LIMITS = {

    "BTC-USD": {"min": 0.05, "max": 0.25},

    "VOO": {"min": 0.10, "max": 0.35},

    "BOTZ": {"min": 0.00, "max": 0.08},

    "INDA": {"min": 0.00, "max": 0.08},

    "TLT": {"min": 0.05, "max": 0.35},

    "GLD": {"min": 0.05, "max": 0.25},

    "USDT": {"min": 0.05, "max": 0.30},
}


# ==========================================================
# HELPERS
# ==========================================================

def clamp(
    value: float,
    low: float,
    high: float,
) -> float:

    return float(
        max(low, min(high, value))
    )


def normalize(
    weights: Dict[str, float],
) -> Dict[str, float]:

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


def positive_score(
    x: float,
) -> float:

    return clamp(
        1.0 + x,
        0.05,
        3.0,
    )


# ==========================================================
# LIMITES REAIS
# ==========================================================

def apply_limits(
    weights: Dict[str, float],
) -> Dict[str, float]:

    assets = list(weights.keys())

    final = {
        asset: 0.0
        for asset in assets
    }

    remaining_assets = set(assets)
    remaining_weight = 1.0

    # ---------------------
    # pisos mínimos
    # ---------------------

    for asset in assets:

        limits = ASSET_LIMITS.get(
            asset,
            {"min": 0.0, "max": 1.0},
        )

        min_weight = limits["min"]

        final[asset] = min_weight

        remaining_weight -= min_weight

    if remaining_weight <= 0:
        return normalize(final)

    # ---------------------
    # redistribuição
    # ---------------------

    base = {
        asset: max(weights[asset], 0.0)
        for asset in assets
    }

    while remaining_assets:

        normalized = normalize(
            {
                asset: base[asset]
                for asset in remaining_assets
            }
        )

        hit_limit = False

        for asset in list(remaining_assets):

            limits = ASSET_LIMITS.get(
                asset,
                {"min": 0.0, "max": 1.0},
            )

            max_weight = limits["max"]

            candidate = (
                final[asset]
                + remaining_weight
                * normalized[asset]
            )

            if candidate > max_weight:

                used = (
                    max_weight
                    - final[asset]
                )

                final[asset] = max_weight

                remaining_weight -= used

                remaining_assets.remove(asset)

                hit_limit = True

        if not hit_limit:

            for asset in remaining_assets:

                final[asset] += (
                    remaining_weight
                    * normalized[asset]
                )

            break

    return final


# ==========================================================
# SCORES DOS ATIVOS
# ==========================================================

def calculate_asset_scores(
    regime_result,
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

    raw = {

        "BTC-USD": (
            0.45 * liquidity
            + 0.30 * real_yield
            + 0.15 * credit
            + 0.10 * filter_score
        ),

        "VOO": (
            0.40 * growth
            + 0.30 * credit
            + 0.20 * liquidity
            + 0.10 * filter_score
        ),

        "BOTZ": (
            0.40 * liquidity
            + 0.30 * real_yield
            + 0.20 * growth
            + 0.10 * credit
        ),

        "INDA": (
            0.40 * growth
            + 0.25 * credit
            + 0.20 * liquidity
            + 0.15 * filter_score
        ),

        "TLT": (
            -0.40 * growth
            -0.35 * real_yield
            -0.10 * liquidity
            + 0.15 * credit
        ),

        "GLD": (
            -0.35 * real_yield
            -0.30 * liquidity
            -0.20 * filter_score
            + 0.15 * credit
        ),

        "USDT": (
            -0.35 * liquidity
            -0.25 * filter_score
            -0.20 * growth
            + 0.20 * credit
        ),
    }

    # ---------------------
    # desaceleração
    # ---------------------

    if regime_result.macro_score < 50:

        raw["INDA"] *= 0.65

        raw["BOTZ"] *= 0.75

    # ---------------------
    # risco elevado
    # ---------------------

    if regime_result.macro_score < 40:

        raw["BTC-USD"] *= 0.80

        raw["INDA"] *= 0.70

        raw["BOTZ"] *= 0.70

    return {
        asset: positive_score(score)
        for asset, score in raw.items()
    }


# ==========================================================
# ALOCAÇÃO
# ==========================================================

def calculate_dynamic_allocation(
    regime_result,
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

    risk_weights = normalize(
        risk_scores
    )

    defensive_weights = normalize(
        defensive_scores
    )

    allocation = {}

    for asset, weight in risk_weights.items():

        allocation[asset] = (
            risk_budget * weight
        )

    for asset, weight in defensive_weights.items():

        allocation[asset] = (
            defensive_budget * weight
        )

    return apply_limits(allocation)


# ==========================================================
# EXPLICAÇÃO
# ==========================================================

def explain_allocation(
    regime_result,
    allocation,
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
            f"{asset}: {score:.3f}"
        )

    lines.append("")
    lines.append("ALOCAÇÃO FINAL")

    for asset, weight in allocation.items():

        lines.append(
            f"{asset}: {weight:.2%}"
        )

    return "\n".join(lines)
