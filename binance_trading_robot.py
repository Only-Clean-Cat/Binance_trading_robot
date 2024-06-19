from binance.client import Client
import keys
import pandas as pd
import time
import colorama
colorama.init()
from termcolor import cprint
import datetime
import balance_total
'''
    Торговый робот для крипто-биржи Binance - (версия Only-Clean-Cat: 14.06.2024.1.01)
    ВАЖНО!!!!!!  Торговля ведется с комиссией в BNB!!!!!!!!!
    Принцип работы:
    1. Соединение
    2. Поиск самой активной монеты по росту
    3. Анализ роста выбраной монеты в настоящий момент
    4. Открытие сделки с указанным stop, take и profit по выбранной монете
    5. Закрытие сделки по профиту или стоп цене
    Настройка по умолчанию: "пара" с USDT; объем сделки = 20 USDT; профит = 1,015; стоп цена = 0,995.
    Отчеты о сесии робота сохраняются в data_report.txt
'''

try:
    client = Client(keys.api_key, keys.api_secret) # подключение к своему счету на Binance
except Exception as exc:
    cprint(f'Ошибка подключения к аккаунту: {exc}', color='red')


def active_coin(): # Поиск самой активной монеты по росту

    all_coins = pd.DataFrame(client.get_ticker()) # получаем массив торговых "пар"
    usdt = all_coins[all_coins.symbol.str.contains('USDT')] # отбор торговых "пар" с USDT
    working = usdt[~((usdt.symbol.str.contains('UP')) | (usdt.symbol.str.contains('DOWN')))] # фильтр монет с малой активностью
    top_coin = working[working.priceChangePercent == working.priceChangePercent.max()] # сортировка по активности
    top_coin = top_coin.symbol.values[0] # выбор самой активной монеты
    info = client.get_symbol_info(top_coin)
    print(info)
    return top_coin


def last_active_coin(symbol, interval, lookback): # Анализ роста выбраной монеты в настоящий момент

    frame = pd.DataFrame(client.get_historical_klines(symbol, interval, lookback + 'min ago UTC')) # запрос аналитики
    frame = frame.iloc[:,:6] # выбор ответов запроса
    frame.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume'] # переименование колонок данных в запросе
    frame = frame.set_index('Time') # сортировка по времени
    frame.index = pd.to_datetime(frame.index, unit='ms')
    frame = frame.astype(float) # переименовываем строковый ответ в числа для операций сравнения
    return frame


def robot_strategy(buy_amt, SL=0.9965, Target=1.01, open_position=False): # Стратегия торгового робота
    # buy_amt - объем захода в сделку;  SL - порог продажи при падении; Target - порог продажи при росте
    try:
        asset = active_coin() # получаем монету
        df = last_active_coin(asset,'1m', '60') # анализ активности монеты за промежуток времени
    except:  # при ошибке отправляем запрос заноново через одну минуту
        time.sleep(61)
        asset = active_coin()
        df = last_active_coin(asset, '1m', '60')
    cur_dt = datetime.datetime.now()
    quantity = round(buy_amt/df.Close.iloc[-1], 1)# округляем сумму до принятых биржей значений
    if ((df.Close.pct_change() + 1).cumprod()).iloc[-1] > 1: # если актив растет
        cprint(f'Монета: {asset}', color='cyan') # монета
        cprint(f'Цена: {df.Close.iloc[-1]}', color='cyan') # цена закрытия последней сделки
        cprint(f'Количество: {quantity}', color='cyan') # объем купленных монет
        print('>' * 50)
        order = client.create_order(symbol=asset, side='BUY', type='MARKET', quantity=quantity) # открываем сделку
        # symbol - монета; side - покупаем; type - тип стратегии; quantity - количество
        cprint(f'Ордер покупки: {order}', color='yellow')
        report = open('data_report.txt', 'a+')
        report.write(f'{cur_dt}\n'
                     f'Ордер покупки: Монета: {asset}! Цена: {df.Close.iloc[-1]}! '
                     f'Количество: {quantity}! Сумма USDT: {quantity * df.Close.iloc[-1]}' + '\n')
        report.close()
        print('>' * 50)
        buyprice = float(order['fills'][0]['price']) # цена покупки
        open_position = True # заход в сделку
        price_trade = round(buyprice * Target, 8)
        price_stop = round(buyprice * SL, 8)
        sum_deal_open = quantity * df.Close.iloc[-1]
        total_balance = 0
        while open_position:
            try:
                df = last_active_coin(asset, '1m', '2') # контроль позиции для закрытия
            except Exception as exc: # при ошибке отправляем запрос заноново через одну минуту
                cprint(f'Что-то пошло не так: {exc}.  Рестарт через одну минуту', color='red')
                time.sleep(61)
                df = last_active_coin(asset, '1m', '2')
            cprint(f'Цена на данный момент: ' + f'{df.Close.iloc[-1]}', color='yellow')
            cprint(f'Цена профит: ' + f'{price_trade}',color='yellow')
            cprint(f'Стоп цена: ' + f'{price_stop}',color='yellow')
            if df.Close.iloc[-1] <= price_stop: # выход из сделки
                order = client.create_order(symbol=asset, side='SELL', type='MARKET', quantity=quantity)
                balance_dial = (quantity * df.Close.iloc[-1] - sum_deal_open) * 1.0003
                total_balance = total_balance + balance_dial
                balance_total.total_balance = total_balance
                cprint(f'Ордер закрыт по неудаче: {order}', color='red')
                report = open('data_report.txt', 'a+')
                report.write(f'{cur_dt}\n'
                             f'Ордер закрыт по стоп цене: Монета: {asset}! Цена: {df.Close.iloc[-1]}! '
                             f'Количество: {quantity}! Сумма USDT: {quantity * df.Close.iloc[-1]}' + '\n'
                             f'Баланс: {balance_dial} USDT' + '\n'
                             f'>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n'
                             f' Тотал баланс: {total_balance} USDT\n'
                             f'>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n')
                report.close()
                print('>' * 50)
                time.sleep(3)
                cprint(f'Баланс: {quantity * df.Close.iloc[-1] - sum_deal_open} USDT', color='magenta')
                time.sleep(3)
                break
            elif df.Close.iloc[-1] >= price_trade: # выход из сделки
                order = client.create_order(symbol=asset, side='SELL', type='MARKET', quantity=quantity)
                balance_dial = (quantity * df.Close.iloc[-1] - sum_deal_open) * 0.9997
                total_balance += balance_dial
                balance_total.total_balance = total_balance
                cprint(f'Ордер закрыт по профиту: {order}', color='green')
                report = open('data_report.txt', 'a+')
                report.write(f'{cur_dt}\n'
                             f'Ордер закрыт по профиту: Монета: {asset}! Цена: {df.Close.iloc[-1]}! '
                             f'Количество: {quantity}! Сумма USDT: {quantity * df.Close.iloc[-1]}' + '\n'
                             f'Баланс: {balance_dial} USDT' + '\n'
                             f'>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n'
                             f' Тотал баланс: {total_balance} USDT\n'
                             f'>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n')
                report.close()
                print('>' * 50)
                time.sleep(3)
                cprint(f'Баланс: {quantity * df.Close.iloc[-1] - sum_deal_open} USDT', color='magenta')
                time.sleep(3)
                break
    else:
        cprint(f'Рынок падает: Нет монеты подходящей под условия сделки', color='red')
        time.sleep(20)

while True:
    time.sleep(5)
    try:
        robot_strategy(19) # непрерывный цикл работы робота с установкой объема в 20 USDT
    except Exception as exc:
        cprint(f'Ошибка: {exc}', color='red')
        time.sleep(3)

