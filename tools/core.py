import pandas as pd


def load_stocks(symbols):
    return yf.download(symbols, start="2000-01-01", group_by="ticker", rounding=True)


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


def strategy(df) -> pd.DataFrame:
    MAX_TICKER = 10
    QUANTILE_LOW_MOMENTUM = 0.6
    QUANTILE_HIGH_MOMENTUM = 0.85

    def lower_quantile(df: pd.DataFrame, column, threshold):
        df = df[column]
        ticker = df[df <= df.quantile(threshold)].index
        return list(ticker)

    def higher_quantile(df: pd.DataFrame, column, threshold):
        df = df[column]
        ticker = df[df >= df.quantile(threshold)].index
        return list(ticker)

    def trendless(df: pd.DataFrame):
        df = df[["last_Close", "SMA"]].copy()
        ticker = df[df.last_Close <= df.SMA].index
        return list(ticker)

    def downtrend(df):
        df = df[["ROC_7"]]
        ticker = df[df.ROC_7 <= 0].index
        return list(ticker)

    def volatility(df: pd.DataFrame):
        df = df["STD_12"].copy()
        ticker = df[df >= df.quantile(0.2)].index
        return list(ticker)

    def performance(df: pd.DataFrame):
        df = df["ROC_12"].copy()
        ticker = df[df <= df.quantile(0.2)].index
        return list(ticker)

    ticker = []

    ticker = ticker + performance(df)
    ticker = ticker + volatility(df)
    ticker = ticker + trendless(df)
    ticker = ticker + downtrend(df)

    ticker = list(set(df.index.unique()) - set(ticker))

    # choose random ticker

    if len(df.loc[ticker]["ROC_12"]) > 10:
        return df.loc[ticker]["ROC_12"].sample(MAX_TICKER).index
    else:
        return df.loc[ticker]["ROC_12"].index

    # return df.loc[ticker]["ROC_12"].nsmallest(MAX_TICKER).index
    # return df.loc[ticker]["ROC_12"].nlargest(MAX_TICKER).index
