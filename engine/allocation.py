from __future__ import annotations

from typing import Dict

from settings import (
    RISK_ASSETS,
    DEFENSIVE_ASSETS,
)

from engine.asset_models import ASSET_FACTORS


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


def positive_score(x: float) -> float:
    return max(0.05, 1.0 + x)


def calculate_asset_scores(regime_result):

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

    for asset, exposures in ASSET_FACTORS.items():

        raw_score = 0.0

        for factor_name, factor_weight in exposures.items():

            raw_score += (
                factor_weight
                * factors[factor_name]
            )

        scores[asset] = positive_score(raw_score)

    return scores


def calculate_dynamic_allocation(
    regime_result
):

    scores = calculate_asset_scores(
        regime_result
    )

    risk_budget = float(
        regime_result.risk_budget
    )

    defensive_budget = float(
        regime_result.defensive_budget
    )

    risk_scores = {
        a: scores[a]
        for a in RISK_ASSETS
    }

    defensive_scores = {
        a: scores[a]
        for a in DEFENSIVE_ASSETS
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
            weight
            * risk_budget
        )

    for asset, weight in defensive_weights.items():

        allocation[asset] = (
            weight
            * defensive_budget
        )

    return allocation


def explain_allocation(
    regime_result,
    allocation,
):

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
        reverse=True,
    ):

        lines.append(
            f"{asset}: {score:.4f}"
        )

    lines.append("")
    lines.append("ALLOCATION")

    for asset, weight in sorted(
        allocation.items(),
        key=lambda x: x[1],
        reverse=True,
    ):

        lines.append(
            f"{asset}: {weight:.2%}"
        )

    return "\n".join(lines)
