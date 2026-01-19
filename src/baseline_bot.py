import backtrader as bt
import datetime
import pandas as pd
import math
import os
from metrics import compute_metrics
from utils import prepare_csv
from plotting import plot_candlestick_with_trades


class SmaCrossStrategy(bt.Strategy):
    params = dict(short_period=10, long_period=20)

    def __init__(self):
        self.sma_short = bt.ind.SMA(period=self.p.short_period)
        self.sma_long = bt.ind.SMA(period=self.p.long_period)
        self.crossover = bt.ind.CrossOver(self.sma_short, self.sma_long)
        self.trades = []  # Track trades for plotting
        self.equity_curve = []  # Track portfolio value for metrics

    def next(self):
        # Track equity curve
        self.equity_curve.append(self.broker.getvalue())

        if self.position.size == 0:
            if self.crossover > 0:
                self.buy()
            elif self.crossover < 0:
                self.sell()
        elif self.position.size > 0 and self.crossover < 0:
            self.close()
            self.sell()
        elif self.position.size < 0 and self.crossover > 0:
            self.close()
            self.buy()

    def notify_trade(self, trade):
        if trade.justopened:
            trade_type = 'buy' if trade.size > 0 else 'sell'
            self.trades.append({
                'date': self.data.datetime.datetime(),
                'type': trade_type,
                'price': trade.price,
            })



def run_backtest(data_path="data/MES_2023.csv", cash=100000.0):
    clean_path = prepare_csv(data_path, "data/MES_2023_clean.csv")

    data = bt.feeds.GenericCSVData(
        dataname=clean_path,
        dtformat='%Y-%m-%d',
        timeframe=bt.TimeFrame.Days,
        openinterest=-1,
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5
    )

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.adddata(data)
    cerebro.addstrategy(SmaCrossStrategy)

    print("Starting Portfolio Value:", cerebro.broker.getvalue())
    results = cerebro.run()
    print("Final Portfolio Value:", cerebro.broker.getvalue())

    # Get strategy and trades
    strat = results[0]
    trades = strat.trades

    # Load data for plotting
    df = pd.read_csv(clean_path)

    # Generate clean academic chart
    plot_candlestick_with_trades(
        df=df,
        trades=trades,
        title="Baseline: Estratégia SMA Crossover (10/20)",
        output_path="results/baseline/baseline_candlestick.png",
    )

    compute_metrics(df, results, out_dir="results/baseline", equity_curve=strat.equity_curve)

    return results, df, trades, strat.equity_curve

if __name__ == "__main__":
    os.makedirs("results/baseline", exist_ok=True)
    run_backtest()
