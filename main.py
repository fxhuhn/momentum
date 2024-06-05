import pandas as pd
import yfinance as yf

from tools import get_stocks, get_symbols, rsi, sma, trade_report, trades_daily

"""
Screen stocks based on momentum indicators and generate trading signals.
"""


def filter(df: pd.DataFrame) -> pd.DataFrame:
    # Apply screening criteria
    df = df[
        (df["Close"] > 10)
        & (df["Volume"] > 1_000_000)
        & (df["atr"] > 2)
        & (df["atr"] < 6.5)
        & (df["aroon"] > 0)
        & (df["sma_200_pct"] > 0)
        & (df["rsi"] > 50)
        & (df["Close"] > df["sma_50"])
        & (df["sma_50"] > df["sma_200"])
    ]

    # df_signals = df_signals.sort_values("rsi")
    return df.sort_values("sma_200_pct")


def get_stock_signals(date):
    signals = []

    for symbol, df in dfs.items():
        df["rsi"] = rsi(df.Close, 20)
        try:
            signal = df.loc[signal_date].to_dict()
            signal["symbol"] = symbol
            signal["date"] = df.loc[signal_date].name
            signals.append(signal)
        except Exception:
            pass
    return signals


if __name__ == "__main__":
    START = "2010-01-01"
    trades = []
    last_day = None

    dfs = get_stocks(get_symbols().to_frame("symbol"))

    date_range = dfs[list(dfs.keys())[0]][START:].index
    spy = yf.download("spy")
    spy["Long"] = spy.Close > sma(spy.Close, 200)

    for signal_date in date_range:
        df_signals = pd.DataFrame()

        if spy.loc[signal_date].Long:
            signals = get_stock_signals(signal_date)
            df_signals = filter(pd.DataFrame(signals))

            # initial last day data
            if last_day is None:
                last_day = df_signals[-10:].copy()
                last_day["days"] = -1

            if len(last_day) > 0:
                keep = pd.merge(
                    df_signals[-15:], last_day[["symbol", "days"]], on="symbol"
                )
                keep["days"] += 1
            else:
                # no trades yesterday
                keep = pd.DataFrame()

            if len(keep) < 10:
                # add some new candidates
                df_signals = pd.concat(
                    [
                        keep,
                        pd.concat([keep, df_signals]).drop_duplicates(
                            subset="symbol", keep=False
                        )[len(keep) - 10 :],
                    ],
                    ignore_index=True,
                )
            else:
                df_signals = keep

            if len(df_signals) > 0:
                try:
                    df_signals["days"] = df_signals.days.fillna(0)
                except Exception:
                    df_signals["days"] = 0
                df_signals.loc[df_signals["days"] == 0.0, "start"] = df_signals["Date"]
            else:
                df_signals = pd.DataFrame()

        last_day = df_signals
        trades.append(df_signals)

    trades = pd.concat(trades, ignore_index=True)

    for symbol in trades.symbol.to_list():
        trades.loc[trades.symbol == symbol, "start"] = trades[
            trades.symbol == symbol
        ].start.ffill()

    # export Reports
    trades_daily(trades)
    trade_report(trades)
