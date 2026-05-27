"""
engine/risk.py
Compatível com DataFrame vindo de market_data.load_portfolio().
"""

from __future__ import annotations

from typing import Dict, List
import numpy as np
import pandas as pd


def _to_float_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _to_float_value(x) -> float:
    try:
        if isinstance(x, pd.Series):
            x = x.dropna().iloc[-1]
        return float(str(x).replace(",", "."))
    except Exception:
        return np.nan


def calculate_portfolio_values(
    portfolio: pd.DataFrame,
    prices: Dict[str, float],
) -> pd.DataFrame:
    df = portfolio.copy()

    df["Ativo"] = df["Ativo"].astype(str).str.upper().str.strip()
    df["Classe"] = df["Classe"].astype(str).str.strip()
    df["Quantidade"] = _to_float_series(df["Quantidade"])

    clean_prices = {
        str(k).upper().strip(): _to_float_value(v)
        for k, v in prices.items()
    }

    df["Preco"] = df["Ativo"].map(clean_prices)
    df["Preco"] = _to_float_series(df["Preco"])

    missing = df[df["Preco"].isna()]["Ativo"].tolist()
    if missing:
        print(f"AVISO: preço não encontrado para {missing}. Valor tratado como 0.")
        df["Preco"] = df["Preco"].fillna(0.0)

    df["Quantidade"] = df["Quantidade"].fillna(0.0)
    df["Valor_USD"] = df["Quantidade"] * df["Preco"]

    total = float(pd.to_numeric(df["Valor_USD"], errors="coerce").fillna(0).sum())

    if total <= 0:
        raise ValueError("Valor total da carteira é zero. Verifique preços e quantidades.")

    df["Peso_Atual"] = df["Valor_USD"] / total

    return df


def generate_rebalance_table(
    portfolio_values: pd.DataFrame,
    recommended_weights: Dict[str, float],
) -> pd.DataFrame:
    df = portfolio_values.copy()

    clean_weights = {
        str(k).upper().strip(): _to_float_value(v)
        for k, v in recommended_weights.items()
    }

    total = float(pd.to_numeric(df["Valor_USD"], errors="coerce").fillna(0).sum())

    df["Peso_Recomendado"] = df["Ativo"].map(clean_weights).fillna(0.0)
    df["Valor_Recomendado_USD"] = df["Peso_Recomendado"] * total
    df["Diferenca_USD"] = df["Valor_Recomendado_USD"] - df["Valor_USD"]
    df["Diferenca_Peso"] = df["Peso_Recomendado"] - df["Peso_Atual"]

    df["Acao"] = np.where(
        df["Diferenca_USD"] > 0,
        "COMPRAR",
        np.where(df["Diferenca_USD"] < 0, "VENDER", "MANTER"),
    )

    return df[
        [
            "Ativo",
            "Classe",
            "Quantidade",
            "Preco",
            "Valor_USD",
            "Peso_Atual",
            "Peso_Recomendado",
            "Valor_Recomendado_USD",
            "Diferenca_Peso",
            "Diferenca_USD",
            "Acao",
        ]
    ].sort_values("Diferenca_USD", ascending=False)


def calculate_risk_summary(
    rebalance: pd.DataFrame,
    risk_assets: List[str],
    defensive_assets: List[str],
) -> Dict[str, float]:
    current_risk = rebalance.loc[
        rebalance["Ativo"].isin(risk_assets),
        "Peso_Atual",
    ].sum()

    recommended_risk = rebalance.loc[
        rebalance["Ativo"].isin(risk_assets),
        "Peso_Recomendado",
    ].sum()

    current_defensive = rebalance.loc[
        rebalance["Ativo"].isin(defensive_assets),
        "Peso_Atual",
    ].sum()

    recommended_defensive = rebalance.loc[
        rebalance["Ativo"].isin(defensive_assets),
        "Peso_Recomendado",
    ].sum()

    return {
        "current_risk": float(current_risk),
        "recommended_risk": float(recommended_risk),
        "current_defensive": float(current_defensive),
        "recommended_defensive": float(recommended_defensive),
        "risk_delta": float(recommended_risk - current_risk),
        "defensive_delta": float(recommended_defensive - current_defensive),
    }
