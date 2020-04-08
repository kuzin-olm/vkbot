import json
import os

from my_lib import mercury, psql, my_excel

import logging.config
from log_settings import LOGGER, LOGGER_STATE
logging.config.dictConfig(LOGGER)
log = logging.getLogger(LOGGER_STATE)


cmd = 'ветрф'
default_cmd = 'бот'

# внутренние команды
c_exit = 'выйти'
c_edit = 'изменить'
c_run = 'запустить'
c_continue = 'продолжить'

# bot statuses
s_default = ' '
s_edit = 'редактирование'
s_proc = 'процесс'
s_auth = 'авторизовано'

# answers
a_start = 'введите через запятую: jsession, srv_id, дата_начало, дата_конец'
a_alarm = 'проверьте введеные jsession и srv_id и повторите попытку'
a_ok = 'ок'
a_fio = 'введите через запятую ФИО'
a_list_fio = 'список фильтра по ФИО:\n\n{}'
a_empty_fio = 'список фильтра по ФИО пуст, измените его'
a_checked_fio = 'есть в системе Меркурии:\n\n{}'
a_addition_checked_fio = '\n\nлибо введи новый список либо жми продолжить'
a_accept_fio = 'принял ФИО, запустить парсер?'
a_wrong_fio = 'данных ФИО в системе Меркурии нет, повторите'
a_auth = 'авторизовано: {}'
a_wrong = 'намекаю, все что после знака "=" jsession, srv_id\n' \
          'итог: jsession, srv_id, 26.08.2018, 25.09.2018\n' \
          'не шаришь? - тык "выйти"'
a_exit = 'чтобы завершить принудительно - выйдите из личного кабинета меркурии'
a_launch_question = 'запустить парсер?'
a_in_proc = 'парсер запущен'
a_reset = 'сброс статуса'
a_exit_lk_mercury = 'возможно вы вышли из меркурии'
a_wrong_cmd = 'кнопкииии'


def main(user_id, text, bot, h_queue):
    attach = None
    key_list = [c_exit]

    # если юзер вызывал ранее команду
    if bot.cmd == cmd:
        log.debug('вход в команду')

        answer, attach, key_list = handler_text(attach, bot, h_queue, key_list, text, user_id)

    # если это первый вызов команды
    else:
        log.debug('присвоение команды')
        psql.upd_bot(user_id=user_id, cmd=cmd)
        answer = a_start

    h_queue.put([user_id, answer, attach, key_list])
    # return user_id, answer, attach, key_list


# очень больное ветвление по статусам :(
def handler_text(attach, bot, h_queue, key_list, text, user_id):
    # если тольк первый раз зашли в команду, то ждем от него данные для авторизации
    if bot.status == s_default:
        log.debug('дефолтный статус')
        if text.lower() == c_exit:
            psql.upd_bot(user_id=user_id, cmd=default_cmd)  # bot.cmd = default_cmd
            answer = a_ok
            key_list = None
        # необходимо для авторизации 4 параметра через запятую
        elif len(text.split(',')) == 4:
            jsession, srv_id, *dates = list(map(str.strip, text.split(',')))

            log.debug(f'введены данные авторизации: {jsession}--{srv_id}--{dates}')
            sess = mercury.VetRF(session_id=jsession, srv_id=srv_id, cert_verify=True)
            page = sess.start()
            # проверка, что jsession srv_id валидны
            if page is not False and sess.auth_info(page.text):
                # читаем из бдшки сохраненные параметры
                params = json.loads(bot.list_fio)
                if 'fio' not in params.keys():
                    params.update({'fio': None})
                # запоминаем их, для дальнейшего использования
                params.update({'sess': [jsession, srv_id, *dates]})
                psql.upd_bot(user_id=user_id, status=s_auth, list_fio=json.dumps(params))

                answer = a_auth.format(sess.info(page.text))
                if params['fio'] is None:
                    answer = answer + '\n' + a_empty_fio
                else:
                    answer = answer + '\n' + a_list_fio.format('\n'.join(params['fio']))
                key_list = [c_run, c_edit, c_exit]
            # если данные не валидны, говорим чтобы перепроверили
            else:
                answer = a_alarm
        # намекаем на то, что получили не то, что ждали
        else:
            answer = a_wrong

    # если данные для авторизации подтверждены
    elif bot.status == s_auth:
        log.debug('статус подтвержденной авторизации')
        text = text.lower()
        if text == c_exit:
            # bot.cmd, bot.status = default_cmd, s_default
            psql.upd_bot(user_id=user_id, cmd=default_cmd, status=s_default)
            answer = a_ok
            key_list = None
        # запускаем парсер, предварительно считав данные, которые запомнили после авторизации
        elif text == c_run:
            params = json.loads(bot.list_fio)
            # если фильтр по ФИО пуст, то не запускаем парсер, говорим чтобы заполнили
            if params['fio'] is None:
                answer = a_empty_fio
                key_list = [c_run, c_edit, c_exit]
            # если есть ФИО для фильтра, то стартуем
            else:
                jsession, srv_id, date_start, date_end = params['sess']
                psql.upd_bot(user_id=user_id, status=s_proc)
                h_queue.put([user_id, a_in_proc, None, key_list])

                answer, attach = vet_rf(user_id, jsession, srv_id, date_start, date_end, params['fio'])
                key_list = None
        # если команда на изменение ФИО, изменяем статус (редактирование ФИО)
        elif text == c_edit:
            # bot.status = s_edit
            psql.upd_bot(user_id=user_id, status=s_edit)
            answer = a_fio
        # если не попали ни в какие команды, говорим что кнопки помогут
        else:
            key_list = [c_run, c_edit, c_exit]
            answer = a_wrong_cmd

    # если находимся в состоянии редактирования фильтра по ФИО
    elif bot.status == s_edit:
        log.debug('статус редактирования списка ФИО')
        text = text.lower()
        if text == c_exit:
            # bot.status = s_auth
            psql.upd_bot(user_id=user_id, status=s_auth)
            answer = a_launch_question
            key_list = [c_run, c_edit, c_exit]
        # выходим из статуса изменения, обратно в подтвержденную авторизацию
        elif text == c_continue:
            # bot.status = s_auth
            psql.upd_bot(user_id=user_id, status=s_auth)
            answer = a_accept_fio
            key_list = [c_run, c_edit, c_exit]
        # ожидаем список ФИО через запятую
        else:
            list_fio = text.split(',')
            list_fio = list(map(str.strip, list_fio))

            params = json.loads(bot.list_fio)
            jsession, srv_id, *other = params['sess']

            sess = mercury.VetRF(session_id=jsession, srv_id=srv_id)
            sess.start()
            # проверяем, есть ли такие ФИО в системе
            fio = list(filter(sess.get_user_info, list_fio))
            if any(fio):
                # если есть, то обновляем данные в бдшке
                params.update({'fio': fio})
                psql.upd_bot(user_id=user_id, list_fio=json.dumps(params))
                answer = a_checked_fio.format('\n'.join(fio))
                answer += a_addition_checked_fio
            else:
                answer = a_wrong_fio
            key_list = [c_continue, c_exit]

    # если выполняется парсер
    elif bot.status == s_proc:
        log.debug('статус выполнения парсера')
        text = text.lower()
        if text == c_exit:
            answer = a_exit
        else:
            answer = a_in_proc

    # перебздеж, если нет такого статуса в обработчике, сбрасываем на дефолтный
    else:
        # bot.status = s_default
        psql.upd_bot(user_id=user_id, status=s_default)
        answer = a_reset
    return answer, attach, key_list


def vet_rf(user_id, j_session, srv_id, date_start, date_to, fio_list: list):
    sess = mercury.VetRF(session_id=j_session, srv_id=srv_id, cert_verify=True)

    # сбор вет номеров
    out_list_result = []

    try:
        sess.body_v3(date_start, date_to, out_list_result, fio_list)
    except Exception as err:
        log.exception(err)
        # bot.cmd, bot.status = 'bot', s_default
        psql.upd_bot(user_id=user_id, cmd=default_cmd, status=s_default)
        return a_exit_lk_mercury, None

    folder = 'docs'
    try:
        os.mkdir(folder)
    except FileExistsError:
        # ну есть папка и фиг с ней
        pass

    filename = 'vetrf_{}.xlsx'.format(user_id)
    filename = os.path.join(folder, filename)
    # df.to_excel(filename, index=False)  # , engine='xlsxwriter') #encoding= 'cp1251'
    # сбор закончен, формирование excel файла

    result_df, quantity_docs = my_excel.counter_docs(list_vet_doc=out_list_result)
    result_df.to_excel(filename, float_format='%i')

    answer = f'всего вет.номеров: {quantity_docs}'
    attach = {'doc': [filename]}

    # bot.cmd, bot.status = 'bot', s_default
    psql.upd_bot(user_id=user_id, cmd=default_cmd, status=s_default)

    # res_queue.put([answer, attach])
    return answer, attach
