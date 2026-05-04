"""
Etapa 1 — Calibração final (risco, execução, microestrutura)

Como usar:
  1) Coloque este arquivo na raiz do projeto (mesma pasta de enchanced_bot.py).
  2) Garanta que o dataset exista (default: data/MES_2023.csv).
  3) Rode:
        python calibrate_step1.py
     ou:
        python calibrate_step1.py --data data/MES_2023.csv --cash 100000

Saídas (entregáveis):
  - results/calibration/calibration_table.csv   (parâmetros -> métricas -> score)
  - results/calibration/selected_config.json   (configuração escolhida)
  - results/final/metrics.csv                  (métricas da configuração final)
  - results/final/enhanced_candlestick.png     (1 gráfico da configuração final)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import backtrader as bt
import pandas as pd

from utils import prepare_csv
from execution import calibrate_execution_params
from microstructure import MicrostructureConfig
from risk import VolatilityTargetSizer
from metrics import compute_metrics
from plotting import plot_candlestick_with_trades
from enchanced_bot import EnhancedSmaCross  # sim, o arquivo está com esse nome


# ----------------------------
# Funções de score / seleção
# ----------------------------
def calmar_ratio(perf: Dict[str, float]) -> float:
    """
    Calmar simples: AnnualizedReturn / |MaxDrawdown|.
    - MaxDrawdown no compute_metrics é negativo (ex.: -0.12). Aqui usamos abs().
    """
    dd = perf.get("MaxDrawdown", None)
    ret = perf.get("AnnualizedReturn", None)
    if dd is None or ret is None:
        return float("-inf")
    dd_abs = abs(float(dd))
    if dd_abs == 0:
        return float("-inf")
    return float(ret) / dd_abs


def pick_best(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Regra simples e declarada:
      1) Maior Calmar
      2) Desempate: maior Sharpe
      3) Desempate: menor (mais próximo de zero) drawdown
    """
    def key(r: Dict[str, Any]) -> Tuple[float, float, float]:
        return (float(r.get("Calmar", float("-inf"))),
                float(r.get("Sharpe", float("-inf"))),
                float(r.get("MaxDrawdown", 0.0)))  # drawdown é negativo: -0.05 > -0.20
    return sorted(rows, key=key, reverse=True)[0]


# ----------------------------
# Backtest controlado (sem plot em massa)
# ----------------------------
def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["datetime"])
    df = df.sort_values("datetime").set_index("datetime")
    return df


def run_backtest(
    *,
    data_path: str | Path,
    cash: float,

    # sinal
    fast_period: int,
    slow_period: int,

    # risco
    target_vol: float,
    vol_lookback: int,
    max_leverage: float,

    # execução
    commission_perc: float,
    slippage_multiplier: float,

    # microestrutura
    min_volume_pct_avg: float,
    min_holding_period: int,
    max_spread_pct: float | None,

    # output
    out_dir: str | Path,
    plot: bool = False,
) -> Dict[str, float]:
    """
    Executa 1 backtest e retorna o dicionário de métricas (Sharpe/Sortino/DD/Retorno anualizado).

    Observação:
    - Plot só quando plot=True (use apenas na configuração final).
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1) limpar CSV (uma vez por run; é idempotente)
    clean_path = prepare_csv(str(data_path), str(Path("data") / "MES_2023_clean.csv"))

    # 2) carregar dataframe
    df = load_ohlcv_csv(clean_path)

    # 3) calibrar execução com multiplicador
    exec_params = calibrate_execution_params(
        df,
        high_col="High",
        low_col="Low",
        commission_perc=commission_perc,
        slippage_multiplier=slippage_multiplier,
    )

    # 4) backtrader
    data_feed = bt.feeds.PandasData(dataname=df)
    cerebro = bt.Cerebro()
    cerebro.adddata(data_feed)

    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=exec_params.commission_perc)
    cerebro.broker.set_slippage_perc(exec_params.slippage_perc)

    cerebro.addsizer(
        VolatilityTargetSizer,
        target_vol=target_vol,
        lookback=vol_lookback,
        max_leverage=max_leverage,
        contract_size=5.0,  # MES (micro) ~ 5 USD por ponto
    )

    cerebro.addstrategy(
        EnhancedSmaCross,
        fast_period=fast_period,
        slow_period=slow_period,
        micro_cfg=MicrostructureConfig(
            min_volume_pct_avg=min_volume_pct_avg,
            max_spread_pct=max_spread_pct,
            min_holding_period=min_holding_period,
        ),
    )

    results = cerebro.run()
    strat = results[0]

    # 5) métricas e (opcional) gráfico
    df_plot = df.reset_index()

    if plot:
        plot_candlestick_with_trades(
            df=df_plot,
            trades=strat.trades,
            title=f"Aprimorado: SMA({fast_period}/{slow_period}) + Micro + VolTarget",
            output_path=str(out_path / "enhanced_candlestick.png"),
            sma_short=fast_period,
            sma_long=slow_period,
        )

    perf = compute_metrics(df_plot, results, out_dir=str(out_path), equity_curve=strat.equity_curve)
    return perf


def run_case(tag: str, base: Dict[str, Any], overrides: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    cfg = dict(base)
    cfg.update(overrides)

    # roda
    perf = run_backtest(
        data_path=cfg["data_path"],
        cash=cfg["cash"],
        fast_period=cfg["fast_period"],
        slow_period=cfg["slow_period"],
        target_vol=cfg["target_vol"],
        vol_lookback=cfg["vol_lookback"],
        max_leverage=cfg["max_leverage"],
        commission_perc=cfg["commission_perc"],
        slippage_multiplier=cfg["slippage_multiplier"],
        min_volume_pct_avg=cfg["min_volume_pct_avg"],
        min_holding_period=cfg["min_holding_period"],
        max_spread_pct=cfg["max_spread_pct"],
        out_dir=str(out_dir),
        plot=False,
    )

    row = {
        "tag": tag,
        **{k: cfg[k] for k in [
            "fast_period", "slow_period",
            "target_vol", "vol_lookback", "max_leverage",
            "commission_perc", "slippage_multiplier",
            "min_volume_pct_avg", "min_holding_period", "max_spread_pct"
        ]},
        **perf,
    }
    row["Calmar"] = calmar_ratio(perf)
    return row


def main():
    parser = argparse.ArgumentParser(description="Etapa 1 — Calibração final (risco, execução, microestrutura)")
    parser.add_argument("--data", type=str, default="data/MES_2023.csv", help="Caminho do CSV bruto (default: data/MES_2023.csv)")
    parser.add_argument("--cash", type=float, default=100_000.0, help="Capital inicial (default: 100000)")
    parser.add_argument("--out-root", type=str, default="results", help="Pasta base de resultados (default: results)")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Não encontrei o arquivo de dados: {data_path.resolve()}")

    root = Path(args.out_root)
    calib_root = root / "calibration"
    final_root = root / "final"
    calib_root.mkdir(parents=True, exist_ok=True)
    final_root.mkdir(parents=True, exist_ok=True)

    # configuração base (ponto de partida)
    base: Dict[str, Any] = {
        "data_path": str(data_path),
        "cash": float(args.cash),

        # sinal
        "fast_period": 10,
        "slow_period": 20,

        # risco
        "target_vol": 0.10,
        "vol_lookback": 20,
        "max_leverage": 2.0,

        # execução
        "commission_perc": 0.0,
        "slippage_multiplier": 0.5,

        # microestrutura
        "min_volume_pct_avg": 0.3,
        "min_holding_period": 1,
        "max_spread_pct": None,
    }

    all_rows: List[Dict[str, Any]] = []

    # ----------------------------
    # 1) EXECUÇÃO (slippage_multiplier)
    # ----------------------------
    rows: List[Dict[str, Any]] = []
    for m in [0.25, 0.5, 1.0]:
        tag = f"execution_slipmult_{m}"
        out_dir = calib_root / "execution" / tag
        rows.append(run_case(tag, base, {"slippage_multiplier": m}, out_dir))
    all_rows += rows

    win = pick_best(rows)
    base["slippage_multiplier"] = win["slippage_multiplier"]

    # ----------------------------
    # 2) RISCO (target_vol, lookback)
    # ----------------------------
    rows = []
    risk_grid = [
        {"target_vol": 0.08, "vol_lookback": 20},
        {"target_vol": 0.10, "vol_lookback": 20},
        {"target_vol": 0.12, "vol_lookback": 20},
        {"target_vol": 0.10, "vol_lookback": 10},
        {"target_vol": 0.10, "vol_lookback": 40},
    ]
    for g in risk_grid:
        tag = f"risk_tv_{g['target_vol']}_lb_{g['vol_lookback']}"
        out_dir = calib_root / "risk" / tag
        rows.append(run_case(tag, base, g, out_dir))
    all_rows += rows

    win = pick_best(rows)
    base["target_vol"] = win["target_vol"]
    base["vol_lookback"] = win["vol_lookback"]

    # ----------------------------
    # 3) MICROESTRUTURA (volume, holding)
    # ----------------------------
    rows = []
    for v in [0.2, 0.3, 0.5]:
        for h in [1, 3]:
            tag = f"micro_vol_{v}_hold_{h}"
            out_dir = calib_root / "microstructure" / tag
            rows.append(run_case(tag, base, {"min_volume_pct_avg": v, "min_holding_period": h}, out_dir))
    all_rows += rows

    win = pick_best(rows)
    base["min_volume_pct_avg"] = win["min_volume_pct_avg"]
    base["min_holding_period"] = win["min_holding_period"]

    # ----------------------------
    # 4) SINAL (SMA)
    # ----------------------------
    rows = []
    sma_grid = [(8, 21), (10, 20), (10, 30), (15, 40), (20, 50)]
    for f, s in sma_grid:
        if f >= s:
            continue
        tag = f"sma_{f}_{s}"
        out_dir = calib_root / "signal" / tag
        rows.append(run_case(tag, base, {"fast_period": f, "slow_period": s}, out_dir))
    all_rows += rows

    win = pick_best(rows)
    base["fast_period"] = win["fast_period"]
    base["slow_period"] = win["slow_period"]

    # ----------------------------
    # Salvar tabela e config escolhida
    # ----------------------------
    df = pd.DataFrame(all_rows)
    table_path = calib_root / "calibration_table.csv"
    df.to_csv(table_path, index=False)

    cfg_path = calib_root / "selected_config.json"
    cfg_path.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")

    # ----------------------------
    # Rodar 1x FINAL com plot=True (1 gráfico)
    # ----------------------------
    final_perf = run_backtest(
        data_path=base["data_path"],
        cash=base["cash"],
        fast_period=base["fast_period"],
        slow_period=base["slow_period"],
        target_vol=base["target_vol"],
        vol_lookback=base["vol_lookback"],
        max_leverage=base["max_leverage"],
        commission_perc=base["commission_perc"],
        slippage_multiplier=base["slippage_multiplier"],
        min_volume_pct_avg=base["min_volume_pct_avg"],
        min_holding_period=base["min_holding_period"],
        max_spread_pct=base["max_spread_pct"],
        out_dir=str(final_root),
        plot=True,
    )

    # print resumo
    print("\n" + "=" * 70)
    print("ETAPA 1 OK — Calibração final concluída")
    print(f"Tabela:        {table_path}")
    print(f"Config final:  {cfg_path}")
    print(f"Final metrics: {final_root / 'metrics.csv'}")
    print(f"Final chart:   {final_root / 'enhanced_candlestick.png'}")
    print("-" * 70)
    print("Resultado financeiro final:")
    print(f"  Capital inicial: {final_perf['StartingEquity']:>14,.2f}")
    print(f"  Capital final:   {final_perf['FinalEquity']:>14,.2f}")
    print(f"  PnL final:       {final_perf['PnL']:>14,.2f}")
    print(f"  Retorno total:   {final_perf['TotalReturn'] * 100:>13.2f}%")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
