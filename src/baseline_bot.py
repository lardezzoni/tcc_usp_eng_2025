import backtrader as bt
import datetime
import pandas as pd
import math
import os
from metrics import compute_metrics
from utils import prepare_csv


class SmaCrossStrategy(bt.Strategy):
    params = dict(short_period=10, long_period=20)

    def __init__(self):
        self.sma_short = bt.ind.SMA(period=self.p.short_period)
        self.sma_long = bt.ind.SMA(period=self.p.long_period)
        self.crossover = bt.ind.CrossOver(self.sma_short, self.sma_long)

    def next(self):
        if self.position.size == 0:
            if self.crossover > 0:  # sinal de compra
                self.buy()
            elif self.crossover < 0:  # sinal de venda
                self.sell()
        elif self.position.size > 0 and self.crossover < 0:
            self.close()  # encerra posição comprada
            self.sell()
        elif self.position.size < 0 and self.crossover > 0:
            self.close()  # encerra posição vendida
            self.buy()



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

    cerebro.plot(style='candlestick')

    df = pd.read_csv(clean_path)
    compute_metrics(df, results, out_dir="results/baseline")

if __name__ == "__main__":
    os.makedirs("results/baseline", exist_ok=True)
    run_backtest()
