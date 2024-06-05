import pandas as pd

# tools to export the reports


def trades_daily(trades: pd.DataFrame) -> None:
    for symbol in trades.symbol.to_list():
        trades.loc[trades.symbol == symbol, "start"] = trades[
            trades.symbol == symbol
        ].start.ffill()
    trades.set_index("Date").to_csv("trades.csv")


def trade_report(trades: pd.DataFrame) -> None:
    df = (
        trades.groupby(["symbol", "start"])
        .agg(
            Start_Datum=("next1_Date", "first"),
            Start_Open=("next1_Open", "first"),
            Ende_Datum=("next2_Date", "last"),
            Ende_Open=("next2_Open", "last"),
            Close=("Close", "first"),
            Volume=("Volume", "first"),
            SL1=("sma_75", "first"),
            SL2=("sma_200", "first"),
            days=("days", "max"),
        )
        .reset_index()
        .sort_values("start")
        .set_index("start")
    )

    df["profit"] = (df.Ende_Open - df.Start_Open) / df.Start_Open * 100
    df["sum"] = df.profit.cumsum()

    print(df.profit.sum())
    df.to_csv("trades2.csv")
    df.to_csv("trades2b.csv", sep=";", decimal=",")
