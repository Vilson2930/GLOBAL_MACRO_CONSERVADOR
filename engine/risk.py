"""
engine/risk.py

Motor de auditoria e rebalanceamento do GLOBAL_MACRO_ENGINE.

Responsável por:

- Calcular valor total da carteira
- Calcular pesos atuais
- Comparar pesos atuais vs pesos-alvo
- Gerar tabela de rebalanceamento
- Informar compra/venda necessária
"""

from __future__ import annotations

from typing import Dict


# ==========================================================
# VALOR TOTAL DA CARTEIRA
# ==========================================================

def calculate_portfolio_values(
    positions: Dict[str, float],
    prices: Dict[str, float],
) -> Dict[str, float]:
    """
    positions:
        {
            "BTC-USD": 0.5,
            "VOO": 10
        }

    prices:
        {
            "BTC-USD": 70000,
            "VOO": 550
        }

    retorno:
        {
            "BTC-USD": 35000,
            "VOO": 5500
        }
    """

    values = {}

    for asset, quantity in positions.items():

        price = prices.get(asset, 0)

        values[asset] = quantity * price

    return values


# ==========================================================
# VALOR TOTAL
# ==========================================================

def calculate_total_value(
    values: Dict[str, float]
) -> float:

    return float(sum(values.values()))


# ==========================================================
# PESOS ATUAIS
# ==========================================================

def calculate_current_weights(
    values: Dict[str, float]
) -> Dict[str, float]:

    total = calculate_total_value(values)

    if total <= 0:
        return {}

    return {
        asset: value / total
        for asset, value in values.items()
    }


# ==========================================================
# DESVIO
# ==========================================================

def calculate_weight_difference(
    current_weights: Dict[str, float],
    target_weights: Dict[str, float]
) -> Dict[str, float]:

    assets = (
        set(current_weights.keys())
        | set(target_weights.keys())
    )

    diff = {}

    for asset in assets:

        current = current_weights.get(asset, 0)

        target = target_weights.get(asset, 0)

        diff[asset] = target - current

    return diff


# ==========================================================
# REBALANCEAMENTO
# ==========================================================

def generate_rebalance_table(
    values: Dict[str, float],
    target_weights: Dict[str, float]
) -> Dict[str, Dict]:

    total = calculate_total_value(values)

    current_weights = calculate_current_weights(values)

    rebalance = {}

    assets = (
        set(values.keys())
        | set(target_weights.keys())
    )

    for asset in assets:

        current_value = values.get(asset, 0)

        current_weight = current_weights.get(asset, 0)

        target_weight = target_weights.get(asset, 0)

        target_value = total * target_weight

        delta_value = target_value - current_value

        if delta_value > 0:
            action = "BUY"

        elif delta_value < 0:
            action = "SELL"

        else:
            action = "HOLD"

        rebalance[asset] = {
            "current_value": round(current_value, 2),
            "current_weight": round(current_weight * 100, 2),
            "target_weight": round(target_weight * 100, 2),
            "target_value": round(target_value, 2),
            "delta_value": round(delta_value, 2),
            "action": action,
        }

    return rebalance


# ==========================================================
# AUDITORIA
# ==========================================================

def portfolio_risk_report(
    values: Dict[str, float],
    target_weights: Dict[str, float]
) -> Dict:

    total = calculate_total_value(values)

    current_weights = calculate_current_weights(values)

    diff = calculate_weight_difference(
        current_weights,
        target_weights
    )

    return {
        "total_value": round(total, 2),
        "current_weights": current_weights,
        "target_weights": target_weights,
        "difference": diff,
    }
