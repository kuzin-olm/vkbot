# -*- coding: utf-8 -*-

import peewee
# import peewee_async as apw
import datetime

from settings import psql_name_base, psql_params

import logging.config
from log_settings import LOGGER, LOGGER_STATE
logging.config.dictConfig(LOGGER)
log = logging.getLogger(LOGGER_STATE)


base = peewee.PostgresqlDatabase(psql_name_base, **psql_params)


class BaseModel(peewee.Model):
    class Meta:
        database = base


class User(BaseModel):
    uid = peewee.PrimaryKeyField(null=False)
    user_id = peewee.IntegerField(unique=True)
    username = peewee.CharField(default='')
    about_me = peewee.TextField(default='')

    created_at = peewee.DateTimeField(default=datetime.datetime.now())
    updated_at = peewee.DateTimeField(default=datetime.datetime.now())

    # if coflict create
    # create_ = peewee.TimestampField(column_name='create')
    # update_ = peewee.TimestampField(column_name='update')

    class Meta:
        order_by = ('created_at',)


class Bot(BaseModel):
    user = peewee.ForeignKeyField(User, to_field='uid')
    cmd = peewee.CharField()
    status = peewee.CharField()
    list_fio = peewee.TextField(default='{}')

    updated_at = peewee.DateTimeField(default=datetime.datetime.now())

    class Meta:
        order_by = ('updated_at',)


# class Message(BaseModel):
#     user = peewee.ForeignKeyField(User, to_field='id')
#     body = peewee.TextField()
#     send_date = peewee.DateTimeField(default=datetime.datetime.now)
#     # use server
#     # timestamp = peewee.DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
#
#     class Meta:
#         order_by = ('send_date',)

def get_user(user_id):
    try:
        user = User.get(User.user_id == int(user_id))
        return user
    except User.DoesNotExist:
        return False


def get_bot(user_id):

    user = get_user(user_id)

    if user:
        try:
            bot = Bot.get(Bot.user == user)
            return bot
        except Bot.DoesNotExist:
            return False
    return False


def create_user(user_id, username='', about='', cmd='', status=''):
    log.debug(f'запрос на создание нового юзера в БД: {user_id}')
    user = User(user_id=int(user_id), username=username, about_me=about)
    bot = Bot(user=user, cmd=cmd, status=status, list_fio='{}')

    try:
        user.save()
        bot.save()
        log.debug(f'новый юзер в БД создан: {user_id}')
        return get_bot(user_id)
    except peewee.IntegrityError:
        return False


def get_bot_or_create(user_id, username='', about='', cmd='', status=''):
    bot = get_bot(user_id)
    if not bot:
        bot = create_user(user_id, username, about, cmd, status)
        if not bot:
            return False
    return bot


def delete_user(user_id):

    user = get_user(user_id)
    bot = get_bot(user_id)
    if user and bot:
        user.delete_instance()
        bot.delete_instance()

        return True
    return False


def upd_user(user_id, username=None, about=None):

    user = get_user(user_id)

    if user:
        if username:
            user.username = username
        if about:
            user.about_me = about

        user.updated_at = datetime.datetime.now()
        user.save()
        return True
    return False


def upd_bot(user_id, cmd=None, status=None, list_fio=None):

    user = get_user(user_id)
    bot = get_bot(user_id)

    if user and bot:
        if cmd:
            bot.cmd = cmd
        if status:
            bot.status = status
        if list_fio:
            bot.list_fio = list_fio

        bot.updated_at = datetime.datetime.now()
        bot.save()
        log.debug(f'обновление в БД: {user_id} - {bot.cmd}, {bot.status}, {bot.list_fio}')
        return True
    return False


try:
    log.debug('тестовый коннект к БД')
    base.connect()
    log.debug('коннект к БД +')
except peewee.InternalError as err:
    log.exception(err)
finally:
    base.close()
    log.debug('закрыли коннект к ДБ')

if len(base.get_tables()) == 0:
    log.debug('не найдено никаких таблиц в БД')
    base.create_tables([User, Bot])
    log.debug('таблицы User и Bot созданы')

# for item in User.select():
#     print(item.uid, item.user_id, item.username, item.about_me)
# for item in Bot.select():
#     print(item.user.uid, item.user.user_id)
