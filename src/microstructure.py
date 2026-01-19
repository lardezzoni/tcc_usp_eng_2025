# src/microstructure.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import backtrader as bt


@dataclass
class MicrostructureConfig:
    """
    Parâmetros simples de controle de microestrutura.

    - min_volume_pct_avg: volume mínimo como % da média de 20 dias
      (ex: 0.3 → só trade se volume >= 30% da média)
    - max_spread_pct: spread máximo aceitável (se você tiver estimativa diária)
    - min_holding_period: nº mínimo de barras entre trocas de posição
      (evita churn microestrutural)
    """
    min_volume_pct_avg: float = 0.3
    max_spread_pct: Optional[float] = None
    min_holding_period: int = 1


class MicrostructureStrategy(bt.Strategy):
    """
    Estratégia base com filtros de microestrutura.

    A idéia é você herdar desta classe:

        class EnhancedSmaCross(MicrostructureStrategy):
            ...

    e chamar `super().next()` no começo do seu `next()`.
    """

    params = (
        ("micro_cfg", MicrostructureConfig()),
    )

    def __init__(self):
        self.vol_ma = bt.indicators.SimpleMovingAverage(self.data.volume, period=20)
        self._bars_since_trade = 0


    def notify_trade(self, trade):
        if trade.isclosed:
            self._bars_since_trade = 0

    def next(self):
        self._bars_since_trade += 1

    def _liquidity_ok(self) -> bool:
        """
        True se o volume atual é razoável comparado à média de volume.
        """
        if self.vol_ma[0] == 0:
            return False

        vol_ratio = self.data.volume[0] / self.vol_ma[0]
        return vol_ratio >= self.p.micro_cfg.min_volume_pct_avg

    def _holding_period_ok(self) -> bool:
        """
        True se já passou o mínimo de barras desde a última troca de posição.
        """
        return self._bars_since_trade >= self.p.micro_cfg.min_holding_period

    def _spread_ok(self) -> bool:
        """
        Se você tiver um indicador de spread por barra, pode checar aqui.

        Por enquanto, apenas respeita max_spread_pct se você
        criar um atributo `self.spread_indicator` na sua estratégia filha.
        """
        if self.p.micro_cfg.max_spread_pct is None:
            return True

        if not hasattr(self, "spread_indicator"):
           
            return True

        current_spread = float(self.spread_indicator[0])
        return current_spread <= self.p.micro_cfg.max_spread_pct

    def micro_ok(self) -> bool:
        """
        Condição completa de microestrutura:
        só trade se todos os filtros forem satisfeitos.
        """
        return self._liquidity_ok() and self._holding_period_ok() and self._spread_ok()
