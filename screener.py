import os
import pickle

import numpy as np
import pandas as pd
import yfinance as yf

QUANTILE_LOW_MOMENTUM = 0.3
QUANTILE_HIGH_MOMENTUM = 0.9


class SP_500_stocks:
    df = None

    def __init__(self, filename="S&P_500_Historical_08-17-2024.csv") -> None:
        if os.path.isfile(filename):
            self.df = pd.read_csv(filename, index_col="date")
            self.df = self.df[self.df.index >= "2000-01-01"]
            self.df["tickers"] = self.df["tickers"].apply(
                lambda x: sorted(x.split(","))
            )

    def get_symbols(self, year: int, month: int, day: int = 1) -> list[str]:
        if self.df is None:
            return None

        snap_shot = f"{year}-{month:02}-{day:02}"
        df2 = self.df[self.df.index <= snap_shot]
        return df2.tail(1).tickers.values[0]

    def all_symbols(self) -> list[str]:
        return sorted(set(sum(self.df.tickers.values, [])))


sp_500_stocks = SP_500_stocks()


def roc(close: pd.Series, period: int = 10) -> pd.Series:
    return (close - close.shift(period)) / close.shift(period) * 100


def load_stocks(symbols):
    return yf.download(symbols, start="2000-01-01", group_by="ticker")


def resample_df(df):
    df = df.reset_index()
    df["Month"] = df["Date"].dt.strftime("%y-%m")
    df = df.groupby(["Month", "Ticker"]).agg(
        Date=("Date", "last"),
        Open=("Open", "first"),
        Close=("Close", "last"),
        Changes=("Changes", "sum"),
        PCT=("PCT", "sum"),
        SMA_100=("SMA_100", "last"),
        ROC_10=("ROC_10", "first"),
    )

    df["Changes_PCT"] = df["Changes"] + (df["PCT"] / 100000)

    return df


def convert_to_multiindex(df: pd.DataFrame) -> pd.DataFrame:
    # Stack the data to move the ticker symbols into the index
    df = df.stack(level=0, future_stack=True)
    df.index.names = ["Date", "Ticker"]

    # Set 'Ticker' and 'Date' as multi-index
    return df.reset_index().set_index(["Ticker", "Date"])


def add_indicator_day(df: pd.DataFrame) -> pd.DataFrame:
    df["SMA"] = df.groupby(level=0)["Close"].transform(
        lambda x: x.rolling(100).mean().round(2)
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
    df["SMA"] = df.groupby(level=1)["SMA"].transform(lambda x: x.shift(1))
    df["last_Close"] = df.Close.shift(1)

    for interval in [3, 6, 9, 12]:
        df[f"Changes_{interval}"] = df.groupby(level=1)["Changes_pct"].transform(
            (lambda x: x.rolling(interval).sum().shift(1))
        )
        df[f"PCT_{interval}"] = df.groupby(level=1)["PCT"].transform(
            (lambda x: x.rolling(interval).sum().shift(1))
        )

    return df


def pre_processing(df: pd.DataFrame) -> pd.DataFrame:
    df = convert_to_multiindex(df)
    df = add_indicator_day(df)
    df = resample_month(df)
    df = add_indicator_month(df)
    return df


def sp_500_ticker(year_month: str) -> list:
    year = 2000 + int(year_month[:2])
    month = year_month[-2:]
    return sp_500_stocks.get_symbols(year, month)


def match_available_ticker(df_ticker: list, sp_500_ticker: list) -> list:
    return list(set(sp_500_ticker).intersection(df_ticker))


def strategy(df) -> pd.DataFrame:
    MAX_TICKER = 10
    QUANTILE_LOW_MOMENTUM = 0.5
    QUANTILE_HIGH_MOMENTUM = 0.8

    def lower_quantile(df: pd.DataFrame, column, threshold):
        df = df[column]
        ticker = df[df <= df.quantile(threshold)].index
        return list(ticker)

    def higher_quantile(df: pd.DataFrame, column, threshold):
        df = df[column]
        ticker = df[df >= df.quantile(threshold)].index
        return list(ticker)

    def trendless(df: pd.DataFrame):
        df = df[["last_Close", "SMA"]]
        ticker = df[df.last_Close < df.SMA].index
        return list(ticker)

    def downtrend(df):
        df = df[["ROC_7"]]
        ticker = df[df.ROC_7 <= 0].index
        return list(ticker)

    ticker = []
    for changes_idx in [9, 12]:
        ticker = ticker + lower_quantile(
            df,
            f"Changes_{changes_idx}",
            QUANTILE_LOW_MOMENTUM,
        )

    for pct_idx in [3, 6, 9]:
        ticker = ticker + higher_quantile(
            df,
            f"PCT_{pct_idx}",
            QUANTILE_HIGH_MOMENTUM,
        )
    ticker = ticker + trendless(df)
    ticker = ticker + downtrend(df)

    ticker = list(set(df.index.unique()) - set(ticker))
    # return df.loc[ticker]["ROC_12"].nlargest(MAX_TICKER).index
    return df.loc[ticker]["ROC_12"].nsmallest(MAX_TICKER).index


def backtest(df: pd.DataFrame) -> dict():
    trade_ticker = {}

    for year_month in df.reset_index().Month.unique():
        available_ticker = sp_500_ticker(year_month)
        monthly_ticker = match_available_ticker(
            df_ticker=df.reset_index().Ticker.unique(),
            sp_500_ticker=available_ticker,
        )

        trade_ticker[year_month] = strategy(
            df.loc[
                (year_month, monthly_ticker),
                :,
            ]
            .dropna()
            .reset_index()
            .drop("Month", axis=1)
            .set_index("Ticker")
        )

    return {year_month: list(ticker) for year_month, ticker in trade_ticker.items()}


def load_sp500_stocks(cache: bool = True) -> pd.DataFrame:
    df = None
    if cache:
        try:
            with open("./data/stocks.pkl", "rb") as file:
                df = pickle.load(file)
        except Exception as e:
            print(e)
    if df is None:
        df = load_stocks(sp_500_stocks.all_symbols())
        df.to_pickle("./data/stocks.pkl")

    return df.round(2)


def main() -> None:
    stocks = load_sp500_stocks()

    stocks = pd.concat(
        [
            stocks,
            pd.DataFrame(
                pd.Series(stocks.index[-1] + pd.Timedelta(days=30)), columns=["Date"]
            ).set_index("Date"),
        ]
    )

    stocks = pre_processing(stocks)

    # reduce Data for backtest
    stocks = stocks.loc[stocks.reset_index().Month.unique()[-10:]].ffill()

    trades = backtest(stocks)

    for year_month, symbols in trades.items():
        if len(symbols) < 10:
            for i in range(len(symbols), 10):
                trades[year_month].append("")

    with open("trades.md", "w") as text_file:
        text_file.write(pd.DataFrame.from_dict(trades).T.to_markdown())


if __name__ == "__main__":
    main()
