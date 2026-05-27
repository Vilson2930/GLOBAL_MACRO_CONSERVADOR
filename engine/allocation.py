"""
engine/allocation.py

Alocação dinâmica por orçamento de risco + score individual por ativo.

Lógica:
1. Regime macro define quanto vai para risco e defesa.
2. Cada ativo recebe score próprio conforme os indicadores.
3. O orçamento do grupo é distribuído proporcionalmente aos scores.
4. Não há peso fixo por ativo.
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from settings import RISK_ASSETS, DEFENSIVE_ASSETS


def clamp(value: float, low: float, high: float) -> float:
    return float(max(low, min(high, value)))


def normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = float(sum(weights.values()))

    if total <= 0:
        n = len(weights)
        return {asset: 1.0 / n for asset in weights}

    return {asset: float(weight / total) for asset, weight in weights.items()}


def score_to_positive(value: float) -> float:
    """
    Converte score macro em número positivo.
    Evita pesos negativos e mantém diferenciação entre ativos.
    """
    return clamp(1.0 + value, 0.05, 3.0)


def calculate_asset_scores(regime_result) -> Dict[str, float]:
    i = regime_result.indicators

    liquidity = 0.60 * i.liquidez_hoje + 0.40 * i.liquidez_t_100
    growth = 0.55 * i.global_pmi + 0.45 * i.oecd_cli
    credit = 0.60 * i.hy_spread + 0.40 * i.nfci
    real_yield = i.real_yield_10y
    filter_score = i.filtro_composto

    raw_scores = {
        # BTC: depende muito de liquidez e taxa real
        "BTC-USD": (
            0.40 * liquidity
            + 0.30 * real_yield
            + 0.20 * credit
            + 0.10 * filter_score
        ),

        # VOO: depende mais de crescimento e crédito
        "VOO": (
            0.35 * growth
            + 0.30 * credit
            + 0.20 * liquidity
            + 0.15 * filter_score
        ),

        # BOTZ: risco alto, sensível a liquidez e taxa real
        "BOTZ": (
            0.35 * liquidity
            + 0.25 * real_yield
            + 0.25 * growth
            + 0.15 * credit
        ),

        # INDA: emergente, sensível a crescimento e liquidez
        "INDA": (
            0.35 * growth
            + 0.25 * liquidity
            + 0.25 * credit
            + 0.15 * filter_score
        ),

        # TLT: favorecido por desaceleração e taxa real menos restritiva
        "TLT": (
            -0.35 * growth
            -0.30 * real_yield
            + 0.20 * credit
            -0.15 * liquidity
        ),

        # GLD: favorecido por taxa real ruim, liquidez fraca e proteção
        "GLD": (
            -0.35 * real_yield
            -0.25 * liquidity
            -0.20 * filter_score
            + 0.20 * credit
        ),

        # USDT: caixa sobe quando liquidez/filtro estão ruins
        "USDT": (
            -0.40 * liquidity
            -0.30 * filter_score
            -0.20 * growth
            + 0.10 * credit
        ),
    }

    return {
        asset: score_to_positive(score)
        for asset, score in raw_scores.items()
    }


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

    allocation: Dict[str, float] = {}

    for asset, weight in risk_weights.items():
        allocation[asset] = risk_budget * weight

    for asset, weight in defensive_weights.items():
        allocation[asset] = defensive_budget * weight

    return normalize(allocation)


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
    lines.append("ALOCAÇÃO RECOMENDADA")

    for asset, weight in allocation.items():
        lines.append(f"{asset}: {weight:.2%}")

    return "\n".join(lines)
