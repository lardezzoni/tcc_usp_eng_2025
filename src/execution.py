# src/execution.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class ExecutionParams:
    """
    Parâmetros de execução calibrados a partir do spread estimado.

    - mean_spread_pct: spread médio (%) baseado em High/Low
    - half_spread_pct: metade do spread (assumindo bid/ask simétricos)
    - slippage_perc: slippage padrão a ser passado para o broker do Backtrader
    - commission_perc: comissão percentual (se quiser incluir corretagem)
    """
    mean_spread_pct: float
    half_spread_pct: float
    slippage_perc: float
    commission_perc: float = 0.0


def estimate_highlow_spread(
    df: pd.DataFrame,
    high_col: str = "High",
    low_col: str = "Low",
) -> pd.Series:
    """
    Estimador simples de spread percentual baseado no range diário:

        spread_t = (H_t - L_t) / ((H_t + L_t) / 2)

    OBS:
    - Isso é um *proxy* bem simples.
    - Vantagem: fácil de implementar.
    - Depois você pode substituir por um estimador mais sofisticado
      (ex: Corwin & Schultz) mantendo a mesma assinatura.
    """
    h = df[high_col].astype(float)
    l = df[low_col].astype(float)

    avg = (h + l) / 2.0
    spread = (h - l) / avg
    spread = spread.replace([np.inf, -np.inf], np.nan)
    return spread


def calibrate_execution_params(
    df: pd.DataFrame,
    high_col: str = "High",
    low_col: str = "Low",
    commission_perc: float = 0.0,
    slippage_multiplier: float = 0.5,
) -> ExecutionParams:
    """
    1. Estima o spread percentual médio a partir do range High/Low.
    2. Define um slippage percentual consistente com esse spread.

    - slippage_multiplier: fração do half-spread (ex: 0.5 → metade do half-spread).
    """
    spread_series = estimate_highlow_spread(df, high_col=high_col, low_col=low_col)
    mean_spread = float(spread_series.dropna().mean())

    # meio-spread: buy no ask, sell no bid
    half_spread = mean_spread / 2.0

    # slippage efetivo (pode ser mais conservador, ex: 1.0 * half_spread)
    slippage_perc = half_spread * slippage_multiplier

    return ExecutionParams(
        mean_spread_pct=mean_spread,
        half_spread_pct=half_spread,
        slippage_perc=slippage_perc,
        commission_perc=commission_perc,
    )
