# src/enhanced_bot.py
import argparse
from pathlib import Path

import backtrader as bt
import pandas as pd

from execution import calibrate_execution_params
from microstructure import MicrostructureStrategy, MicrostructureConfig
from risk import VolatilityTargetSizer

from utils import prepare_csv
from metrics import compute_metrics
from pathlib import Path

DEFAULT_RAW_DATA = Path("data") / "MES_2023.csv"
DEFAULT_CLEAN_DATA = Path("data") / "MES_2023_clean.csv"
DEFAULT_RESULTS_DIR = Path("results") / "enhanced"

class EnhancedSmaCross(MicrostructureStrategy):
    """
    Versão aprimorada da estratégia de médias móveis:

    - Reutiliza a ideia de SMA curta x SMA longa (baseline)
    - Acrescenta filtros de microestrutura (volume, holding period, spread)
    - Tamanho da posição via volatility targeting (VolatilityTargetSizer)
    """

    params = (
        ("fast_period", 10),
        ("slow_period", 20),
        ("micro_cfg", MicrostructureConfig()),
    )

    def __init__(self):
        super().__init__()

        self.sma_fast = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.fast_period
        )
        self.sma_slow = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.slow_period
        )

        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def next(self):
        
        super().next()

        #
        if not self.micro_ok():
            return

        
        if not self.position:  # sem posição
            if self.crossover > 0:
                self.buy()   # entra long
            elif self.crossover < 0:
                self.sell()  # entra short
        else:
            
            if self.crossover > 0 and self.position.size < 0:
                self.close()
                self.buy()
            elif self.crossover < 0 and self.position.size > 0:
                self.close()
                self.sell()



def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """
    Lê o CSV limpo gerado pelo prepare_csv, que tem colunas:
    datetime, Open, High, Low, Close, Volume
    """
    df = pd.read_csv(path, parse_dates=["datetime"])
    df = df.sort_values("datetime").set_index("datetime")
    return df




def run_backtest(
    data_path: str | Path = DEFAULT_RAW_DATA,
    cash: float = 100_000.0,
    target_vol: float = 0.10,
    plot: bool = False,
    out_dir: str | Path = DEFAULT_RESULTS_DIR,
):
    # 1) Limpa o CSV bruto, igual ao baseline_bot
    clean_path = prepare_csv(str(data_path), str(DEFAULT_CLEAN_DATA))

    # 2) Carrega o CSV limpo para DataFrame
    df = load_ohlcv_csv(clean_path)

    # 3) Calibra parâmetros de execução (spread/slippage)
    exec_params = calibrate_execution_params(df, high_col="High", low_col="Low")

    # 4) Cria o feed de dados para o Backtrader
    data_feed = bt.feeds.PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.adddata(data_feed)

    # broker
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=exec_params.commission_perc)
    cerebro.broker.set_slippage_perc(exec_params.slippage_perc)

    # sizer de volatilidade
    cerebro.addsizer(
        VolatilityTargetSizer,
        target_vol=target_vol,
        lookback=20,
        max_leverage=2.0,
        contract_size=5.0,  # MES = micro E-mini, multiplicador 5 USD por ponto
    )

        # estratégia
    cerebro.addstrategy(
        EnhancedSmaCross,
        micro_cfg=MicrostructureConfig(
            min_volume_pct_avg=0.3,
            max_spread_pct=None,
            min_holding_period=1,
        ),
    )

    # analyzers (como você já tinha)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, riskfreerate=0.0, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="ddown")
    cerebro.addanalyzer(bt.analyzers.Returns, tann=252, _name="returns")

    results = cerebro.run()
    strat = results[0]

    if plot:
        cerebro.plot(style="candlestick")

    # 5) Gera metrics.csv no mesmo formato do baseline, mas em results/enhanced
    compute_metrics(df, results, out_dir=str(out_dir))

    # 6) Mantém o dicionário de métricas dos analyzers (se quiser usar depois)
    sharpe = strat.analyzers.sharpe.get_analysis().get("sharperatio", None)
    ddown = strat.analyzers.ddown.get_analysis()["max"]["drawdown"]
    rets = strat.analyzers.returns.get_analysis()
    annual_return = rets.get("rnorm", None)
    annual_return_pct = rets.get("rnorm100", None)

    metrics = {
        "sharpe": sharpe,
        "max_drawdown_pct": ddown,
        "annual_return": annual_return,
        "annual_return_pct": annual_return_pct,
    }

    return strat, metrics




def main():
    parser = argparse.ArgumentParser(
        description="Backtest do robô aprimorado (volatility targeting + microestrutura)"
    )
    parser.add_argument(
        "--data",
        type=str,
        default=str(DEFAULT_RAW_DATA),
        help="Caminho do CSV OHLCV bruto (default: data/MES_2023.csv)",
    )
    parser.add_argument(
        "--cash",
        type=float,
        default=100_000.0,
        help="Capital inicial",
    )
    parser.add_argument(
        "--target-vol",
        type=float,
        default=0.10,
        help="Volatilidade anual alvo (ex: 0.10 = 10%% a.a.)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Se passar esta flag, plota o gráfico de candles",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default=str(DEFAULT_RESULTS_DIR),
        help="Diretório para salvar metrics.csv (default: results/enhanced)",
    )

    args = parser.parse_args()

    strat, metrics = run_backtest(
        data_path=args.data,
        cash=args.cash,
        target_vol=args.target_vol,
        plot=args.plot,
        out_dir=args.results_dir,
    )

    print("==== RESULTADOS ENHANCED BOT ====")
    print(f"Sharpe Ratio (analyzer):       {metrics['sharpe']}")
    print(f"Max Drawdown (%):              {metrics['max_drawdown_pct']:.2f}")
    print(f"Retorno anual (dec):           {metrics['annual_return']}")
    print(f"Retorno anual (%):             {metrics['annual_return_pct']:.2f}")
    print(f"Metrics CSV salvo em: {args.results_dir}/metrics.csv")


if __name__ == "__main__":
    main()
