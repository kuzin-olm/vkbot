# -*- coding: utf-8 -*-
from bot import Bot
from settings import tester_id, token, group_id


bot = Bot(token, group_id, tester_id)
bot.start()
