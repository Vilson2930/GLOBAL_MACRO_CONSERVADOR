"""
engine/allocation.py

Motor de alocação dinâmica do GLOBAL_MACRO_ENGINE.

Responsável por:
- Converter Macro Score e indicadores em pesos recomendados
- Aumentar risco quando o ambiente macro é favorável
- Reduzir risco quando liquidez, crescimento ou crédito deterioram
- Distribuir dinamicamente entre ativos da carteira real
- NÃO usa tabela fixa por regime
- NÃO executa ordens
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from settings import (
    RISK_ASSETS,
    DEFENSIVE_ASSETS,
)


# ==========================================================
# HELPERS
# ==========================================================

def clamp(
    value: float,
    lower: float,
    upper: float,
) -> float:
    return float(max(lower, min(upper, value)))


def normalize_weights(
    weights: Dict[str, float],
) -> Dict[str, float]:
    total = sum(weights.values())

    if total <= 0:
        n = len(weights)
        return {
            asset: 1.0 / n
            for asset in weights
        }

    return {
        asset: weight / total
        for asset, weight in weights.items()
    }


# ==========================================================
# ORÇAMENTO DE RISCO
# ==========================================================

def calculate_risk_budget_from_regime(
    regime_result,
) -> tuple[float, float]:
    """
    Recebe regime_result vindo do engine.regime.

    Macro Score:
    - 0   = defesa máxima
    - 50  = neutro
    - 100 = risco máximo

    O score é contínuo, portanto não existe tabela fixa por regime.
    """

    risk_budget = clamp(
        regime_result.risk_budget,
        0.10,
        0.85,
    )

    defensive_budget = 1.0 - risk_budget

    return risk_budget, defensive_budget


# ==========================================================
# SCORE DOS ATIVOS DE RISCO
# ==========================================================

def score_risk_assets(
    regime_result,
) -> Dict[str, float]:
    """
    Define preferência relativa dentro dos ativos de risco.

    Ativos:
    - BTC-USD: mais sensível à liquidez e taxa real
    - VOO: ações amplas, sensível a crescimento e crédito
    - BOTZ: risco alto / crescimento secular, exige ambiente pró-risco
    - INDA: emergente/Índia, sensível a dólar, crescimento e liquidez
    """

    i = regime_result.indicators

    liquidity_power = (
        0.60 * i.liquidez_hoje
        + 0.40 * i.liquidez_t_100
    )

    growth_power = (
        0.55 * i.global_pmi
        + 0.45 * i.oecd_cli
    )

    credit_power = (
        0.60 * i.hy_spread
        + 0.40 * i.nfci
    )

    filter_power = i.filtro_composto
    real_yield_power = i.real_yield_10y

    macro_power = (regime_result.macro_score - 50.0) / 50.0

    scores = {
        "BTC-USD": (
            1.00
            + 0.55 * liquidity_power
            + 0.30 * real_yield_power
            + 0.20 * credit_power
            + 0.20 * macro_power
        ),

        "VOO": (
            1.00
            + 0.40 * growth_power
            + 0.30 * credit_power
            + 0.20 * liquidity_power
            + 0.15 * macro_power
        ),

        "BOTZ": (
            1.00
            + 0.55 * growth_power
            + 0.35 * liquidity_power
            + 0.25 * credit_power
            + 0.30 * macro_power
            + 0.20 * filter_power
        ),

        "INDA": (
            1.00
            + 0.45 * growth_power
            + 0.30 * liquidity_power
            + 0.20 * credit_power
            + 0.20 * macro_power
            + 0.25 * filter_power
        ),
    }

    # Evita peso negativo e limita concentração relativa.
    return {
        asset: clamp(score, 0.05, 3.00)
        for asset, score in scores.items()
        if asset in RISK_ASSETS
    }


# ==========================================================
# SCORE DOS ATIVOS DEFENSIVOS
# ==========================================================

def score_defensive_assets(
    regime_result,
) -> Dict[str, float]:
    """
    Define preferência relativa dentro dos ativos defensivos.

    Ativos:
    - TLT: proteção em desaceleração/queda de crescimento
    - USDT: liquidez imediata em stress
    - GLD: proteção monetária/risco sistêmico
    """

    i = regime_result.indicators

    liquidity_power = (
        0.60 * i.liquidez_hoje
        + 0.40 * i.liquidez_t_100
    )

    growth_power = (
        0.55 * i.global_pmi
        + 0.45 * i.oecd_cli
    )

    credit_power = (
        0.60 * i.hy_spread
        + 0.40 * i.nfci
    )

    filter_power = i.filtro_composto
    real_yield_power = i.real_yield_10y

    macro_power = (regime_result.macro_score - 50.0) / 50.0

    defensive_pressure = -macro_power

    scores = {
        "TLT": (
            1.00
            + 0.45 * defensive_pressure
            - 0.35 * growth_power
            - 0.25 * real_yield_power
            + 0.15 * credit_power
        ),

        "USDT": (
            1.00
            + 0.55 * defensive_pressure
            - 0.25 * credit_power
            - 0.20 * liquidity_power
            - 0.15 * filter_power
        ),

        "GLD": (
            1.00
            + 0.35 * defensive_pressure
            - 0.20 * real_yield_power
            - 0.15 * filter_power
            - 0.10 * liquidity_power
        ),
    }

    return {
        asset: clamp(score, 0.05, 3.00)
        for asset, score in scores.items()
        if asset in DEFENSIVE_ASSETS
    }


# ==========================================================
# ALOCAÇÃO DINÂMICA FINAL
# ==========================================================

def calculate_dynamic_allocation(
    regime_result,
) -> Dict[str, float]:
    """
    Função principal do allocation.py.

    Entrada:
    - regime_result gerado pelo engine.regime.calculate_regime()

    Saída:
    - dicionário com pesos recomendados por ativo

    Lógica:
    - Macro Score define quanto vai para risco e defesa
    - Indicadores individuais definem quais ativos comprar/vender
    """

    risk_budget, defensive_budget = calculate_risk_budget_from_regime(
        regime_result
    )

    risk_scores = score_risk_assets(
        regime_result
    )

    defensive_scores = score_defensive_assets(
        regime_result
    )

    risk_weights = normalize_weights(
        risk_scores
    )

    defensive_weights = normalize_weights(
        defensive_scores
    )

    allocation: Dict[str, float] = {}

    for asset, weight in risk_weights.items():
        allocation[asset] = risk_budget * weight

    for asset, weight in defensive_weights.items():
        allocation[asset] = defensive_budget * weight

    allocation = normalize_weights(
        allocation
    )

    return allocation


# ==========================================================
# AUDITORIA
# ==========================================================

def explain_allocation(
    regime_result,
    allocation: Dict[str, float],
) -> Dict[str, object]:
    """
    Retorna uma explicação auditável da alocação.
    Útil para report.py.
    """

    risk_budget, defensive_budget = calculate_risk_budget_from_regime(
        regime_result
    )

    return {
        "macro_score": regime_result.macro_score,
        "regime": regime_result.regime,
        "risk_budget": risk_budget,
        "defensive_budget": defensive_budget,
        "risk_assets": {
            asset: allocation.get(asset, 0.0)
            for asset in RISK_ASSETS
        },
        "defensive_assets": {
            asset: allocation.get(asset, 0.0)
            for asset in DEFENSIVE_ASSETS
        },
    }
