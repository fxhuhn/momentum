import datetime
import os
import pickle
from typing import Dict, List

import pandas as pd
import yfinance as yf

from .calc import aroon, atr, rsi, sma


def get_symbol_metadata(symbol: str) -> Dict[str, str]:
    """
    Returns sector and country of the given stock symbol.

    Args:
        symbol (str): Stock symbol.

    Returns:
        Dict[str, str]: Dictionary containing sector, country, and industry of the stock.
    """
    stock_metadata = yf.Ticker(symbol).info
    return {
        "sector": stock_metadata.get("sector"),
        "country": stock_metadata.get("country"),
        "industry": stock_metadata.get("industry"),
    }


def get_symbols() -> List[str]:
    """
    Fetches stock symbols from Alpha Vantage and filters them for NASDAQ and NYSE.

    Returns:
        List[str]: List of filtered stock symbols.
    """
    URL: str = "https://www.alphavantage.co/query?function=LISTING_STATUS&apikey=demo"
    filename: str = "./data/stocks.pkl"

    try:
        symbols = pd.read_pickle(filename)
    except FileNotFoundError:
        stocks = pd.read_csv(URL)
        symbols = stocks.query(
            'exchange in ["NASDAQ", "NYSE"] and assetType == "Stock"'
        ).symbol

        for index, row in symbols.items():
            if "-" in str(row) or "/" in str(row) or "-" in str(row):
                symbols.drop(index)
            else:
                try:
                    symbol_metadata = get_symbol_metadata(row)
                    if symbol_metadata["country"] != "United States":
                        symbols.drop(index)
                except Exception:
                    pass

        symbols.to_pickle(filename)

    return symbols


def fetch_and_prepare(symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Fetches stock data from Yahoo Finance and prepares it by removing unclear items and NaNs.

    Args:
        symbols (List[str]): List of stock symbols to fetch data for.

    Returns:
        Dict[str, pd.DataFrame]: A dictionary where keys are stock symbols and values are their corresponding dataframes.
    """

    prepared_data = {}
    for _, group in symbols.groupby(symbols.symbol.str[0]):
        stock_data = yf.download(
            group.symbol.values.tolist(),
            rounding=2,
            progress=False,
            group_by="ticker",
            start="2000-01-01",
        )

        # perform some pre preparation
        for symbol in stock_data.columns.get_level_values(0).unique():
            # drop unclear items
            df = stock_data[symbol]
            df = df[~(df.High == df.Low)]
            df = df.dropna()
            df.index = pd.to_datetime(df.index)
            df = prepare_stockdata(df)

            if not df.empty:
                prepared_data[symbol.lower()] = df
    return prepared_data


def get_stocks(symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Fetches stock data for the given list of symbols. If cached data is older than 12 hours, it fetches new data from Yahoo Finance.

    Args:
        symbols (List[str]): List of stock symbols to fetch data for.

    Returns:
        Dict[str, pd.DataFrame]: A dictionary where keys are stock symbols and values are their corresponding dataframes.
    """
    filename: str = "./data/yahoo.pkl"
    dfs = {}

    try:
        # Check if the cached file exists and is not older than 12 hours
        file_time = os.path.getmtime(filename)
        file_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(file_time)

        # Load cached data
        with open(filename, "rb") as file:
            dfs = pickle.load(file)

        if file_age.days > 0 or file_age.seconds / 3600 > 12:
            symbols = dfs.keys().to_frame("symbol")
            raise FileNotFoundError

    except FileNotFoundError:
        # Fetch new data if the cached file is not found or is too old
        dfs = fetch_and_prepare(symbols)

        # Save the new data to the cache
        with open(filename, "wb") as file:
            pickle.dump(dfs, file)

    return dfs


def prepare_stockdata(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares stock data by calculating various technical indicators.

    Args:
        df (pd.DataFrame): DataFrame containing stock data with 'Close', 'High', 'Low', 'Open', and 'Volume' columns.

    Returns:
        pd.DataFrame: DataFrame with calculated technical indicators.
    """

    df["Date"] = df.index
    df["next1_Date"] = df["Date"].shift(-1)
    df["next2_Date"] = df["Date"].shift(-2)
    df["next1_Open"] = df["Open"].shift(-1)
    df["next2_Open"] = df["Open"].shift(-2)

    df["sma_200"] = sma(df["Close"], 200)
    df["sma_50"] = sma(df["Close"], 50)

    df["sma_200_pct"] = df.sma_200.pct_change(200, fill_method=None)

    df["Volume_sma_20"] = sma(df["Volume"], 20)

    df["atr"] = atr(df, 20) / df["Close"] * 100
    df["rsi"] = rsi(df.Close, 20)
    df["aroon"] = aroon(df["High"], df["Low"], 20)

    return df.dropna()
