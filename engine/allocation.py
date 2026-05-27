"""
engine/allocation.py

Alocação macro por matriz de sensibilidade econômica.

Fluxo:
Macro indicators -> Asset factor scores -> Risk/Defense budget -> Final allocation
"""

from __future__ import annotations

from typing import Dict

from settings import RISK_ASSETS, DEFENSIVE_ASSETS
from engine.asset_models import ASSET_FACTORS, ASSET_LIMITS


def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = float(sum(weights.values()))

    if total <= 0:
        n = len(weights)
        return {asset: 1.0 / n for asset in weights}

    return {asset: value / total for asset, value in weights.items()}


def positive_score(value: float) -> float:
    return clamp(1.0 + value, 0.05, 3.0)


def build_macro_factors(regime_result) -> Dict[str, float]:
    i = regime_result.indicators

    liquidity = 0.60 * i.liquidez_hoje + 0.40 * i.liquidez_t_100
    growth = 0.55 * i.global_pmi + 0.45 * i.oecd_cli
    credit = 0.60 * i.hy_spread + 0.40 * i.nfci
    real_yield = i.real_yield_10y
    stress = -i.filtro_composto
    usd = -i.filtro_composto

    return {
        "liquidity": liquidity,
        "growth": growth,
        "credit": credit,
        "real_yield": real_yield,
        "stress": stress,
        "usd": usd,
    }


def calculate_asset_scores(regime_result) -> Dict[str, float]:
    macro = build_macro_factors(regime_result)

    scores = {}

    for asset, factors in ASSET_FACTORS.items():
        raw_score = 0.0

        for factor_name, sensitivity in factors.items():
            raw_score += sensitivity * macro.get(factor_name, 0.0)

        scores[asset] = positive_score(raw_score)

    return scores


def apply_limits(weights: Dict[str, float]) -> Dict[str, float]:
    assets = list(weights.keys())

    final = {asset: 0.0 for asset in assets}
    remaining_assets = set(assets)
    remaining_weight = 1.0

    for asset in assets:
        limits = ASSET_LIMITS.get(asset, {"min": 0.0, "max": 1.0})
        min_weight = float(limits.get("min", 0.0))

        final[asset] = min_weight
        remaining_weight -= min_weight

    if remaining_weight <= 0:
        return normalize(final)

    base = {asset: max(float(weights[asset]), 0.0) for asset in assets}

    while remaining_assets:
        active_base = {asset: base[asset] for asset in remaining_assets}
        active_weights = normalize(active_base)

        hit_limit = False

        for asset in list(remaining_assets):
            limits = ASSET_LIMITS.get(asset, {"min": 0.0, "max": 1.0})
            max_weight = float(limits.get("max", 1.0))

            candidate = final[asset] + remaining_weight * active_weights[asset]

            if candidate > max_weight:
                used = max_weight - final[asset]
                final[asset] = max_weight
                remaining_weight -= used
                remaining_assets.remove(asset)
                hit_limit = True

        if not hit_limit:
            for asset in remaining_assets:
                final[asset] += remaining_weight * active_weights[asset]
            break

    return final


def calculate_dynamic_allocation(regime_result) -> Dict[str, float]:
    risk_budget = float(regime_result.risk_budget)
    defensive_budget = float(regime_result.defensive_budget)

    scores = calculate_asset_scores(regime_result)

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

    risk_weights = normalize(risk_scores)
    defensive_weights = normalize(defensive_scores)

    allocation = {}

    for asset, weight in risk_weights.items():
        allocation[asset] = risk_budget * weight

    for asset, weight in defensive_weights.items():
        allocation[asset] = defensive_budget * weight

    return apply_limits(allocation)


def explain_allocation(regime_result, allocation: Dict[str, float]) -> str:
    scores = calculate_asset_scores(regime_result)
    macro = build_macro_factors(regime_result)

    lines = [
        f"Regime: {regime_result.regime}",
        f"Macro Score: {regime_result.macro_score:.2f}",
        f"Risk Budget: {regime_result.risk_budget:.2%}",
        f"Defensive Budget: {regime_result.defensive_budget:.2%}",
        "",
        "FATORES MACRO",
    ]

    for factor, value in macro.items():
        lines.append(f"{factor}: {value:.3f}")

    lines.append("")
    lines.append("SCORES POR ATIVO")

    for asset, score in scores.items():
        lines.append(f"{asset}: {score:.3f}")

    lines.append("")
    lines.append("ALOCAÇÃO FINAL")

    for asset, weight in allocation.items():
        lines.append(f"{asset}: {weight:.2%}")

    return "\n".join(lines)
