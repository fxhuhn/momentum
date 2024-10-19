import numpy as np
import pandas as pd


def roc(close: pd.Series, period: int = 10) -> pd.Series:
    return (close - close.shift(period)) / close.shift(period) * 100


def convert_to_multiindex(df: pd.DataFrame) -> pd.DataFrame:
    # Stack the data to move the ticker symbols into the index
    df = df.stack(level=0, future_stack=True)
    df.index.names = ["Date", "Ticker"]

    # Set 'Ticker' and 'Date' as multi-index
    return df.reset_index().set_index(["Ticker", "Date"])


def add_indicator_day(df: pd.DataFrame) -> pd.DataFrame:
    df["SMA"] = df.groupby(level=0)["Close"].transform(
        lambda x: x.rolling(300).mean().round(2)
    )
    df["ROC_7"] = df.groupby(level=0)["Close"].transform(lambda x: roc(x, 7))

    df["PCT"] = df.groupby(level=0)["Close"].transform(
        lambda x: x.ffill().pct_change(fill_method=None) * 100
    )
    df["Changes"] = df.groupby(level=0)["PCT"].transform(lambda x: np.sign(x))

    return df


def resample_month(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index()

    df["Month"] = df["Date"].dt.strftime("%y-%m")

    df = df.groupby(["Month", "Ticker"]).agg(
        Date=("Date", "last"),
        Open=("Open", "first"),
        Close=("Close", "last"),
        Changes=("Changes", "sum"),
        PCT=("PCT", "sum"),
        SMA=("SMA", "last"),
        ROC_7=("ROC_7", "first"),
    )

    df["Changes_pct"] = df["Changes"] + (df["PCT"] / 100000)
    return df


def add_indicator_month(df: pd.DataFrame) -> pd.DataFrame:
    df["ROC_12"] = df.groupby(level=1)["Close"].transform(lambda x: roc(x, 12).shift(1))
    df["STD_12"] = df.groupby(level=1)["PCT"].transform(
        lambda x: x.rolling(9).std().shift(1)
    )

    df["SMA"] = df.groupby(level=1)["SMA"].transform(lambda x: x.shift(1))
    df["last_Close"] = df.groupby(level=1)["Close"].transform(lambda x: x.shift(1))

    for interval in [3, 6, 9, 12]:
        df[f"Changes_{interval}"] = df.groupby(level=1)["Changes_pct"].transform(
            (lambda x: x.rolling(interval).sum().shift(1))
        )
        df[f"PCT_{interval}"] = df.groupby(level=1)["PCT"].transform(
            (lambda x: x.rolling(interval).sum().shift(1))
        )

    return df
