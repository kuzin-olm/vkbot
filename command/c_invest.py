from my_lib import psql, my_finam

import datetime
import os.path

import logging.config
from log_settings import LOGGER, LOGGER_STATE
logging.config.dictConfig(LOGGER)
log = logging.getLogger(LOGGER_STATE)

cmd = 'инвестиции'
default_cmd = 'бот'

c_exit = 'выйти'
c_tickers = ['sber', 'five']


def main(user_id, text, bot, h_queue):

    text = text.lower()
    attach = None
    key_list = [*c_tickers, c_exit]

    if bot.cmd == cmd:

        if text == c_exit:
            psql.upd_bot(user_id=user_id, cmd=default_cmd)
            answer = 'ок'
            key_list = None

        elif text in c_tickers:
            try:
                answer, attach = get_finam(user_id=user_id, ticker=text)
            except Exception as err:
                log.exception(err)
                answer = 'упс... не удалось получить данные с finam`а'

        else:
            answer = 'введи тикер'

    else:
        answer = 'доступные тикеры в клавиатуре'
        psql.upd_bot(user_id=user_id, cmd=cmd)

    h_queue.put([user_id, answer, attach, key_list])
    # return user_id, answer, attach, key_list


def get_finam(user_id, ticker):
    log.debug(f'{user_id}: тикер определен - {ticker}')
    day_now = datetime.datetime.now()

    log.debug(f'{user_id}: загрузка исторических данных - {ticker}')
    df = my_finam.get_shares(code=ticker, start_date=datetime.date(2017, 1, 1), end_date=day_now)
    log.debug(f'{user_id}: данные загружены - {ticker}')

    df = my_finam.macd(df, period=my_finam.SHARES[ticker])
    df = my_finam.my_filtr(df)
    log.debug(f'{user_id}: применена стратегия к - {ticker}')

    test = my_finam.trade(
        df,  # исходные данные с индикаторами
        val=int(30),  # кол-во акций
        commission=float(0.3) / 100,  # коммисия за сделку в %
        month_pay=float(99)  # месячная подписка
    )
    log.debug(f'{user_id}: тест стратегии - {ticker}')

    ans = 'тест на истории: брокер Тинькофф, кол-во акций 30 шт.\n\n'
    answer = 'максимальная просадка: {}% \n' \
             'максимальный профит: {}%\n' \
             'текущий профит: {}%\n' \
             'цена акции при последней покупке: {}\n' \
             'цена акции при последней продаже: {}'.format(
                                                    round(test['lose'].max() / test['acc_profit'].max() * 100, 2),
                                                    round(test['result_perc'].max(), 2),
                                                    round(test['result_perc'].values[-1], 2),
                                                    round(test[test.buy_to_insure]['close'].values[-1], 2),
                                                    round(test[test.sell]['close'].values[-1], 2)
                                                )
    answer = ans + answer

    name = f'plotly_{user_id}_{datetime.datetime.timestamp(day_now)}.png'

    folder = 'photos'
    try:
        os.mkdir(folder)
    except FileExistsError:
        # ну есть папка и фиг с ней
        pass
    name = os.path.join(folder, name)

    my_finam.save_plot(df, test, name)
    log.debug(f'{user_id}: сохраннена фотография - {ticker} - {name}')

    attach = {'photo': [name]}

    return answer, attach
