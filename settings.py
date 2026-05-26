"""
settings.py

Configuração central do GLOBAL_MACRO_ENGINE

Tudo que é parâmetro fixo do robô fica aqui.

Não colocar lógica de investimento.
Não colocar cálculos.
Não colocar rebalanceamento.

Somente configuração.
"""

from __future__ import annotations

import os
import pandas as pd

# ==========================================================
# API KEYS
# ==========================================================

FRED_API_KEY = os.getenv("FRED_API_KEY")

# ==========================================================
# URLs
# ==========================================================

FRED_BASE_URL = (
    "https://api.stlouisfed.org/fred/series/observations"
)

# ==========================================================
# LÓGICA PRINCIPAL
# ==========================================================

# Liquidez opera com atraso
LAG_LIQUIDEZ_DIAS = 100

# ==========================================================
# PESOS DOS 8 INDICADORES
# ==========================================================

INDICATOR_WEIGHTS = {

    # BLOCO LIQUIDEZ (40%)

    "liquidez_t_100": 0.20,

    "liquidez_hoje": 0.15,

    "real_yield_10y": 0.05,

    # BLOCO CRESCIMENTO (35%)

    "global_pmi": 0.20,

    "oecd_cli": 0.15,

    # BLOCO CRÉDITO (25%)

    "hy_spread": 0.15,

    "nfci": 0.10,
}

# ==========================================================
# BANDAS DE REBALANCEAMENTO
# ==========================================================

BANDA_TATICA = 0.05
BANDA_OBRIGATORIA = 0.10

# ==========================================================
# LIMITES DE CONCENTRAÇÃO
# ==========================================================

MAX_PESO_BTC = 0.40
MAX_PESO_USDT = 0.40
MAX_PESO_TLT = 0.50

# ==========================================================
# CARTEIRA REAL PADRÃO
# ==========================================================

DEFAULT_PORTFOLIO = pd.DataFrame([

    {
        "Ativo": "BTC-USD",
        "Classe": "Cripto",
        "Quantidade": 0.6020509176,
    },

    {
        "Ativo": "USDT",
        "Classe": "Caixa",
        "Quantidade": 24000.0,
    },

    {
        "Ativo": "GLD",
        "Classe": "Commodities",
        "Quantidade": 13.0,
    },

    {
        "Ativo": "VOO",
        "Classe": "ETF",
        "Quantidade": 23.0,
    },

    {
        "Ativo": "TLT",
        "Classe": "Renda_Fixa",
        "Quantidade": 130.0,
    },

    {
        "Ativo": "BOTZ",
        "Classe": "Acoes",
        "Quantidade": 10.0,
    },

    {
        "Ativo": "INDA",
        "Classe": "ETF",
        "Quantidade": 10.0,
    },
])

# ==========================================================
# ATIVOS DE RISCO
# ==========================================================

RISK_ASSETS = [

    "BTC-USD",

    "VOO",

    "BOTZ",

    "INDA",
]

# ==========================================================
# ATIVOS DEFENSIVOS
# ==========================================================

DEFENSIVE_ASSETS = [

    "TLT",

    "USDT",

    "GLD",
]

# ==========================================================
# DISTRIBUIÇÃO INTERNA
# ==========================================================

INTERNAL_WEIGHTS = {

    # risco

    "BTC-USD": 0.35,

    "VOO": 0.35,

    "BOTZ": 0.15,

    "INDA": 0.15,

    # defesa

    "TLT": 0.50,

    "USDT": 0.30,

    "GLD": 0.20,
}

# ==========================================================
# SÉRIES FRED
# ==========================================================

FRED_SERIES = {

    "real_yield_10y": "DFII10",

    "hy_spread": "BAMLH0A0HYM2",

    "nfci": "NFCI",

    "yield_curve_10y_3m": "T10Y3M",

    "dxy_proxy": "DTWEXBGS",

    "vix": "VIXCLS",

    "fed_assets": "WALCL",
}

# ==========================================================
# TICKERS YAHOO
# ==========================================================

YFINANCE_TICKERS = {

    "BTC-USD": "BTC-USD",

    "USDT": "USDT-USD",

    "GLD": "GLD",

    "VOO": "VOO",

    "TLT": "TLT",

    "BOTZ": "BOTZ",

    "INDA": "INDA",
}

# ==========================================================
# PARÂMETROS DE SCORE
# ==========================================================

BULL_THRESHOLD = 70

EXPANSAO_THRESHOLD = 55

NEUTRO_THRESHOLD = 45

DESACELERACAO_THRESHOLD = 30

# abaixo disso = STRESS

# ==========================================================
# RELATÓRIO
# ==========================================================

EXPORT_CSV = True

CSV_NAME = "rebalance_output.csv"

# ==========================================================
# DEBUG
# ==========================================================

DEBUG = False
