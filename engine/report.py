"""
engine/report.py

Relatório e exportação do GLOBAL_MACRO_ENGINE.
- Gera relatório consolidado
- Exporta CSV
- Envia para Google Sheets quando configurado
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Optional

import pandas as pd


def build_report_dataframe(
    rebalance: pd.DataFrame,
    regime_result,
    allocation: Dict[str, float],
) -> pd.DataFrame:
    df = rebalance.copy()

    df["Macro_Score"] = regime_result.macro_score
    df["Regime"] = regime_result.regime
    df["Risk_Budget"] = regime_result.risk_budget
    df["Defensive_Budget"] = regime_result.defensive_budget
    df["Data_UTC"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    return df


def save_csv(
    report_df: pd.DataFrame,
    path: str = "rebalance_output.csv",
) -> str:
    report_df.to_csv(path, index=False)
    return path


def print_report(
    regime_result,
    allocation: Dict[str, float],
    rebalance: pd.DataFrame,
) -> None:
    print("\n" + "=" * 100)
    print("GLOBAL_MACRO_ENGINE — RELATÓRIO")
    print("=" * 100)

    print(f"Data UTC: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Macro Score: {regime_result.macro_score:.2f}")
    print(f"Regime: {regime_result.regime}")
    print(f"Risk Budget: {regime_result.risk_budget:.2%}")
    print(f"Defensive Budget: {regime_result.defensive_budget:.2%}")

    print("\nPESOS RECOMENDADOS")
    for asset, weight in allocation.items():
        print(f"{asset}: {weight:.2%}")

    print("\nREBALANCEAMENTO")
    print(rebalance.to_string(index=False))

    print("=" * 100)


def send_to_google_sheets(
    report_df: pd.DataFrame,
    spreadsheet_id: Optional[str] = None,
    worksheet_name: str = "rebalance_output",
    credentials_path: Optional[str] = None,
) -> None:
    """
    Envia o DataFrame para Google Sheets.

    Requisitos:
        pip install gspread google-auth

    Configuração recomendada:
        GOOGLE_SHEET_ID=seu_id_da_planilha
        GOOGLE_APPLICATION_CREDENTIALS=service_account.json
    """

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        raise ImportError(
            "Instale dependências: pip install gspread google-auth"
        ) from exc

    spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEET_ID")
    credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not spreadsheet_id:
        raise ValueError("GOOGLE_SHEET_ID não configurado.")

    if not credentials_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS não configurado.")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(
        credentials_path,
        scopes=scopes,
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=1000,
            cols=50,
        )

    worksheet.clear()

    clean_df = report_df.copy()
    clean_df = clean_df.replace([float("inf"), float("-inf")], None)
    clean_df = clean_df.where(pd.notnull(clean_df), None)

    values = [
        clean_df.columns.tolist()
    ] + clean_df.astype(str).values.tolist()

    worksheet.update(values)


def generate_report(
    regime_result,
    allocation: Dict[str, float],
    rebalance: pd.DataFrame,
    export_csv: bool = True,
    csv_path: str = "rebalance_output.csv",
    export_sheets: bool = False,
    spreadsheet_id: Optional[str] = None,
    worksheet_name: str = "rebalance_output",
    credentials_path: Optional[str] = None,
) -> pd.DataFrame:
    report_df = build_report_dataframe(
        rebalance=rebalance,
        regime_result=regime_result,
        allocation=allocation,
    )

    print_report(
        regime_result=regime_result,
        allocation=allocation,
        rebalance=rebalance,
    )

    if export_csv:
        save_csv(report_df, csv_path)
        print(f"\nCSV gerado: {csv_path}")

    if export_sheets:
        send_to_google_sheets(
            report_df=report_df,
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            credentials_path=credentials_path,
        )
        print("Google Sheets atualizado com sucesso.")

    return report_df
