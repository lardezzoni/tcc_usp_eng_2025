# src/plotting.py
"""
Clean academic-style charts for TCC USP.
Simple price chart + SMA + trade markers.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np


def plot_candlestick_with_trades(
    df: pd.DataFrame,
    trades: list,
    title: str = "Estratégia SMA Crossover",
    output_path: str = "chart.png",
    sma_short: int = 10,
    sma_long: int = 20,
):
    """
    Create a clean academic candlestick chart.

    Args:
        df: DataFrame with columns [datetime, Open, High, Low, Close]
        trades: List of dicts with {date, type, price}
        title: Chart title
        output_path: Where to save the PNG
        sma_short: Short SMA period
        sma_long: Long SMA period
    """
    # Prepare data
    df = df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)

    # Calculate SMAs
    df['SMA10'] = df['Close'].rolling(window=sma_short).mean()
    df['SMA20'] = df['Close'].rolling(window=sma_long).mean()

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 7))

    # Plot candlesticks manually (simple version - just use close price line + range)
    dates = df['datetime']

    # Plot price as a line with high-low range shading
    ax.fill_between(dates, df['Low'], df['High'], alpha=0.3, color='gray', label='_nolegend_')
    ax.plot(dates, df['Close'], color='black', linewidth=1, label='Preço de Fechamento')

    # Plot SMAs
    ax.plot(dates, df['SMA10'], color='#2E86AB', linewidth=1.5, label=f'MMS({sma_short})')
    ax.plot(dates, df['SMA20'], color='#E94F37', linewidth=1.5, label=f'MMS({sma_long})')

    # Plot trades
    buys = [t for t in trades if t['type'] == 'buy']
    sells = [t for t in trades if t['type'] == 'sell']

    if buys:
        buy_dates = [t['date'] for t in buys]
        buy_prices = [t['price'] for t in buys]
        ax.scatter(buy_dates, buy_prices, marker='^', color='green', s=100,
                   zorder=5, label='Compra')

    if sells:
        sell_dates = [t['date'] for t in sells]
        sell_prices = [t['price'] for t in sells]
        ax.scatter(sell_dates, sell_prices, marker='v', color='red', s=100,
                   zorder=5, label='Venda')

    # Formatting
    ax.set_xlabel('Data', fontsize=11)
    ax.set_ylabel('Preço (USD)', fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    fig.autofmt_xdate()

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved chart to {output_path}")
    plt.close(fig)


def plot_equity_comparison(
    baseline_dates: list,
    baseline_equity: list,
    enhanced_dates: list,
    enhanced_equity: list,
    output_path: str = "results/equity_curve_comparison.png",
    initial_cash: float = 100_000.0,
):
    """
    Plot equity curves for baseline vs enhanced - clean academic style.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(baseline_dates, baseline_equity,
            color='#2E86AB', linewidth=1.5, label='Baseline (SMA Cross)')
    ax.plot(enhanced_dates, enhanced_equity,
            color='#E94F37', linewidth=1.5, label='Aprimorado (Microestrutura)')

    # Add horizontal line at initial capital
    ax.axhline(y=initial_cash, color='gray', linestyle='--', alpha=0.5, label='Capital Inicial')

    ax.set_xlabel('Data', fontsize=11)
    ax.set_ylabel('Valor do Portfólio (USD)', fontsize=11)
    ax.set_title('Curva de Capital: Baseline vs Aprimorado', fontsize=13, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')

    # Format y-axis with thousands separator
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
    fig.autofmt_xdate()

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Saved equity curve to {output_path}")
    plt.close(fig)
