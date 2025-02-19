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

    for year_month, ticker in trade_ticker.items():
        trades = df.loc[(year_month, ticker), ["Open", "Close"]]
        if len(trades) > 0:
            trades = trades.round({"Open": 2, "Close": 2, "Profit": 1, "Gewinn": 2})

            trades["Profit"] = (trades.Close - trades.Open) / trades.Open * 100
            trades["qty"] = (start / len(trades)) // trades.Open
            trades["Gewinn"] = (trades.Close - trades.Open) * trades.qty
            gewinn = trades.Gewinn.sum()

            trades = trades.round({"Open": 2, "Close": 2, "Profit": 1, "Gewinn": 2})
            trades.sort_values("Ticker").dropna().to_csv(
                f"./data/trades/{year_month}.csv", header=True, mode="w"
            )

            change_matrix = change_matrix + [
                list((year_month[:2], year_month[-2:], trades.Profit.mean()))
            ]

            start = (
                start
                - (trades.Open * trades.qty).sum()
                + (trades.Close * trades.qty).sum()
            )
        else:
            gewinn = 0
        depot = depot + [{"year_month": year_month, "depot": start, "monthly": gewinn}]

    change_matrix = pd.DataFrame(
        change_matrix, columns=["Year", "Month", "Change"]
    ).set_index(["Year", "Month"])

    pd.DataFrame(depot).round(2).to_csv(
        "./data/depot.csv", header=True, mode="w", index=False
    )

    return change_matrix, start


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
    stocks = pre_processing(stocks)

    # reduce Data for backtest
    stocks = stocks.loc[
        stocks.reset_index().Month.unique()[-166:]
    ]  # 11:166, 18:82, 21:46, 23:22, 21:46

    trade_matrix, profit = backtest(stocks)

    output = trade_matrix.unstack(level=1)
    output.loc[:, "Average"] = output.mean(axis=1)
    output.loc["Average", :] = output.mean(axis=0)
    output.loc[:, "Yearly"] = output.Average.mul(12)
    output = output.round(2)

    with open("matrix.md", "w") as text_file:
        text_file.write(
            output.to_markdown(floatfmt=".2f")
            .replace("(", " ")
            .replace(")", " ")
            .replace("'", " ")
            .replace(" ,", "  ")
            .replace("nan", "   ")
            .replace("Change", "      ")
        )
    print(output)

    print(f"{profit:,.0f}")


if __name__ == "__main__":
    main()
