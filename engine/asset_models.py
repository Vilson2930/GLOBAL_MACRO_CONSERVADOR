"""
engine/asset_models.py

Matriz de sensibilidade macro por ativo.
Cada ativo reage de forma diferente a liquidez,
crescimento, crédito, taxa real, dólar e stress.
"""

from __future__ import annotations


ASSET_FACTORS = {

    "BTC-USD": {
        "liquidity": 0.55,
        "real_yield": -0.25,
        "credit": 0.10,
        "usd": -0.10,
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
        "growth": 0.35,
        "liquidity": 0.15,
        "credit": 0.20,
        "usd": -0.30,
    },

    "TLT": {
        "real_yield": -0.50,
        "growth": -0.25,
        "credit": 0.15,
        "liquidity": -0.05,
    },

    "GLD": {
        "real_yield": -0.45,
        "usd": -0.25,
        "stress": 0.15,
        "credit": 0.10,
        "liquidity": 0.05,
    },

    "USDT": {
        "stress": 0.40,
        "credit": -0.25,
        "liquidity": -0.20,
        "growth": -0.15,
    },
}


ASSET_LIMITS = {

    "BTC-USD": {
        "min": 0.00,
        "max": 0.35,
    },

    "VOO": {
        "min": 0.05,
        "max": 0.45,
    },

    "BOTZ": {
        "min": 0.00,
        "max": 0.10,
    },

    "INDA": {
        "min": 0.00,
        "max": 0.10,
    },

    "TLT": {
        "min": 0.00,
        "max": 0.45,
    },

    "GLD": {
        "min": 0.00,
        "max": 0.35,
    },

    "USDT": {
        "min": 0.05,
        "max": 0.40,
    },
}
