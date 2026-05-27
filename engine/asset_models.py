"""
engine/asset_models.py

Matriz de sensibilidade macro por ativo.
Cada ativo reage de forma diferente a liquidez,
crescimento, crédito, taxa real, dólar e stress.
"""

from __future__ import annotations


ASSET_FACTORS = {
    "BTC-USD": {
        "liquidity": 0.45,
        "real_yield": -0.25,
        "credit": 0.15,
        "usd": -0.15,
    },

    "VOO": {
        "growth": 0.40,
        "credit": 0.25,
        "liquidity": 0.20,
        "real_yield": -0.15,
    },

    "BOTZ": {
        "liquidity": 0.35,
        "real_yield": -0.35,
        "growth": 0.20,
        "credit": 0.10,
    },

    "INDA": {
        "growth": 0.50,
        "liquidity": 0.20,
        "credit": 0.15,
        "usd": -0.15,
    },

    "TLT": {
        "real_yield": -0.50,
        "growth": -0.25,
        "credit": 0.15,
        "liquidity": 0.10,
    },

    "GLD": {
        "real_yield": -0.45,
        "liquidity": 0.25,
        "stress": 0.20,
        "credit": 0.10,
    },

    "USDT": {
        "stress": 0.40,
        "credit": -0.25,
        "liquidity": -0.20,
        "growth": -0.15,
    },
}


ASSET_LIMITS = {
    "BTC-USD": {"min": 0.00, "max": 0.35},
    "VOO": {"min": 0.05, "max": 0.45},
    "BOTZ": {"min": 0.00, "max": 0.15},
    "INDA": {"min": 0.00, "max": 0.15},
    "TLT": {"min": 0.00, "max": 0.45},
    "GLD": {"min": 0.00, "max": 0.35},
    "USDT": {"min": 0.05, "max": 0.40},
}
