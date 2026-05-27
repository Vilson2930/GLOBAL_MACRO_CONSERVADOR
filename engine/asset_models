"""
engine/asset_models.py

Modelos macro estruturais dos ativos.

Cada ativo possui sensibilidades diferentes
a crescimento, liquidez, crédito, juros reais,
dólar e stress financeiro.

Não há teto máximo artificial.
O peso final será consequência do regime macro.
"""

from __future__ import annotations


# ============================================================
# FATORES MACRO POR ATIVO
# ============================================================

ASSET_FACTORS = {

    # ========================================================
    # BITCOIN
    # Principal beneficiário de liquidez global
    # ========================================================
    "BTC-USD": {
        "liquidity": 0.70,
        "real_yield": -0.40,
        "credit": 0.10,
        "usd": -0.20,
    },

    # ========================================================
    # S&P500
    # Crescimento econômico global
    # ========================================================
    "VOO": {
        "growth": 0.60,
        "credit": 0.20,
        "liquidity": 0.10,
        "real_yield": -0.10,
    },

    # ========================================================
    # IA / ROBÓTICA
    # Muito sensível a liquidez e juros reais
    # ========================================================
    "BOTZ": {
        "liquidity": 0.45,
        "real_yield": -0.55,
        "growth": 0.15,
        "credit": 0.05,
    },

    # ========================================================
    # ÍNDIA
    # Aposta de crescimento emergente
    # ========================================================
    "INDA": {
        "growth": 0.70,
        "liquidity": 0.10,
        "credit": 0.10,
        "usd": -0.10,
    },

    # ========================================================
    # TREASURY LONGO
    # Beneficia desaceleração e queda de juros reais
    # ========================================================
    "TLT": {
        "real_yield": -0.70,
        "growth": -0.20,
        "credit": 0.10,
    },

    # ========================================================
    # OURO
    # Hedge monetário e stress sistêmico
    # ========================================================
    "GLD": {
        "real_yield": -0.40,
        "stress": 0.40,
        "liquidity": 0.15,
        "credit": 0.05,
    },

    # ========================================================
    # CAIXA
    # Reserva para crises
    # ========================================================
    "USDT": {
        "stress": 0.60,
        "credit": -0.25,
        "growth": -0.15,
    },
}


# ============================================================
# LIMITES
# ============================================================
#
# Sem teto máximo.
# O regime macro decide.
#
# ============================================================

ASSET_LIMITS = {
    "BTC-USD": {"min": 0.00, "max": 1.00},
    "VOO": {"min": 0.00, "max": 1.00},
    "BOTZ": {"min": 0.00, "max": 1.00},
    "INDA": {"min": 0.00, "max": 1.00},
    "TLT": {"min": 0.00, "max": 1.00},
    "GLD": {"min": 0.00, "max": 1.00},
    "USDT": {"min": 0.00, "max": 1.00},
}
