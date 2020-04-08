# -*- coding: utf-8 -*-
from my_lib import psql
from command import list_cmd

import threading
from queue import Queue, Empty
import time

# from random import choice
# from enum import Enum

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.upload import VkUpload

import logging.config
from log_settings import LOGGER, LOGGER_STATE

logging.config.dictConfig(LOGGER)
log = logging.getLogger(LOGGER_STATE)


class Bot:

    def __init__(self, token: str, group_id: int, testers=None):
        """
        основной класс бота

        :param token: токен группы со всеми разрешениями
        :param group_id: id группы к которой привязн токен
        :param testers: список из id тестеров
        """

        self.group_id = group_id
        self.testers = testers
        self.vk_session = vk_api.VkApi(token=token, api_version='5.85',
                                       scope='MESSAGE, DOCS, PHOTOS, OFFLINE')

        self.upload = VkUpload(self.vk_session)  # self.vk_session_me
        self.longpoll = VkBotLongPoll(self.vk_session, self.group_id, wait=25)

        self.vk = self.vk_session.get_api()

        self.cmd_keyboard = self.c_keyboard(list(list_cmd.keys()))
        self.exit_keyboard = self.c_keyboard(list('выйти'))
        self.first_run = True

        self.outgoing_mess_queue = Queue()

    def send(self, user_id, message, **kwargs):
        self.vk.messages.send(user_id=user_id, message=message, **kwargs)

    def c_keyboard(self, key_list, one_time=False):
        """
        генерирует клавиатуру (из переданного списка) с 3мя кнопками в одной строке

        :param key_list: список кнопок, которые хоти видеть
        :param one_time: True если хотим видеть одноразовый вызов клавиатуры

        :return: объект VkKeyboard для последующего вызова
        """

        color = VkKeyboardColor.DEFAULT
        keyboard = VkKeyboard(one_time=one_time)
        len_key_list = len(key_list)
        for item in key_list:
            # TODO цвета как-нибудь бы передать
            if item == 'выйти':
                # color = VkKeyboardColor.NEGATIVE
                keyboard.add_button(item, color=VkKeyboardColor.NEGATIVE, payload='')
            else:
                keyboard.add_button(item, color=color, payload='')

            if (key_list.index(item) + 1) % 3 == 0 and key_list.index(item) != len_key_list - 1:
                keyboard.add_line()
        return keyboard

    def run(self):
        """
        запускает бесконечный цикл в котором слушаем сервер,
        при получении инфы от сервера запускаем поток с обработчиком

        :return:
        """
        queue_thread = threading.Thread(target=self.outgoing_mess_queue_handler)
        queue_thread.start()

        log.debug('слушаем сервер')
        for event in self.longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW and event.obj.text:  # and event.to_me and event.text
                text = event.obj.text
                user_id = event.obj.peer_id
                handler = threading.Thread(target=self.handler_mess, args=(user_id, text))  # event.user_id, event.text
                handler.start()
                log.debug('запущен поток для обработки')
            time.sleep(0.05)

    def start(self):
        """
        команда для старта бота
        при старте оповещает тестеров, что бот запустился

        :return:
        """

        log.debug('старт бота')
        if self.testers and self.first_run:
            log.debug('оповещание тестеров')
            self.first_run = False
            [self.send(user_id=t_id, message='йа запустилсо ┐( ˘_˘)┌') for t_id in self.testers]

        try:
            self.run()
        except Exception as e:
            log.exception(e)
            self.start()

    def outgoing_mess_queue_handler(self):
        """
        обработчик исходящих сообщений
        в очередь скидываются результаты работы функции handler_mess для ответа юзеру

        :return:
        """
        while True:
            try:
                user_id, mess, attach, key_list = self.outgoing_mess_queue.get(timeout=0.1)
            except Empty:
                time.sleep(0.1)
                continue

            # чтобы загружать файлы ВК в прикреплёнке не в функции обработчике, а в основном теле
            # необходимо в аттач складывать dict('тип ВК прикрепления' = [массив ссылок на файлы, ...], ...)
            if attach:
                all_attach = list()
                photo = 'photo'
                doc = 'doc'

                if photo in attach.keys():
                    log.debug(f'{user_id} есть фото в аттаче')
                    for f in attach[photo]:
                        data = self.upload.photo_messages(photos=f, peer_id=user_id)[0]
                        log.debug(f'{user_id} загружено фото: {f}')
                        att = 'photo{}_{}'.format(data['owner_id'], data['id'])
                        all_attach.append(att)

                if doc in attach.keys():
                    log.debug(f'{user_id} есть документ в аттаче')
                    for d in attach[doc]:
                        data = self.upload.document_message(d, title=f'doc_{user_id}', peer_id=user_id)[0]
                        log.debug(f'{user_id} загружен документ: {d}')
                        att = 'doc{}_{}'.format(data['owner_id'], data['id'])
                        all_attach.append(att)

                attach = all_attach

            # после того как получим нормальный сформированный аттач и текст для ответа
            # создадим клаву и отправим все это
            keyboard = self.c_keyboard(key_list) if key_list else self.cmd_keyboard
            self.send(user_id=user_id, message=mess, keyboard=keyboard.get_keyboard(), attachment=attach)

    def handler_mess(self, user_id, text):
        """
        обработчик входящих сообщений
        в папке /command/ лежат файлы с обработчиками комманд
        my_func переопределяет функцию из list_cmd


        :param user_id: кто написал сообщение
        :param text: текст сообщения

        :return:
        """

        # можно пометить сразу, что прочитали, но тогда при долгом ответе покажется, что мы зависли :)
        # self.vk.messages.markAsRead(peer_id=user_id)

        log.debug('запрос к БДшке')
        bot = psql.get_bot_or_create(user_id, username='', about='', cmd='бот', status=' ')
        # text = text.lower()

        if bot.cmd != 'бот':
            # если текущая команда пользователя != дефолтной, т.е. он находится в какой-то другой
            # то вызываем тот обработчик, на котором он находится
            log.debug(f'{user_id} текущее состояние: {bot.cmd}')
            my_func = list_cmd[bot.cmd]
        else:
            # если у пользователя нет текущей команды (т.е. дефолтная), то смотрим какие есть у нас
            if text in list_cmd.keys():
                # если такая есть, то вызываем ее
                log.debug(f'{user_id} вызвал команда: {text}')
                my_func = list_cmd[text]
            else:
                # если у нас нет такой команды, то намекаем, что надо выбрать из того, что есть (дефолтная клава)
                log.debug(f'{user_id} вызвал не существующую команду: {text}')
                self.send(user_id=user_id, message='выбирай', keyboard=self.cmd_keyboard.get_keyboard())
                return

        my_func(user_id, text, bot, self.outgoing_mess_queue)

        return
