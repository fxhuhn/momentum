import pickle

import pandas as pd
import yfinance as yf

from tools import SP500, calc
from tools import strategy as momentum

sp_500_stocks = SP500.stocks


def load_stocks(symbols):
    return yf.download(
        symbols, start="2000-01-01", group_by="ticker", rounding=True, threads=False
    )


def pre_processing(df: pd.DataFrame) -> pd.DataFrame:
    df = calc.convert_to_multiindex(df)
    df = calc.add_indicator_day(df)
    df = calc.resample_month(df)
    df = calc.add_indicator_month(df)
    return df


def sp_500_ticker(year_month: str) -> list:
    year = 2000 + int(year_month[:2])
    month = year_month[-2:]
    return sp_500_stocks.get_symbols(year, month)


def match_available_ticker(df_ticker: list, sp_500_ticker: list) -> list:
    return list(set(sp_500_ticker).intersection(df_ticker))


def backtest(df: pd.DataFrame) -> dict():
    trade_ticker = {}

    for year_month in df.reset_index().Month.unique():
        available_ticker = sp_500_ticker(year_month)
        monthly_ticker = match_available_ticker(
            df_ticker=df.reset_index().Ticker.unique(),
            sp_500_ticker=available_ticker,
        )

        trade_ticker[year_month] = momentum.strategy(
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

    # add upcoming month
    stocks = pd.concat(
        [
            stocks.dropna(thresh=500),
            pd.DataFrame(
                pd.Series(stocks.index[-1] + pd.Timedelta(days=30)), columns=["Date"]
            ).set_index("Date"),
        ]
    )

    # fill future date with current data
    stocks.iloc[-1] = stocks.iloc[-4:].ffill().iloc[-1]

    stocks = pre_processing(stocks)

    # reduce Data for backtest
    stocks = stocks.loc[stocks.reset_index().Month.unique()[-10:]].ffill()

    trades = backtest(stocks)

    for year_month, symbols in trades.items():
        trades[year_month].sort()

        if len(symbols) < 10:
            for i in range(len(symbols), 10):
                trades[year_month].append("")

    with open("trades.md", "w") as text_file:
        text_file.write(pd.DataFrame.from_dict(trades).T.to_markdown())


if __name__ == "__main__":
    main()
