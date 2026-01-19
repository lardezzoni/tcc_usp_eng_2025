# src/compare.py
"""
Script para gerar comparacao entre baseline e enhanced bot.
Gera a equity curve (curva de capital) comparativa.
"""
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import backtrader as bt

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from baseline_bot import SmaCrossStrategy, run_backtest as run_baseline
from enchanced_bot import EnhancedSmaCross, run_backtest as run_enhanced
from utils import prepare_csv


def run_backtest_with_equity(
    strategy_class,
    data_path: str,
    clean_path: str,
    cash: float = 100_000.0,
    strategy_kwargs: dict = None,
):
    """
    Run a backtest and return the equity curve (portfolio value over time).
    """
    from microstructure import MicrostructureConfig
    from execution import calibrate_execution_params
    from risk import VolatilityTargetSizer

    clean_path = prepare_csv(data_path, clean_path)
    df = pd.read_csv(clean_path, parse_dates=["datetime"])
    df = df.sort_values("datetime").set_index("datetime")

    data_feed = bt.feeds.PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.adddata(data_feed)
    cerebro.broker.setcash(cash)

    # Add time return analyzer to track equity
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')

    if strategy_kwargs:
        cerebro.addstrategy(strategy_class, **strategy_kwargs)
        # Add volatility sizer for enhanced
        if strategy_class == EnhancedSmaCross:
            exec_params = calibrate_execution_params(df, high_col="High", low_col="Low")
            cerebro.broker.setcommission(commission=exec_params.commission_perc)
            cerebro.broker.set_slippage_perc(exec_params.slippage_perc)
            cerebro.addsizer(
                VolatilityTargetSizer,
                target_vol=0.10,
                lookback=20,
                max_leverage=2.0,
                contract_size=5.0,
            )
    else:
        cerebro.addstrategy(strategy_class)

    results = cerebro.run()
    strat = results[0]

    # Get time returns and compute equity curve
    time_returns = strat.analyzers.timereturn.get_analysis()

    dates = list(time_returns.keys())
    returns = list(time_returns.values())

    # Build equity curve from returns
    equity = [cash]
    for ret in returns:
        if ret is not None:
            equity.append(equity[-1] * (1 + ret))
        else:
            equity.append(equity[-1])

    return dates, equity[1:]  # Remove initial cash value


def plot_equity_curves(
    baseline_dates,
    baseline_equity,
    enhanced_dates,
    enhanced_equity,
    output_path: str = "results/equity_curve_comparison.png",
):
    """
    Plot equity curves for baseline and enhanced strategies.
    Academic style chart with legend for ABNT/USP format.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(baseline_dates, baseline_equity, label="Baseline (SMA Cross)",
            color="#1f77b4", linewidth=1.5)
    ax.plot(enhanced_dates, enhanced_equity, label="Aprimorado (Microestrutura + Vol. Targeting)",
            color="#ff7f0e", linewidth=1.5)

    ax.set_xlabel("Data", fontsize=11)
    ax.set_ylabel("Valor do Portfólio (USD)", fontsize=11)
    ax.set_title("Curva de Capital: Baseline vs Aprimorado", fontsize=12, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3)

    # Format x-axis dates
    fig.autofmt_xdate()

    # Add annotation for academic caption
    fig.text(0.5, -0.02,
             "Figura — Comparacao da evolucao do capital entre estrategia baseline e aprimorada.",
             ha='center', fontsize=9, style='italic')

    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved equity curve comparison to {output_path}")
    plt.close(fig)


def main():
    """
    Run both backtests and generate comparison chart.
    """
    from microstructure import MicrostructureConfig

    data_path = "data/MES_2023.csv"
    baseline_clean = "data/MES_2023_baseline_clean.csv"
    enhanced_clean = "data/MES_2023_enhanced_clean.csv"
    cash = 100_000.0

    print("=" * 50)
    print("Running Baseline Backtest...")
    print("=" * 50)
    baseline_dates, baseline_equity = run_backtest_with_equity(
        SmaCrossStrategy,
        data_path,
        baseline_clean,
        cash=cash,
    )

    print("\n" + "=" * 50)
    print("Running Enhanced Backtest...")
    print("=" * 50)
    enhanced_dates, enhanced_equity = run_backtest_with_equity(
        EnhancedSmaCross,
        data_path,
        enhanced_clean,
        cash=cash,
        strategy_kwargs={
            "micro_cfg": MicrostructureConfig(
                min_volume_pct_avg=0.3,
                max_spread_pct=None,
                min_holding_period=1,
            )
        },
    )

    print("\n" + "=" * 50)
    print("Generating Equity Curve Comparison...")
    print("=" * 50)
    plot_equity_curves(
        baseline_dates,
        baseline_equity,
        enhanced_dates,
        enhanced_equity,
        output_path="results/equity_curve_comparison.png",
    )

    # Print summary statistics
    print("\n" + "=" * 50)
    print("Summary Statistics")
    print("=" * 50)

    baseline_final = baseline_equity[-1] if baseline_equity else cash
    enhanced_final = enhanced_equity[-1] if enhanced_equity else cash

    baseline_return = (baseline_final - cash) / cash * 100
    enhanced_return = (enhanced_final - cash) / cash * 100

    print(f"Baseline Final Value:  ${baseline_final:,.2f} ({baseline_return:+.2f}%)")
    print(f"Enhanced Final Value:  ${enhanced_final:,.2f} ({enhanced_return:+.2f}%)")
    print(f"Difference:            ${enhanced_final - baseline_final:,.2f}")


if __name__ == "__main__":
    main()
