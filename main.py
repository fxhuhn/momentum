import os
import pickle

import numpy as np
import pandas as pd
import yfinance as yf

QUANTILE_LOW_MOMENTUM = 0.3
QUANTILE_HIGH_MOMENTUM = 0.9


class SP_500_stocks:
    df = None

    def __init__(self, filename="S&P_500_Historical_04-08-2024.csv") -> None:
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
    df["SMA"] = df.groupby(level=0)["Close"].transform(lambda x: x.rolling(100).mean())
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
    QUANTILE_LOW_MOMENTUM = 0.3
    QUANTILE_HIGH_MOMENTUM = 0.9

    def lower_quantile(df: pd.DataFrame, column, threshold):
        df = df[column]
        ticker = df[df < df.quantile(threshold)].index
        return list(ticker)

    def higher_quantile(df: pd.DataFrame, column, threshold):
        df = df[column]
        ticker = df[df > df.quantile(threshold)].index
        return list(ticker)

    def trendless(df: pd.DataFrame):
        df = df[["Close", "SMA"]]
        ticker = df[df.Close < df.SMA].index
        return list(ticker)

    def downtrend(df):
        df = df[["ROC_7"]]
        ticker = df[df.ROC_7 < 0].index
        return list(ticker)

    ticker = []
    for changes_idx in [6, 9]:
        ticker = ticker + lower_quantile(
            df,
            f"Changes_{changes_idx}",
            QUANTILE_LOW_MOMENTUM,
        )

    for pct_idx in [3]:
        ticker = ticker + higher_quantile(
            df,
            f"PCT_{pct_idx}",
            QUANTILE_HIGH_MOMENTUM,
        )
    ticker = ticker + trendless(df)
    ticker = ticker + downtrend(df)

    ticker = list(set(df.index.unique()) - set(ticker))

    """
    # choose random ticker
    if len(df.loc[ticker]["ROC_12"]) > 0:
        return df.loc[ticker]["ROC_12"].sample(MAX_TICKER).index
    else:
        return []
    """
    # return df.loc[ticker]["ROC_12"].nlargest(MAX_TICKER).index
    return df.loc[ticker]["ROC_12"].nsmallest(MAX_TICKER).index


def backtest(df: pd.DataFrame):  # -> tuple(pd.DataFrame, float):
    trade_ticker = {}
    start = 10_000
    change_matrix = []
    depot = []

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
            .reset_index()
            .drop("Month", axis=1)
            .set_index("Ticker")
        )

    for year_month, ticker in trade_ticker.items():
        trades = df.loc[(year_month, ticker), ["Open", "Close"]]
        trades_debug = df.loc[(year_month, ticker), :]
        if len(trades) > 0:
            trades = trades.round({"Open": 2, "Close": 2, "Profit": 1, "Gewinn": 2})
            trades_debug = trades_debug.round(
                {
                    "Open": 2,
                    "Close": 2,
                    "Profit": 1,
                    "Gewinn": 2,
                    "SMA": 2,
                    "PCT": 4,
                    "Changes_pct": 4,
                    "ROC_7": 4,
                    "ROC_12": 4,
                    "Changes_3": 4,
                    "Changes_6": 4,
                    "Changes_9": 4,
                    "Changes_12": 4,
                    "PCT_3": 4,
                    "PCT_6": 4,
                    "PCT_9": 4,
                    "PCT_12": 4,
                }
            )

            trades_debug[
                [
                    "Open",
                    "Close",
                    "SMA",
                    "PCT",
                    "ROC_7",
                    "ROC_12",
                    # "Changes_3",
                    "Changes_6",
                    "Changes_9",
                    # "Changes_12",
                    "PCT_3",
                    # "PCT_6",
                    # "PCT_9",
                    # "PCT_12",
                ]
            ].sort_values("Ticker").dropna().to_csv(
                f"./data/trades/debug_{year_month}.csv", header=True, mode="w"
            )

            trades["Profit"] = (trades.Close - trades.Open) / trades.Open * 100
            trades["qty"] = (start / len(trades)) // trades.Open
            trades["Gewinn"] = (trades.Close - trades.Open) * trades.qty
            gewinn = trades.Gewinn.sum()

            trades = trades.round({"Open": 2, "Close": 2, "Profit": 1, "Gewinn": 2})
            # trades.qty = trades.qty.astype(int)
            trades.sort_values("Ticker").dropna().to_csv(
                f"./data/trades/{year_month}.csv", header=True, mode="w"
            )

            change_matrix = change_matrix + [
                list((year_month[:2], year_month[-2:], trades.Profit.mean()))
            ]
        else:
            gewinn = 0
        start = start + gewinn
        depot = depot + [{"year_month": year_month, "depot": start, "monthly": gewinn}]

    change_matrix = pd.DataFrame(
        change_matrix, columns=["Year", "Month", "Change"]
    ).set_index(["Year", "Month"])

    pd.DataFrame(depot).to_csv("./data/depot.csv", header=True, mode="w", index=False)

    return change_matrix, start


def load_sp500_stocks(cache: bool = True) -> pd.DataFrame:
    if cache:
        with open("./data/stocks.pkl", "rb") as file:
            df = pickle.load(file)
    else:
        df = load_stocks(sp_500_stocks.all_symbols())
        df.to_pickle("./data/stocks.pkl")

    return df


def main() -> None:
    stocks = load_sp500_stocks(cache=True)
    stocks = pre_processing(stocks)

    # reduce Data for backtest
    stocks = stocks.loc[stocks.reset_index().Month.unique()[-166:]]  # 11:166, 18:82

    trade_matrix, profit = backtest(stocks)

    output = trade_matrix.unstack(level=1)
    output.loc[:, "Average"] = output.mean(axis=1)
    output.loc["Average", :] = output.mean(axis=0)
    output = output.round(2)

    with open("matrix.md", "w") as text_file:
        text_file.write(
            output.to_markdown(floatfmt=".2f")
            .replace("(", " ")
            .replace(")", " ")
            .replace("'", " ")
            .replace("Change ,", "        ")
        )
    print(output)

    print(f"{profit:,.0f}")


if __name__ == "__main__":
    main()
