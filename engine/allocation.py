"""
engine/allocation.py

Alocação dinâmica baseada em orçamento de risco.

Lógica:

Macro Score
    ↓
Risk Budget
    ↓
Defensive Budget
    ↓
Distribuição interna dos grupos

Não existe peso fixo por regime.
Os indicadores definem apenas quanto risco
a carteira pode carregar.
"""

from __future__ import annotations

from typing import Dict

from settings import (
    RISK_ASSETS,
    DEFENSIVE_ASSETS,
)

# ==========================================================
# DISTRIBUIÇÃO INTERNA DOS GRUPOS
# ==========================================================

RISK_INTERNAL = {

    "BTC-USD": 0.60,

    "VOO": 0.25,

    "BOTZ": 0.10,

    "INDA": 0.05,
}

DEFENSIVE_INTERNAL = {

    "TLT": 0.40,

    "GLD": 0.35,

    "USDT": 0.25,
}


# ==========================================================
# VALIDAÇÃO
# ==========================================================

def _validate_weights(weights: Dict[str, float]) -> None:

    total = sum(weights.values())

    if abs(total - 1.0) > 0.0001:
        raise ValueError(
            f"Pesos internos inválidos. Soma={total:.4f}"
        )


_validate_weights(RISK_INTERNAL)
_validate_weights(DEFENSIVE_INTERNAL)


# ==========================================================
# ALOCAÇÃO DINÂMICA
# ==========================================================

def calculate_dynamic_allocation(
    regime_result,
) -> Dict[str, float]:

    risk_budget = float(regime_result.risk_budget)

    defensive_budget = float(
        regime_result.defensive_budget
    )

    allocation = {}

    # ------------------------
    # Grupo Risco
    # ------------------------

    for asset in RISK_ASSETS:

        internal_weight = RISK_INTERNAL.get(asset, 0)

        allocation[asset] = (
            risk_budget * internal_weight
        )

    # ------------------------
    # Grupo Defesa
    # ------------------------

    for asset in DEFENSIVE_ASSETS:

        internal_weight = DEFENSIVE_INTERNAL.get(asset, 0)

        allocation[asset] = (
            defensive_budget * internal_weight
        )

    # normalização final

    total = sum(allocation.values())

    allocation = {
        k: v / total
        for k, v in allocation.items()
    }

    return allocation


# ==========================================================
# EXPLICAÇÃO
# ==========================================================

def explain_allocation(
    regime_result,
    allocation: Dict[str, float],
) -> str:

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
    lines.append("ALOCAÇÃO RECOMENDADA")

    for asset, weight in allocation.items():

        lines.append(
            f"{asset}: {weight:.2%}"
        )

    return "\n".join(lines)
