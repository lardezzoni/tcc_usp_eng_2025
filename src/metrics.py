import numpy as np
import pandas as pd
import os

def compute_metrics(df, results, out_dir="results"):
    returns = df["Close"].pct_change().dropna()
    mean_ret = returns.mean()
    std_ret = returns.std()

    sharpe = (mean_ret / std_ret) * np.sqrt(252)
    sortino = (mean_ret / returns[returns < 0].std()) * np.sqrt(252)
    max_dd = (df["Close"] / df["Close"].cummax() - 1).min()

    metrics = {
        "Sharpe": sharpe,
        "Sortino": sortino,
        "MaxDrawdown": max_dd,
        "AnnualizedReturn": mean_ret * 252,
    }

    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame([metrics]).to_csv(os.path.join(out_dir, "metrics.csv"), index=False)
    print(f"\nSaved metrics to {out_dir}/metrics.csv")
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")
