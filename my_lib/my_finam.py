# -*- coding: utf-8 -*-

# import asyncio
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# from my_libr.fin import Exporter, Market, Timeframe, FinamParsingError

from finam.export import Exporter, Market, Timeframe, FinamParsingError

from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()

# sber долгосрок [12, 21, 10]
# SHARES = {'sber': [14, 46, 8]}

with open('period.json', 'r') as file:
    SHARES = json.load(file)


def get_shares(code=None, start_date=None, end_date=None):
    if code:
        code = code.upper()

    exporter = Exporter()

    # все акции в пандас таблице из финама
    items = exporter.lookup(market=Market.SHARES)
    share_id = items[items.code == code]

    if share_id.empty:
        return None
    else:
        share_id = share_id.index[0]
        temp = exporter.download(share_id,
                                 Market.SHARES,  # акции
                                 start_date=start_date,
                                 end_date=end_date,
                                 timeframe=Timeframe.DAILY)
        temp.reset_index(inplace=True)
        temp.columns = [x[1:-1].lower() for x in temp.columns]
        temp.rename(columns={'nde': 'timestamp'}, inplace=True)

        return temp


def macd(data, period=None):
    if period is None:
        period = [12, 26, 9]

    df = data.copy()
    ma_fast = df['close'].ewm(span=period[0], adjust=False).mean()
    ma_slow = df['close'].ewm(span=period[1], adjust=False).mean()
    df['macd'] = ma_fast - ma_slow
    df['macd_signal'] = df['macd'].ewm(span=period[2], adjust=False).mean()
    # macd hist
    df['macd_hist'] = df['macd'] - df['macd_signal']
    # ---------------------------------------------------------------
    return df


def rsi(data, period=14):
    df = data.copy()

    delta = df['close'].diff()

    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0

    gain = up.ewm(span=period, adjust=False).mean()
    loss = down.abs().ewm(span=period, adjust=False).mean()

    rs = gain / loss

    df['rsi'] = pd.Series(100 - (100 / (1 + rs)))
    df['rsi'].fillna(method='bfill', inplace=True)

    return df


def my_filtr(data, filtr=1):
    df = data.copy()
    # проверка на тренд по трем точкам гистограммы
    df['shift_1'] = df['macd_hist'].shift(1)
    df['shift_2'] = df['macd_hist'].shift(2)
    df['shift_3'] = df['macd_hist'].shift(3)

    # плюс фильтр trend_h, чтобы отсеивать шум
    df['trend_up'] = (df['shift_1'] > filtr) & (df['macd_hist'] > df['shift_1']) & (df['shift_1'] > df['shift_2']) & (
            df['shift_2'] > df['shift_3'])
    df['trend_down'] = (df['shift_1'] < -filtr) & (df['macd_hist'] < df['shift_1']) & (
            df['shift_1'] < df['shift_2']) & (df['shift_2'] < df['shift_3'])
    df.drop(['shift_1', 'shift_2', 'shift_3'], axis=1, inplace=True)

    # если получили петлю после некоего продолжительного тренда(up/down), то можем предположить покупку/продажу
    df['sell'] = (df['trend_up'].shift(1) == True) & (df['trend_up'] == False)
    df['buy'] = (df['trend_down'].shift(1) == True) & (df['trend_down'] == False)
    df.drop(['trend_up', 'trend_down'], axis=1, inplace=True)

    df['pr'] = (df['macd_hist'] >= 0) & (df['macd_hist'].shift(1) < 0)

    #     buy_to_insure = []
    #     check = False
    #     for index,row in df.iterrows():
    #         if row['buy']:
    #             check = True
    #         elif row['pr'] and not check:
    #             check = True
    #         elif row['pr'] and check:
    #             buy_to_insure.append(True)
    #             check = False
    #             continue
    #         elif row['sell'] and check:
    #             check = False
    #         buy_to_insure.append(False)

    #     df['buy_to_insure'] = buy_to_insure

    # pandas way
    df['temp'] = np.NaN
    df.loc[df.buy, 'temp'] = True
    pr_shift = df.pr.shift().fillna(False)
    df.loc[pr_shift, 'temp'] = True
    df.loc[df.sell, 'temp'] = False
    df.temp.fillna(method='ffill', inplace=True)
    df.temp.fillna(False, inplace=True)

    df['buy_to_insure'] = False
    df.loc[(df.temp & df.pr), 'buy_to_insure'] = True
    df.drop(['temp'], axis=1, inplace=True)

    return df


def trade(data, val=3, commission=0.003, month_pay=99):
    df = data.copy()

    # ---------
    df = df[df['buy_to_insure'] | df['sell']]  # [['timestamp', 'close', 'buy_to_insure', 'sell']]
    sell_shift = df['sell'].shift()
    df = df[~(df['sell'] & sell_shift)]
    df = df[df['buy_to_insure'] != df['buy_to_insure'].shift()]
    # ---------

    df['close_val'] = df['close'] * val

    df['commission'] = df['close_val'] * commission
    df['profit'] = df['close_val'].diff()
    df.loc[df['buy_to_insure'], 'profit'] = 0

    df['profit'] = df['profit'] - df['commission']
    df.loc[df['buy_to_insure'], 'profit'] *= -1
    df['profit'] = df['profit'].diff()
    df.loc[df['buy_to_insure'], 'profit'] = 0

    df['perc'] = df['profit'] / df['close_val'].shift() * 100

    df['acc_profit'] = df['profit'].cumsum().fillna(0)
    df['acc_perc'] = df['perc'].cumsum().fillna(0)

    df['max_acc_profit'] = np.maximum.accumulate(df['acc_profit'])
    df['max_acc_perc'] = np.maximum.accumulate(df['acc_perc'])

    df['lose'] = (df['max_acc_profit'] - df['acc_profit'])

    #     timestamp_month = df['timestamp'].apply(lambda x: x.month)
    timestamp_month = df['timestamp'].dt.month
    df['month_pay'] = 0
    df.loc[timestamp_month != timestamp_month.shift(), 'month_pay'] = month_pay
    df['acc_month_pay'] = df['month_pay'].cumsum().fillna(0)

    df['result'] = df['profit'] - df['month_pay']
    df['result'] = df['result'].cumsum().fillna(0)
    df['result_perc'] = ((df['profit'] - df['month_pay']) / df['close_val'].shift() * 100).cumsum().fillna(0)

    df['max_result_perc'] = np.maximum.accumulate(df['result_perc'])
    # df['real_lose'] = (df['max_result_perc'] - df['result_perc'])

    return df


def save_plot(df, test, name='plotly.jpg'):
    dff_buy = test[test.buy_to_insure]
    dff_sell = test[test.sell]

    fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, figsize=(20, 18))  # default (20,6)

    ax1.plot(df.timestamp, df.close)
    ax1.plot_date(dff_buy.timestamp, dff_buy.close, color='green')
    ax1.plot_date(dff_sell.timestamp, dff_sell.close, color='red')
    ax1.grid()
    ax1.set_title('Изменение цены акции', {'fontsize': 25})

    ax2.plot(test.timestamp, test.acc_profit, linewidth=1, color='red', label='профит')
    ax2.plot(test.timestamp, test.max_acc_profit, linewidth=0.5, label='масимальный зафиксированный профит')
    ax2.plot(test.timestamp, test.result, linewidth=3, color='g', label='реальный профит с учетом комиссий')
    ax2.grid()
    ax2.legend(loc='upper left')
    ax2.set_title('Профит в денежном эквиваленте', {'fontsize': 25})

    ax3.plot(test.timestamp, test.acc_perc, linewidth=1, color='red', label='профит')
    ax3.plot(test.timestamp, test.max_result_perc, linewidth=0.5, label='масимальный зафиксированный профит')
    ax3.plot(test.timestamp, test.result_perc, linewidth=3, color='g', label='реальный профит с учетом комиссий')
    ax3.grid()
    ax3.legend(loc='upper left')
    ax3.set_title('Профит в процентах', {'fontsize': 25})

    plt.savefig(name)
    plt.close('all')
