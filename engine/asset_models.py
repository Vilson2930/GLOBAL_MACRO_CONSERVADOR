"""
engine/asset_models.py

Modelos macro estruturais dos ativos.
"""

from __future__ import annotations


ASSET_FACTORS = {

    "BTC-USD": {
        "liquidity": 0.70,
        "real_yield": -0.40,
        "credit": 0.10,
        "usd": -0.20,
    },

    "VOO": {
        "growth": 0.60,
        "credit": 0.20,
        "liquidity": 0.10,
        "real_yield": -0.10,
    },

    "BOTZ": {
        "liquidity": 0.45,
        "real_yield": -0.55,
        "growth": 0.15,
        "credit": 0.05,
    },

    # Dólar forte penaliza emergentes.
    # Dólar fraco favorece Índia.
    "INDA": {
        "growth": 0.65,
        "liquidity": 0.10,
        "credit": 0.10,
        "usd": -0.15,
    },

    "TLT": {
        "real_yield": -0.70,
        "growth": -0.20,
        "credit": 0.10,
    },

    # Ouro reage a juro real, stress e dólar.
    # Dólar forte tende a pesar contra ouro.
    "GLD": {
        "real_yield": -0.35,
        "stress": 0.35,
        "liquidity": 0.15,
        "usd": -0.15,
    },

    "USDT": {
        "stress": 0.60,
        "credit": -0.25,
        "growth": -0.15,
    },
}


ASSET_LIMITS = {
    "BTC-USD": {"min": 0.00, "max": 1.00},
    "VOO": {"min": 0.00, "max": 1.00},
    "BOTZ": {"min": 0.00, "max": 1.00},
    "INDA": {"min": 0.00, "max": 1.00},
    "TLT": {"min": 0.00, "max": 1.00},
    "GLD": {"min": 0.00, "max": 1.00},
    "USDT": {"min": 0.00, "max": 1.00},
}
