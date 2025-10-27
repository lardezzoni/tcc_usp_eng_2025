import pandas as pd
import os

import pandas as pd
import os

def prepare_csv(input_path="data/MES_2023.csv", output_path="data/MES_2023_clean.csv"):
    print(f"🔧 Limpando dataset: {input_path}")
    df = pd.read_csv(input_path)

    # Se o arquivo veio do yfinance e contém a coluna "Ticker", elimina
    if "Ticker" in df.columns:
        df = df.drop(columns=["Ticker"])

    # Tenta identificar a coluna de data
    if "Date" in df.columns:
        df["datetime"] = pd.to_datetime(df["Date"])
    elif "Date" not in df.columns and "Unnamed: 0" in df.columns:
        df["datetime"] = pd.to_datetime(df["Unnamed: 0"])
    elif "Price" in df.columns:  # caso mal formatado com "Price" como data
        df["datetime"] = pd.to_datetime(df["Price"], errors="coerce")
    else:
        raise ValueError("Nenhuma coluna de data válida encontrada no CSV!")

    # Agora tenta encontrar os campos OHLCV
    possible_cols = ["Open", "High", "Low", "Close", "Volume"]
    found_cols = [c for c in possible_cols if c in df.columns]

    if len(found_cols) < 5:
        print("⚠️ Algumas colunas faltando, detectando automaticamente...")
        print("Colunas encontradas:", df.columns.tolist())

    # Filtra apenas as colunas necessárias
    df_clean = df[["datetime", "Open", "High", "Low", "Close", "Volume"]].copy()
    df_clean = df_clean.dropna()
    df_clean = df_clean.sort_values("datetime")

    # Salva em formato compatível
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_clean.to_csv(output_path, index=False, date_format="%Y-%m-%d")

    print(f"✅ CSV limpo salvo em: {output_path}")
    print(df_clean.head())

    return output_path
