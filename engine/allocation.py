%cd /content/GLOBAL_MACRO_ENGINE

code = r'''
from __future__ import annotations

from typing import Dict

from settings import RISK_ASSETS, DEFENSIVE_ASSETS
from engine.asset_models import ASSET_FACTORS


def normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    return {k: v / total for k, v in weights.items()}


def positive_score(x: float) -> float:
    return max(0.05, 1.0 + x)


def safe_get(obj, name: str, default: float = 0.0) -> float:
    try:
        return float(getattr(obj, name, default))
    except Exception:
        return default


def calculate_asset_scores(regime_result) -> Dict[str, float]:
    i = regime_result.indicators

    macro = {
        "liquidity": 0.60 * safe_get(i, "liquidez_hoje") + 0.40 * safe_get(i, "liquidez_t_100"),
        "growth": 0.55 * safe_get(i, "global_pmi") + 0.45 * safe_get(i, "oecd_cli"),
        "credit": 0.60 * safe_get(i, "hy_spread") + 0.40 * safe_get(i, "nfci"),
        "real_yield": safe_get(i, "real_yield_10y"),
        "usd": safe_get(i, "dxy_proxy", 0.0),
        "stress": safe_get(i, "vix", 0.0),
    }

    scores = {}

    for asset, factors in ASSET_FACTORS.items():
        raw = 0.0
        for factor, weight in factors.items():
            raw += macro.get(factor, 0.0) * float(weight)
        scores[asset] = positive_score(raw)

    return scores


def calculate_dynamic_allocation(regime_result) -> Dict[str, float]:
    scores = calculate_asset_scores(regime_result)

    risk_budget = float(regime_result.risk_budget)
    defensive_budget = float(regime_result.defensive_budget)

    risk_scores = {asset: scores[asset] for asset in RISK_ASSETS if asset in scores}
    defensive_scores = {asset: scores[asset] for asset in DEFENSIVE_ASSETS if asset in scores}

    risk_weights = normalize(risk_scores)
    defensive_weights = normalize(defensive_scores)

    allocation = {}

    for asset, weight in risk_weights.items():
        allocation[asset] = risk_budget * weight

    for asset, weight in defensive_weights.items():
        allocation[asset] = defensive_budget * weight

    return normalize(allocation)


def explain_allocation(regime_result, allocation: Dict[str, float]) -> str:
    scores = calculate_asset_scores(regime_result)

    lines = [
        f"Regime: {regime_result.regime}",
        f"Macro Score: {regime_result.macro_score:.2f}",
        f"Risk Budget: {regime_result.risk_budget:.2%}",
        f"Defensive Budget: {regime_result.defensive_budget:.2%}",
        "",
        "SCORES",
    ]

    for asset, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{asset}: {score:.4f}")

    lines.append("")
    lines.append("ALLOCATION")

    for asset, weight in sorted(allocation.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"{asset}: {weight:.2%}")

    return "\n".join(lines)
'''

open("engine/allocation.py", "w").write(code)

print("allocation.py substituído com sucesso")
