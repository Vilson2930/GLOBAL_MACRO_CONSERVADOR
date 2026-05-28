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

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def get_fred_api_key() -> str:
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


FRED_SERIES = {
    "real_yield_10y": "DFII10",
    "hy_spread": "BAMLH0A0HYM2",
    "nfci": "NFCI",
    "yield_curve_10y_3m": "T10Y3M",
    "dxy_proxy": "DTWEXBGS",
    "vix": "VIXCLS",
    "fed_assets": "WALCL",
}


DEFAULT_PORTFOLIO = pd.DataFrame([
    {"Ativo": "BTC-USD", "Classe": "Cripto", "Quantidade": 0.6020509176},
    {"Ativo": "USDT", "Classe": "Caixa", "Quantidade": 24000.0},
    {"Ativo": "GLD", "Classe": "Commodities", "Quantidade": 13.0},
    {"Ativo": "VOO", "Classe": "ETF", "Quantidade": 23.0},
    {"Ativo": "TLT", "Classe": "Renda_Fixa", "Quantidade": 130.0},
    {"Ativo": "BOTZ", "Classe": "Acoes", "Quantidade": 10.0},
    {"Ativo": "INDA", "Classe": "ETF", "Quantidade": 10.0},
])


YFINANCE_TICKERS = {
    "BTC-USD": "BTC-USD",
    "USDT": "USDT-USD",
    "GLD": "GLD",
    "VOO": "VOO",
    "TLT": "TLT",
    "BOTZ": "BOTZ",
    "INDA": "INDA",
}


def fetch_fred_series(series_id: str, start_date: str = "2010-01-01") -> pd.Series:
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
    }

    response = requests.get(FRED_BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    observations = response.json().get("observations", [])
    df = pd.DataFrame(observations)

    if df.empty:
        raise ValueError(f"Série FRED vazia: {series_id}")

    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"].replace(".", np.nan), errors="coerce")
    df = df.dropna(subset=["value"])

    return df.set_index("date")["value"].sort_index()


def fetch_all_fred() -> Dict[str, pd.Series]:
    output = {}

    for name, series_id in FRED_SERIES.items():
        print(f"Buscando FRED: {name} ({series_id})")
        output[name] = fetch_fred_series(series_id)

    return output


def test_fred() -> None:
    print("Testando FRED...")
    series = fetch_fred_series("DFII10")
    print(series.tail())
    print("FRED OK")


def _extract_close(data) -> float:
    if data is None or len(data) == 0:
        return np.nan

    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = close.dropna()

    if close.empty:
        return np.nan

    return float(close.iloc[-1])


def _price_from_yfinance_download(ticker: str) -> float:
    if yf is None:
        return np.nan

    data = yf.download(
        ticker,
        period="10d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    return _extract_close(data)


def _price_from_yfinance_ticker(ticker: str) -> float:
    if yf is None:
        return np.nan

    obj = yf.Ticker(ticker)

    try:
        fast_price = obj.fast_info.get("last_price")
        if fast_price is not None and fast_price > 0:
            return float(fast_price)
    except Exception:
        pass

    data = obj.history(
        period="10d",
        interval="1d",
        auto_adjust=True,
    )

    return _extract_close(data)


def _price_from_yahoo_chart(ticker: str) -> float:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

    params = {
        "range": "10d",
        "interval": "1d",
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    result = data.get("chart", {}).get("result", [])

    if not result:
        return np.nan

    quote = result[0].get("indicators", {}).get("quote", [])

    if not quote:
        return np.nan

    closes = quote[0].get("close", [])

    valid = [
        x for x in closes
        if x is not None and not pd.isna(x) and float(x) > 0
    ]

    if not valid:
        return np.nan

    return float(valid[-1])


def get_latest_price(asset: str) -> float:
    asset = str(asset).upper().strip()

    if asset == "USDT":
        return 1.0

    ticker = YFINANCE_TICKERS.get(asset, asset)

    methods = [
        _price_from_yfinance_download,
        _price_from_yfinance_ticker,
        _price_from_yahoo_chart,
    ]

    for method in methods:
        try:
            price = method(ticker)

            if price is not None and not pd.isna(price) and float(price) > 0:
                return float(price)

        except Exception:
            continue

    return np.nan


def get_prices_yfinance(assets: List[str]) -> Dict[str, float]:
    prices = {}

    for asset in assets:
        prices[asset] = get_latest_price(asset)

    missing = [
        asset for asset, price in prices.items()
        if pd.isna(price) or price <= 0
    ]

    if missing:
        print(f"AVISO: preço não encontrado para {missing}. Valor tratado como 0.")

    return prices


def load_portfolio(path: str = "portfolio.csv") -> pd.DataFrame:
    if os.path.exists(path):
        df = pd.read_csv(path)
    else:
        df = DEFAULT_PORTFOLIO.copy()

    required = {"Ativo", "Classe", "Quantidade"}

    if not required.issubset(df.columns):
        raise ValueError("portfolio.csv inválido")

    df["Ativo"] = df["Ativo"].astype(str).str.upper().str.strip()
    df["Classe"] = df["Classe"].astype(str).str.strip()
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce")

    return df.dropna(subset=["Quantidade"])


def get_latest_value(
    series: pd.Series,
    date: Optional[pd.Timestamp] = None,
) -> float:
    if date is None:
        date = pd.Timestamp.today()

    valid = series.loc[series.index <= date].dropna()

    if valid.empty:
        raise ValueError("Sem dado disponível")

    return float(valid.iloc[-1])
