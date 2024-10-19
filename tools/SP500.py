import os

import pandas as pd


class SP500Stocks:
    # df = None

    def __init__(self, filename: str = "./S&P_500_Historical_08-17-2024.csv") -> None:
        if not os.path.isfile(filename):
            raise FileNotFoundError(f"The file '{filename}' does not exist.")

        self.df = pd.read_csv(filename, index_col="date", parse_dates=True)

        self.df = self.df[self.df.index >= "2000-01-01"]
        self.df["tickers"] = self.df["tickers"].str.split(",").map(sorted)

    def get_symbols(self, year: int, month: int, day: int = 1) -> list[str]:
        if self.df is None:
            return []

        date = pd.Timestamp(int(year), int(month), int(day))
        df2 = self.df[self.df.index <= date]
        return df2.iloc[-1].tickers if not df2.empty else []

    def all_symbols(self) -> list[str]:
        return sorted(set(symbol for tickers in self.df.tickers for symbol in tickers))


stocks = SP500Stocks()


if __name__ == "__main__":
    print(stocks.get_symbols(2024, 8, 17))
    print(stocks.all_symbols())
