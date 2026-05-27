"""
engine/risk.py

Módulo de risco e rebalanceamento do GLOBAL_MACRO_ENGINE.

Responsável por:
- Calcular valor atual da carteira
- Calcular peso atual por ativo
- Comparar peso atual vs peso recomendado pelos indicadores
- Gerar sugestão de COMPRAR / VENDER / MANTER
- NÃO usa tabela fixa por regime
- NÃO executa ordens
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def calculate_portfolio_values(
    portfolio: pd.DataFrame,
    prices: Dict[str, float],
) -> pd.DataFrame:
    df = portfolio.copy()

    df["Ativo"] = (
        df["Ativo"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["Preco"] = df["Ativo"].map(prices)

    missing = df[df["Preco"].isna()]["Ativo"].tolist()

    if missing:
        print(f"AVISO: preço não encontrado para {missing}. Valor tratado como 0.")
        df["Preco"] = df["Preco"].fillna(0.0)

    df["Valor_USD"] = df["Quantidade"] * df["Preco"]

    total = df["Valor_USD"].sum()

    if total <= 0:
        raise ValueError("Valor total da carteira é zero. Verifique preços e quantidades.")

    df["Peso_Atual"] = df["Valor_USD"] / total

    return df


def generate_rebalance_table(
    portfolio_values: pd.DataFrame,
    recommended_weights: Dict[str, float],
) -> pd.DataFrame:
    df = portfolio_values.copy()

    total = df["Valor_USD"].sum()

    df["Peso_Recomendado"] = (
        df["Ativo"]
        .map(recommended_weights)
        .fillna(0.0)
    )

    df["Valor_Recomendado_USD"] = df["Peso_Recomendado"] * total

    df["Diferenca_USD"] = (
        df["Valor_Recomendado_USD"] - df["Valor_USD"]
    )

    df["Diferenca_Peso"] = (
        df["Peso_Recomendado"] - df["Peso_Atual"]
    )

    def action(value: float) -> str:
        if value > 0:
            return "COMPRAR"
        if value < 0:
            return "VENDER"
        return "MANTER"

    df["Acao"] = df["Diferenca_USD"].apply(action)

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
    risk_assets: list[str],
    defensive_assets: list[str],
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
