# src/risk.py
import math
import numpy as np
import backtrader as bt


class VolatilityTargetSizer(bt.Sizer):
    """
    Sizer que ajusta o tamanho da posição para atingir
    uma volatilidade alvo do portfólio (volatility targeting).

    Parâmetros principais:
    - target_vol: volatilidade anual alvo (ex: 0.10 = 10% a.a.)
    - lookback: janela de cálculo da volatilidade em dias (nº de barras)
    - annualization: fator de anualização (252 p/ diário)
    - max_leverage: limite de alavancagem (exposição máxima)
    - contract_size: multiplicador do contrato futuro (ex: 50 p/ E-mini)

    Aqui a volatilidade é estimada a partir dos retornos de
    fechamento dos últimos `lookback` candles.
    """

    params = (
        ("target_vol", 0.10),
        ("lookback", 20),
        ("annualization", 252),
        ("max_leverage", 2.0),
        ("contract_size", 50.0),
        ("min_size", 1),
    )

    def __init__(self):
        # Só pré-calculamos o fator de anualização
        self._ann_factor = math.sqrt(self.p.annualization)

    # ----------------------------------------------------------
    # helper para estimar a volatilidade anualizada
    # ----------------------------------------------------------
    def _estimate_ann_vol(self, data) -> float | None:
        """
        Estima a volatilidade anualizada com base nos últimos
        `lookback` fechamentos.

        Retorna None se não houver dados suficientes.
        """
        n = len(data)
        if n <= self.p.lookback:
            return None

        # Pegamos os últimos `lookback` preços de fechamento,
        # incluindo o atual (índice 0) e voltando pra trás.
        closes = []
        # índices de -lookback+1 até 0 (por ex.: -19, ..., 0)
        for i in range(-self.p.lookback + 1, 1):
            closes.append(float(data.close[i]))

        closes = np.array(closes, dtype=float)

        # retornos percentuais
        rets = np.diff(closes) / closes[:-1]
        if len(rets) == 0:
            return None

        daily_vol = np.nanstd(rets, ddof=1)
        if daily_vol <= 0 or np.isnan(daily_vol):
            return None

        ann_vol = daily_vol * self._ann_factor
        return ann_vol

    # ----------------------------------------------------------
    # método principal do sizer
    # ----------------------------------------------------------
    def _getsizing(self, comminfo, cash, data, isbuy):
        price = data.close[0]

        if price <= 0:
            return 0

        # estima volatilidade anualizada
        ann_vol = self._estimate_ann_vol(data)
        if ann_vol is None or ann_vol <= 0 or np.isnan(ann_vol):
            return 0

        equity = self.broker.getvalue()

        # exposição alvo ~ target_vol / vol_realizada
        raw_exposure = self.p.target_vol / ann_vol
        exposure = max(0.0, min(self.p.max_leverage, raw_exposure))

        # valor nocional alvo do portfólio
        target_notional = equity * exposure

        # cada contrato tem valor price * contract_size
        contract_notional = price * self.p.contract_size
        if contract_notional <= 0:
            return 0

        size = int(target_notional / contract_notional)

        if size < self.p.min_size:
            return 0

        return size
