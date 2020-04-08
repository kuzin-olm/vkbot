# -*- coding: utf-8 -*-
from threading import Thread
from queue import Queue
import requests as rq
from time import sleep, clock
import bs4
from settings import firm_list

import logging.config
from log_settings import LOGGER, LOGGER_STATE
logging.config.dictConfig(LOGGER)
log = logging.getLogger(LOGGER_STATE)

headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip,deflate,sdch',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36'
}


class VetRF:
    '''
    для работы с сайтом 'mercury.vetrf.ru/gve/' личный кабинет
    требуется id сервака и токен сессии
    '''

    def __init__(self, session_id=None, srv_id=None, cert_verify=True):
        assert type(session_id) is str, 'not string input: session_id'
        assert type(srv_id) is str, 'not string input: srv_id'

        self.url = 'https://mercury.vetrf.ru/gve/operatorui'
        self.proxies = None

        self.cookies = {'JSESSIONID': session_id, 'srv_id': srv_id}
        self.session = rq.Session()
        self.session.verify = cert_verify
        self.session.headers = headers
        # для потоков
        # типы вет док-ов
        self.actions = ['VetDocumentAjax', 'ProducedVetDocumentAjax', 'RawMilkVetDocumentAjax']
        # очередь для обработки сырого текста после поиска
        self.queue_for_doc = Queue()
        # очередь для обработки номеров вет.доков
        self.queue_out = Queue()

    # загрузка начальной страницы (можно не использовать)
    def start(self):
        try:
            return self.session.get(self.url,
                                    params={'_action': 'login', '_language': 'ru'},
                                    cookies=self.cookies,
                                    proxies=self.proxies)
        except UnicodeEncodeError:
            return False

    # выцепляет под кем залогинились
    @staticmethod
    def info(html):
        bs = bs4.BeautifulSoup(html, "html5lib").find('div', {'id': 'loggedas'}).text.split()
        user = ' '.join(bs[1:5])
        return user

    # проверка зашли ли мы в систему
    @staticmethod
    def auth_info(html):
        try:
            bs4.BeautifulSoup(html, "html5lib").find('div', {'id': 'loggedas'}).text.split()
        except AttributeError:
            return False
        return True

    # возврат на домашнюю страницу
    def home(self):
        self.session.get(self.url,
                         params={'_action': 'home', '_language': 'ru'},
                         cookies=self.cookies,
                         proxies=self.proxies)

    # получаем ФИО и id из системы
    def get_user_info(self, name=''):
        assert type(name) is str, 'not string input: nameFinder'
        response = self.session.post(self.url,
                                     params={'_action': 'listVUUsersJson', '_language': 'ru'},
                                     data={'template': name, 'pageList': ''},
                                     cookies=self.cookies,
                                     proxies=self.proxies)
        res = response.json()['results']
        if len(res) > 0:
            return res[0]['text'], res[0]['id']
        else:
            return False

    # страница выбора предприятий (некое состояние)
    def change_corp(self):
        return self.session.get(self.url,
                                params={'_action': 'changeServicedEnterprise', '_language': 'ru'},
                                cookies=self.cookies,
                                proxies=self.proxies)

    # выбор предприятия
    def set_corp(self, corp_value):
        self.session.get(self.url,
                         params={'enterprisePk': corp_value, '_action': 'chooseServicedEnterprise', '_language': 'ru'},
                         cookies=self.cookies,
                         proxies=self.proxies)

    # получает имя предприятия и его id(value) с home или start
    @staticmethod
    def get_corp_list(response):
        corp_list = []
        response = bs4.BeautifulSoup(response, "html5lib")
        table = response.find_all('tbody')[0].find('tr').find_all('tr')
        if table is not None:
            for item in table:
                name = ''
                item = item.find_all('td')
                value = item[0].find('input').get('value')
                name_1 = item[1].text.strip().split()
                while True:
                    if ')' in name_1[-1]:
                        name = ' '.join(name_1)
                        break
                    else:
                        name_1 = name_1[:-1]
                        if len(name_1) == 0:
                            break
                corp_list.append({'name': name,
                                  'value': value})
            return corp_list
        else:
            log.debug('список предприятий пуст')
            return []

    # переход на страницу вет документов/производственных/молочки по action
    def list_viewer_doc(self, action):
        self.session.post(self.url,
                          params={'_action': action, 'all': 'true'},
                          data={'rows': '100', '_action': 'list' + action, '_language': 'ru'},
                          cookies=self.cookies,
                          proxies=self.proxies)
        self.session.post(self.url,
                          data={'rows': '100', '_action': 'list' + action, '_language': 'ru'},
                          cookies=self.cookies,
                          proxies=self.proxies)

    # поиск документов среди одного предприятия по дате,виду action, и возм. ФИО
    def find_doc(self, corp_name, date_begin, date_end, action, page=1, name_id='null', firm_id='', firm_name=''):
        if action == 'RawMilkVetDocumentAjax':
            return self.session.post(self.url,
                                     data={'senderEnterprise.name': corp_name, 'firm': firm_id,
                                           'traffic.firm.name': firm_name,
                                           'findStateSet': [1, 7, 3], 'vetDocumentDate': date_begin,
                                           'vetDocumentDateTo': date_end,
                                           'whoGeneral': name_id, 'findUserSet': [4, 2, 3], 'productType': 5,
                                           'product': 26, 'pageList': page, 'find': 'true', '_action': 'find' + action,
                                           'request': 'false', '_language': 'ru'},
                                     cookies=self.cookies,
                                     proxies=self.proxies).text
        elif action in ['VetDocumentAjax', 'ProducedVetDocumentAjax']:
            return self.session.post(self.url,
                                     data={'senderEnterprise.name': corp_name, 'firm': firm_id,
                                           'traffic.firm.name': firm_name,
                                           'findStateSet': [1, 7, 3], 'vetDocumentDate': date_begin,
                                           'vetDocumentDateTo': date_end,
                                           'whoGeneral': name_id, 'findUserSet': [4, 2], 'pageList': page,
                                           'find': 'true', '_action': 'find' + action, 'request': 'false',
                                           '_language': 'ru'},
                                     cookies=self.cookies,
                                     proxies=self.proxies).text

    # со страницы ответа поисковика выцепляет все номера вет.доков
    @staticmethod
    def list_number_doc(find_docs=None):
        list_nd = []
        list_doc = bs4.BeautifulSoup(find_docs, "html5lib").find_all('input', {'name': 'vetDocumentPk'})
        if list_doc is not None:
            [list_nd.append(item.get('value')) for item in list_doc]
        return list_nd

    # на странице поиска ищет слово "Следующая"
    @staticmethod
    def word_next_finder(find_doc):
        doc_page = bs4.BeautifulSoup(find_doc, "html5lib").find('div', {'class': 'pagenavBlock'})
        if doc_page is not None:
            if doc_page.find('a') is not None:
                #             if Doc.find('a').text == 'Следующая': return True
                if doc_page.find_all('a')[-1].text == 'Следующая':
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

    # добавлена очередь для многопоточности, кидает текст в эту очередь и метку для обработки
    def get_full_list_vet_doc(self, corp_value, corp_name, action, date_begin, date_end,
                              name_id='null', firm_id='', firm_name=''):

        self.list_viewer_doc(action)
        find_docs = self.find_doc(corp_name, date_begin, date_end, action,
                                  page=1, name_id=name_id, firm_id=firm_id, firm_name=firm_name)

        # list_nd = self.list_number_doc(find_docs)
        # если надо обработать по дополнительным предприятиям
        mod_handler = False  # 0 if len(firm_name) > 2 else False   # what??!?!?))
        # складываем в очередь страницу ответа, чек для доп.обр., и "где нашли"
        self.queue_for_doc.put([find_docs, mod_handler, action])

        word_next = self.word_next_finder(find_docs)
        if word_next:
            page = 2
            while True:
                find_docs = self.find_doc(corp_name, date_begin, date_end, action, page, name_id, firm_id, firm_name)

                # next_nd = self.list_number_doc(find_docs)
                self.queue_for_doc.put([find_docs, mod_handler, action])

                word_next = self.word_next_finder(find_docs)
                # [list_nd.append(item) for item in next_nd]
                if word_next is False:
                    # return list_nd
                    return
                page += 1
        else:
            # return list_nd
            return

    # обработчик list`а номеров документов
    def handler_nd(self, list_nd, res, mod_handler=False):
        response = self.session.post(self.url,
                                     data={'printScope': 'currentPage', 'printType': 1, 'printAction': 2,
                                           'printSchemaSelect': 'null',
                                           'number': 'printField', 'sender': 'printField', 'service': 'printField',
                                           '_action': 'printSelectedVetDocuments', '_language': 'ru',
                                           'printForm': 'vetDocumentPrintForm',
                                           'selectedVetDocumentPk': list_nd},
                                     cookies=self.cookies,
                                     proxies=self.proxies)

        table = bs4.BeautifulSoup(response.text, "html5lib").find('td', {'class': 'data'}).find('tbody').find_all('tr')

        row = 3 if mod_handler else 2
        for item in table:
            item = item.find_all('td')

            res.append({
                'vetDoc': item[1].text,
                'name_corp': item[row].text,
                'owner_product': item[2].text,
                'type_service': ' '.join(item[4].text.split())
            })
        return res

    # предобработка/подготовка списка для обработчика номеров вет доков
    def h_nd(self, list_nd, res, mod_handler=False):
        size_lnd = len(list_nd)
        if size_lnd > 1000:
            ish = size_lnd // 1000
            for i in range(1, ish + 1):
                self.handler_nd(list_nd[i * 1000 - 1000: i * 1000], res, mod_handler=mod_handler)
            if size_lnd % 1000 > 0:
                self.handler_nd(list_nd[ish * 1000:], res, mod_handler=mod_handler)
        else:
            self.handler_nd(list_nd, res, mod_handler=mod_handler)

    # просто запускает парсер текста в порядке action`ов для предприятия
    def doc_scraper(self, corp_name, corp_value, date_begin, date_end, name_id='null', firm_id='', firm_name=''):

        for action in self.actions:
            self.get_full_list_vet_doc(corp_value, corp_name, action, date_begin, date_end, name_id, firm_id, firm_name)

    # обработчик очереди, запускать в отдельном потоке
    def start_queue_handler(self):
        temp = []
        mod_temp = []
        while True:
            item = self.queue_for_doc.get()
            # квитанция конца
            if item[0] == 'stop_thread':
                self.queue_for_doc.task_done()
                break

            list_nd = self.list_number_doc(item[0])
            mod_handler = item[1]
            action = item[2]

            if len(list_nd) > 0:
                list_nd.append(action)
                if mod_handler:
                    # [mod_temp.append(nd) for nd in list_nd]
                    mod_temp.append(list_nd)
                else:
                    # [temp.append(nd) for nd in list_nd]
                    temp.append(list_nd)
                # list_nd.clear()

            self.queue_for_doc.task_done()
            # после замеров подобрать оптимум
            sleep(0.1)
        # дообработать остатки
        self.queue_out.put([temp, False])
        self.queue_out.put([mod_temp, True])

    def body_v3(self, in_date, in_date_to, result_list, name_list):
        # проверка списка фильтра
        if (name_list is None) or (len(name_list) == 0):
            return
        # получили список предприятий
        list_corp = self.get_corp_list(self.change_corp().text)
        if len(list_corp) == 0:
            return
        # запуск обработчика очереди
        my_thread = Thread(target=self.start_queue_handler, daemon=True)
        my_thread.start()

        # для каждого предприятия
        for item in list_corp:
            log.debug(item)
            # выберем его основным
            self.set_corp(item['value'])
            # пройдем по предприятию по списку ФИО в фильтре
            for name in name_list:
                # получим id человека
                name_id = self.get_user_info(name)[1]
                # если предприятие требуется расширить по доп списку то
                if int(item['value']) in firm_list.keys():
                    # для каждого из этого списка
                    for key, value in firm_list[int(item['value'])].items():
                        # запустить сборщик номеров документов
                        self.doc_scraper(corp_name=item['name'], corp_value=item['value'],
                                         date_begin=in_date, date_end=in_date_to, name_id=name_id,
                                         firm_id=str(key), firm_name=value)
                else:
                    # сборщик номеров документов стандартный
                    self.doc_scraper(corp_name=item['name'], corp_value=item['value'],
                                     date_begin=in_date, date_end=in_date_to, name_id=name_id)
            # переход на страницу смены предприятия
            self.change_corp()

        # шлем квитанцию, что мы все предприятия обработали
        self.queue_for_doc.put(item=['stop_thread', False])
        # ждем когда очередь обработается
        self.queue_for_doc.join()

        # обработка очереди выходной, финальной
        # два словаря, ключи - тип вет дока (action)
        # value для тех - которые надо допом обрабатывать(data_mod),
        # и тех - что не надо (data)
        data = {self.actions[0]: [], self.actions[1]: [], self.actions[2]: []}
        data_mod = {self.actions[0]: [], self.actions[1]: [], self.actions[2]: []}
        log.debug('обработка очереди')
        # пока очередь не пуста
        while not self.queue_out.empty():
            # получаем из очереди
            item = self.queue_out.get()
            # распределение по спискам словарей
            if item[1]:
                for number in item[0]:
                    [data_mod[number[-1]].append(num) for num in number[:-1]]
            else:
                for number in item[0]:
                    [data[number[-1]].append(num) for num in number[:-1]]
            # квитанция обработки итема, взятого из очереди
            self.queue_out.task_done()

        # для уточнения по номерам вет.док, чтобы узнать какой конкретно он формы
        # встаем на любое (конкретно тут первое) предприятие, чтобы можно было юзать форму Меркурия
        self.set_corp(list_corp[0]['value'])
        for key in data.keys():
            # переходим к странице с нужным типом action`а
            self.list_viewer_doc(key)
            # запрашиваем уточнение
            self.h_nd(data[key], result_list, mod_handler=False)
            self.h_nd(data_mod[key], result_list, mod_handler=True)
            # все это складывается в список, который передали при вызове
        log.debug('закончили')
