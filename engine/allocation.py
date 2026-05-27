"""
engine/allocation.py

Alocação institucional baseada em fatores macro.

Não utiliza:
- Risk Budget
- Defensive Budget
- Buckets fixos

Todos os ativos competem entre si
pelos mesmos indicadores macro.
"""

from __future__ import annotations

from typing import Dict

from engine.asset_models import (
    ASSET_FACTORS,
    ASSET_LIMITS,
)


# ============================================================
# UTIL
# ============================================================

def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def normalize(weights: Dict[str, float]) -> Dict[str, float]:

    total = sum(weights.values())

    if total <= 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}

    return {
        k: v / total
        for k, v in weights.items()
    }


# ============================================================
# SCORE DOS ATIVOS
# ============================================================

def calculate_asset_scores(regime_result) -> Dict[str, float]:

    i = regime_result.indicators

    factors = {
        "liquidity":
            0.60 * i.liquidez_hoje
            + 0.40 * i.liquidez_t_100,

        "growth":
            0.55 * i.global_pmi
            + 0.45 * i.oecd_cli,

        "credit":
            0.60 * i.hy_spread
            + 0.40 * i.nfci,

        "real_yield":
            i.real_yield_10y,

        "usd":
            i.dxy_proxy,

        "stress":
            i.vix,
    }

    scores = {}

    for asset, model in ASSET_FACTORS.items():

        score = 1.0

        for factor_name, sensitivity in model.items():

            factor_value = factors.get(
                factor_name,
                0.0
            )

            score += sensitivity * factor_value

        scores[asset] = max(score, 0.05)

    return scores


# ============================================================
# ALOCAÇÃO FINAL
# ============================================================

def calculate_dynamic_allocation(
    regime_result
) -> Dict[str, float]:

    scores = calculate_asset_scores(
        regime_result
    )

    weighted_scores = {}

    for asset, score in scores.items():

        strength = sum(
            abs(v)
            for v in ASSET_FACTORS[asset].values()
        )

        weighted_scores[asset] = (
            score * strength
        )

    allocation = normalize(
        weighted_scores
    )

    final_weights = {}

    for asset, weight in allocation.items():

        limits = ASSET_LIMITS[asset]

        final_weights[asset] = clamp(
            weight,
            limits["min"],
            limits["max"]
        )

    return normalize(
        final_weights
    )


# ============================================================
# EXPLICAÇÃO
# ============================================================

def explain_allocation(
    regime_result,
    allocation: Dict[str, float]
) -> str:

    scores = calculate_asset_scores(
        regime_result
    )

    lines = [
        f"Regime: {regime_result.regime}",
        f"Macro Score: {regime_result.macro_score:.2f}",
        "",
        "SCORES",
    ]

    for asset, score in sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        lines.append(
            f"{asset}: {score:.4f}"
        )

    lines.append("")
    lines.append("ALLOCATION")

    for asset, weight in sorted(
        allocation.items(),
        key=lambda x: x[1],
        reverse=True
    ):
        lines.append(
            f"{asset}: {weight:.2%}"
        )

    return "\n".join(lines)
