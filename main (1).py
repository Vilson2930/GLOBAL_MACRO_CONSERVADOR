"""
main.py
Orquestrador oficial do GLOBAL_MACRO_ENGINE.
"""

from __future__ import annotations

import os
import getpass

from market_data import (
    test_fred,
    fetch_all_fred,
    load_portfolio,
    get_prices_yfinance,
)

from engine.regime import calculate_regime
from engine.allocation import calculate_dynamic_allocation
from engine.risk import calculate_portfolio_values, generate_rebalance_table
from engine.report import generate_report


def ensure_fred_key() -> None:
    if not os.getenv("FRED_API_KEY"):
        key = getpass.getpass("Digite sua FRED_API_KEY: ")
        os.environ["FRED_API_KEY"] = key


def main() -> None:
    ensure_fred_key()

    test_fred()

    fred = fetch_all_fred()

    regime = calculate_regime(fred)

    allocation = calculate_dynamic_allocation(regime)

    portfolio = load_portfolio()

    prices = get_prices_yfinance(
        portfolio["Ativo"].tolist()
    )

    values = calculate_portfolio_values(
        portfolio=portfolio,
        prices=prices,
    )

    rebalance = generate_rebalance_table(
        portfolio_values=values,
        recommended_weights=allocation,
    )

    report_df = generate_report(
        regime_result=regime,
        allocation=allocation,
        rebalance=rebalance,
        export_csv=True,
        export_sheets=False,
    )

    print("\nCHECK FINAL")
    print("Soma pesos recomendados:", round(sum(allocation.values()), 6))
    print("Soma diferença USD:", round(rebalance["Diferenca_USD"].sum(), 2))
    print("Valor carteira:", round(rebalance["Valor_USD"].sum(), 2))
    print("Valor recomendado:", round(rebalance["Valor_Recomendado_USD"].sum(), 2))
    print("NaN:", rebalance.isna().sum().sum())


if __name__ == "__main__":
    main()
