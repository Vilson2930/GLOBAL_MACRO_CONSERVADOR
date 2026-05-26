"""
market_data.py

Responsável por:

- Ler chave FRED
- Buscar séries macro no FRED
- Buscar preços Yahoo Finance
- Carregar carteira
- Entregar dados para engine.regime
- Entregar preços para engine.risk
"""

from __future__ import annotations

import os
import warnings
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import requests

try:
    import yfinance as yf
except ImportError:
    yf = None

warnings.filterwarnings("ignore")

# ==========================================================
# FRED
# ==========================================================

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_fred_api_key() -> str:
    """
    Ordem de busca:

    1) variável ambiente
    2) Colab Secrets
    3) input manual
    """

    key = os.getenv("FRED_API_KEY")

    if key:
        return key

    try:
        from google.colab import userdata

        key = userdata.get("FRED_API_KEY")

        if key:
            return key

    except Exception:
        pass

    key = input("Digite sua FRED_API_KEY: ").strip()

    if not key:
        raise RuntimeError("FRED_API_KEY não fornecida.")

    return key


FRED_API_KEY = get_fred_api_key()


# ==========================================================
# SÉRIES FRED
# ==========================================================

FRED_SERIES = {

    # Taxa real 10 anos
    "real_yield_10y": "DFII10",

    # High Yield Spread
    "hy_spread": "BAMLH0A0HYM2",

    # Financial Conditions Index
    "nfci": "NFCI",

    # Curva
    "yield_curve_10y_3m": "T10Y3M",

    # Dollar Index amplo
    "dxy_proxy": "DTWEXBGS",

    # VIX
    "vix": "VIXCLS",

    # Fed Balance Sheet
    "fed_assets": "WALCL",
}


# ==========================================================
# CARTEIRA REAL
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
# TICKERS
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
# FRED FETCH
# ==========================================================

def fetch_fred_series(
    series_id: str,
    start_date: str = "2010-01-01",
) -> pd.Series:

    params = {

        "series_id": series_id,

        "api_key": FRED_API_KEY,

        "file_type": "json",

        "observation_start": start_date,
    }

    response = requests.get(
        FRED_BASE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    observations = response.json().get(
        "observations",
        [],
    )

    df = pd.DataFrame(observations)

    if df.empty:
        raise ValueError(
            f"Série FRED vazia: {series_id}"
        )

    df["date"] = pd.to_datetime(
        df["date"]
    )

    df["value"] = pd.to_numeric(
        df["value"].replace(
            ".",
            np.nan,
        ),
        errors="coerce",
    )

    df = df.dropna(
        subset=["value"]
    )

    return (
        df
        .set_index("date")["value"]
        .sort_index()
    )


# ==========================================================
# BAIXAR TODAS AS SÉRIES
# ==========================================================

def fetch_all_fred() -> Dict[str, pd.Series]:

    output = {}

    for name, series_id in FRED_SERIES.items():

        print(
            f"Buscando FRED: {name} ({series_id})"
        )

        output[name] = fetch_fred_series(
            series_id
        )

    return output


# ==========================================================
# TESTE FRED
# ==========================================================

def test_fred() -> None:

    print("Testando FRED...")

    series = fetch_fred_series(
        "DFII10"
    )

    print(series.tail())

    print("FRED OK")


# ==========================================================
# PREÇOS YAHOO
# ==========================================================

def get_prices_yfinance(
    assets: List[str]
) -> Dict[str, float]:

    if yf is None:

        raise ImportError(
            "Instale yfinance."
        )

    prices = {}

    for asset in assets:

        if asset == "USDT":

            prices[asset] = 1.0

            continue

        ticker = YFINANCE_TICKERS.get(
            asset
        )

        if ticker is None:

            prices[asset] = np.nan

            continue

        try:

            data = yf.download(
                ticker,
                period="10d",
                auto_adjust=True,
                progress=False,
            )

            if data.empty:

                prices[asset] = np.nan

            else:

                prices[asset] = float(
                    data["Close"]
                    .dropna()
                    .iloc[-1]
                )

        except Exception:

            prices[asset] = np.nan

    return prices


# ==========================================================
# CARTEIRA
# ==========================================================

def load_portfolio(
    path: str = "portfolio.csv",
) -> pd.DataFrame:

    if os.path.exists(path):

        df = pd.read_csv(path)

    else:

        df = DEFAULT_PORTFOLIO.copy()

    required = {
        "Ativo",
        "Classe",
        "Quantidade",
    }

    if not required.issubset(
        df.columns
    ):

        raise ValueError(
            "portfolio.csv inválido"
        )

    df["Ativo"] = (
        df["Ativo"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["Quantidade"] = pd.to_numeric(
        df["Quantidade"],
        errors="coerce",
    )

    return df.dropna(
        subset=["Quantidade"]
    )


# ==========================================================
# ÚLTIMO VALOR
# ==========================================================

def get_latest_value(
    series: pd.Series,
    date: Optional[pd.Timestamp] = None,
) -> float:

    if date is None:
        date = pd.Timestamp.today()

    valid = series.loc[
        series.index <= date
    ]

    if valid.empty:

        raise ValueError(
            "Sem dado disponível"
        )

    return float(
        valid.iloc[-1]
    )
