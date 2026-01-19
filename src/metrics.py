import numpy as np
import pandas as pd
import os


def compute_metrics(df, results, out_dir="results", equity_curve=None):
    """
    Compute trading metrics from the strategy's equity curve.

    Args:
        df: DataFrame with price data (used only if equity_curve is None)
        results: Backtrader results list
        out_dir: Output directory for metrics.csv
        equity_curve: List of portfolio values over time (from strategy)
    """

    if equity_curve is not None and len(equity_curve) > 1:
        # Use actual equity curve from the robot
        equity = pd.Series(equity_curve)
        returns = equity.pct_change().dropna()
    else:
        # Fallback: try to get from backtrader analyzers
        strat = results[0]
        if hasattr(strat, 'analyzers') and hasattr(strat.analyzers, 'timereturn'):
            time_returns = strat.analyzers.timereturn.get_analysis()
            returns = pd.Series(list(time_returns.values())).dropna()
        else:
            # Last resort: use asset returns (not ideal)
            returns = df["Close"].pct_change().dropna()

    # Calculate metrics
    mean_ret = returns.mean()
    std_ret = returns.std()

    # Sharpe Ratio (annualized)
    sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0

    # Sortino Ratio (annualized, using downside deviation)
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else std_ret
    sortino = (mean_ret / downside_std) * np.sqrt(252) if downside_std > 0 else 0

    # Max Drawdown from equity curve
    if equity_curve is not None and len(equity_curve) > 1:
        equity = pd.Series(equity_curve)
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        max_dd = drawdown.min()
    else:
        # Approximate from returns
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_dd = drawdown.min()

    # Annualized Return
    annualized_return = mean_ret * 252

    metrics = {
        "Sharpe": sharpe,
        "Sortino": sortino,
        "MaxDrawdown": max_dd,
        "AnnualizedReturn": annualized_return,
    }

    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame([metrics]).to_csv(os.path.join(out_dir, "metrics.csv"), index=False)
    print(f"\nSaved metrics to {out_dir}/metrics.csv")
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")

    return metrics
