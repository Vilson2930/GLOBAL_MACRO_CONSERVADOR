"""
engine/allocation.py

Alocação dinâmica institucional:
Macro Score -> Risk Budget / Defensive Budget
-> Score individual por ativo
-> limites estruturais por ativo
-> penalização de satélites em desaceleração
-> pesos finais normalizados
"""

from __future__ import annotations

from typing import Dict

from settings import RISK_ASSETS, DEFENSIVE_ASSETS


ASSET_LIMITS = {
    "BTC-USD": {"min": 0.05, "max": 0.25},
    "VOO": {"min": 0.10, "max": 0.35},
    "BOTZ": {"min": 0.00, "max": 0.08},
    "INDA": {"min": 0.00, "max": 0.08},
    "TLT": {"min": 0.05, "max": 0.35},
    "GLD": {"min": 0.05, "max": 0.25},
    "USDT": {"min": 0.05, "max": 0.30},
}


def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())

    if total <= 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}

    return {k: v / total for k, v in weights.items()}


def apply_limits(weights: Dict[str, float]) -> Dict[str, float]:
    limited = {}

    for asset, weight in weights.items():
        limits = ASSET_LIMITS.get(asset, {"min": 0.0, "max": 1.0})
        limited[asset] = clamp(weight, limits["min"], limits["max"])

    return normalize(limited)


def positive_score(x: float) -> float:
    return clamp(1.0 + x, 0.05, 3.0)


def calculate_asset_scores(regime_result) -> Dict[str, float]:
    i = regime_result.indicators

    liquidity = 0.60 * i.liquidez_hoje + 0.40 * i.liquidez_t_100
    growth = 0.55 * i.global_pmi + 0.45 * i.oecd_cli
    credit = 0.60 * i.hy_spread + 0.40 * i.nfci
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

    if regime_result.macro_score < 50:
        raw["INDA"] *= 0.65
        raw["BOTZ"] *= 0.75

    if regime_result.macro_score < 40:
        raw["BTC-USD"] *= 0.80
        raw["INDA"] *= 0.70
        raw["BOTZ"] *= 0.70

    return {asset: positive_score(score) for asset, score in raw.items()}


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

    risk_internal = normalize(risk_scores)
    defensive_internal = normalize(defensive_scores)

    raw_allocation = {}

    for asset, weight in risk_internal.items():
        raw_allocation[asset] = risk_budget * weight

    for asset, weight in defensive_internal.items():
        raw_allocation[asset] = defensive_budget * weight

    return apply_limits(raw_allocation)


def explain_allocation(regime_result, allocation: Dict[str, float]) -> str:
    scores = calculate_asset_scores(regime_result)

    lines = [
        f"Regime: {regime_result.regime}",
        f"Macro Score: {regime_result.macro_score:.2f}",
        f"Risk Budget: {regime_result.risk_budget:.2%}",
        f"Defensive Budget: {regime_result.defensive_budget:.2%}",
        "",
        "SCORES INDIVIDUAIS",
    ]

    for asset, score in scores.items():
        lines.append(f"{asset}: {score:.3f}")

    lines.append("")
    lines.append("ALOCAÇÃO FINAL")

    for asset, weight in allocation.items():
        lines.append(f"{asset}: {weight:.2%}")

    return "\n".join(lines)
