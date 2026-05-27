"""
engine/allocation.py

Alocação dinâmica por orçamento de risco + score individual por ativo.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from settings import RISK_ASSETS, DEFENSIVE_ASSETS


def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        n = len(weights)
        return {k: 1 / n for k in weights}
    return {k: v / total for k, v in weights.items()}


def calculate_asset_scores(regime_result) -> Dict[str, float]:
    i = regime_result.indicators

    liquidity = 0.60 * i.liquidez_hoje + 0.40 * i.liquidez_t_100
    growth = 0.55 * i.global_pmi + 0.45 * i.oecd_cli
    credit = 0.60 * i.hy_spread + 0.40 * i.nfci
    real_yield = i.real_yield_10y
    filter_score = i.filtro_composto

    scores = {
        "BTC-USD": 1.00 + 0.45 * liquidity + 0.30 * real_yield + 0.15 * credit,
        "VOO": 1.00 + 0.35 * growth + 0.30 * credit + 0.20 * liquidity,
        "BOTZ": 1.00 + 0.35 * liquidity + 0.25 * growth + 0.25 * real_yield,
        "INDA": 1.00 + 0.35 * growth + 0.25 * liquidity + 0.20 * filter_score,
        "TLT": 1.00 - 0.35 * growth - 0.25 * real_yield + 0.25 * credit,
        "GLD": 1.00 - 0.30 * real_yield - 0.20 * filter_score - 0.15 * liquidity,
        "USDT": 1.00 - 0.35 * liquidity - 0.25 * filter_score,
    }

    return {k: clamp(v, 0.05, 3.0) for k, v in scores.items()}


def calculate_dynamic_allocation(regime_result) -> Dict[str, float]:
    risk_budget = float(regime_result.risk_budget)
    defensive_budget = float(regime_result.defensive_budget)

    scores = calculate_asset_scores(regime_result)

    risk_scores = {a: scores[a] for a in RISK_ASSETS if a in scores}
    defensive_scores = {a: scores[a] for a in DEFENSIVE_ASSETS if a in scores}

    risk_weights = normalize(risk_scores)
    defensive_weights = normalize(defensive_scores)

    allocation = {}

    for asset, weight in risk_weights.items():
        allocation[asset] = risk_budget * weight

    for asset, weight in defensive_weights.items():
        allocation[asset] = defensive_budget * weight

    return normalize(allocation)


def explain_allocation(regime_result, allocation: Dict[str, float]) -> str:
    lines = [
        f"Regime: {regime_result.regime}",
        f"Macro Score: {regime_result.macro_score:.2f}",
        f"Risk Budget: {regime_result.risk_budget:.2%}",
        f"Defensive Budget: {regime_result.defensive_budget:.2%}",
        "",
        "ALOCAÇÃO RECOMENDADA",
    ]

    for asset, weight in allocation.items():
        lines.append(f"{asset}: {weight:.2%}")

    return "\n".join(lines)
