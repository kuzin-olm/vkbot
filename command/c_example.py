from io import BytesIO

from my_lib import psql
import requests

# основная команда, по которой запускается обработка
cmd = 'аватарка'

c_exit = 'выйти'


def main(user_id, text, bot, h_queue):
    """
    основная функция имя всегда должно быть 'main'
    список параметров не должен меняться

    :param h_queue:
    :param user_id: id вк пользователя
    :param text: сообщение, которое необходимо обработать
    :param bot: объект из БД  с состояниями bot.cmd и bot.status

    :return: id вк пользователя, текст ответа, какие либо прикрепления, список кнопок (которые надо будет показать)
    """
    text = text.lower()

    attach = None
    key_list = [c_exit]

    if bot.cmd == cmd:

        if text == c_exit:
            # так изменяется состояние юзера в БД
            psql.upd_bot(user_id=user_id, cmd='бот')
            answer = 'ок'
            key_list = None
        else:
            img = get_avatar(text)
            # так должен выглядеть аттач
            attach = {'photo': [img]}
            answer = 'если напишешь другое, то морда поменяется :)'

    else:
        answer = 'отправь рандомное слово ;)'
        psql.upd_bot(user_id=user_id, cmd=cmd)

    h_queue.put([user_id, answer, attach, key_list])
    # return user_id, answer, attach, key_list


def get_avatar(text):
    """
    рандомная морда с http://avatars.adorable.io

    :param text:  любой текст
    :return: картинка в байтовом представлении
    """
    size = 285
    response = requests.get(f'https://api.adorable.io/avatars/{size}/{text}')
    img = BytesIO(response.content)
    return img
