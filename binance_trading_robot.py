from binance.client import Client
import keys
import pandas as pd
import time
import colorama
colorama.init()
from termcolor import cprint
'''
    Торговый робот для крипто-биржи Binance - (версия Only-Clean-Cat: 14.06.2024.1.01)
    Принцип работы:
    1. Соединение
    2. Поиск самой активной монеты по росту
    3. Анализ роста выбраной монеты в настоящий момент
    4. Открытие сделки с указанным stop, take и profit по выбранной монете
    5. Закрытие сделки по профиту или неудаче
    Настройка по умолчанию: "пара" с USDT; объем сделки = 20 USDT; профит = 1,02; неудача = 0,985.
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
    return top_coin


def last_active_coin(symbol, interval, lookback): # Анализ роста выбраной монеты в настоящий момент

    frame = pd.DataFrame(client.get_historical_klines(symbol, interval, lookback + 'min ago UTC')) # запрос аналитики
    frame = frame.iloc[:,:6] # выбор ответов запроса
    frame.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume'] # переименование колонок данных в запросе
    frame = frame.set_index('Time') # сортировка по времени
    frame.index = pd.to_datetime(frame.index, unit='ms')
    frame = frame.astype(float) # переименовываем строковый ответ в числа для операций сравнения
    return frame


def robot_strategy(buy_amt, SL=0.985, Target=1.015, open_position=False): # Стратегия торгового робота
    # buy_amt - объем захода в сделку;  SL - порог продажи при падении; Target - порог продажи при росте
    try:
        asset = active_coin() # получаем монету
        df = last_active_coin(asset,'1m', '120') # анализ активности монеты за промежуток времени
    except:  # при ошибке отправляем запрос заноново через одну минуту
        time.sleep(61)
        asset = active_coin()
        df = last_active_coin(asset, '1m', '120')

    quantity = round(buy_amt/df.Close.iloc[-1], 1) # округляем сумму до принятых биржей значений
    if ((df.Close.pct_change() + 1).cumprod()).iloc[-1] > 1: # если актив растет
        cprint(f'Монета: {asset}', color='cyan') # монета
        cprint(f'Цена: {df.Close.iloc[-1]}', color='cyan') # цена закрытия последней сделки
        cprint(f'Количество: {quantity}', color='cyan') # объем купленных монет
        print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
        order = client.create_order(symbol=asset, side='BUY', type='MARKET', quantity=quantity) # открываем сделку
        # symbol - монета; side - покупаем; type - тип стратегии; quantity - количество
        cprint(f'Ордер покупки: {order}', color='yellow')
        buyprice = float(order['fills'][0]['price']) # цена покупки
        open_position = True # заход в сделку

        while open_position:
            try:
                df = last_active_coin(asset, '1m', '2') # контроль позиции для закрытия
            except: # при ошибке отправляем запрос заноново через одну минуту
                cprint('Что-то пошло не так. Рестарт через одну минуту', color='red')
                time.sleep(61)
                df = last_active_coin(asset, '1m', '2')
            cprint(f'Цена на данный момент: 'f'{df.Close.iloc[-1]}\r', color='yellow', end='', flush=True)
            cprint(f'Цена продажи: 'f'{buyprice * Target}\r',color='yellow', end='', flush=True)
            cprint(f'Стоп цена: 'f'{buyprice * SL}\r',color='yellow', end='', flush=True)
            if df.Close.iloc[-1] <= buyprice * SL : # выход из сделки
                order = client.create_order(symbol=asset, side='SELL', type='MARKET', quantity=quantity)
                print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
                cprint(f'Ордер закрыт по неудаче: {order}', color='red')
                time.sleep(3)
                cprint(f'Баланс: {buy_amt} USDT', color='magenta')
                time.sleep(3)
                break
            elif df.Close.iloc[-1] >= buyprice * Target: # выход из сделки
                order = client.create_order(symbol=asset, side='SELL', type='MARKET', quantity=quantity)
                print('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
                cprint(f'Ордер закрыт по профиту: {order}', color='green')
                time.sleep(3)
                cprint(f'Баланс: {buy_amt} USDT', color='magenta')
                time.sleep(3)
                break
    else:
        cprint(f'Рынок падает:' + f'Нет монеты подходящей под условия сделки\r', color='red',end='', flush=True)
        time.sleep(20)

while True:
    try:
     robot_strategy(20) # непрерывный цикл работы робота с установкой объема в 20 USDT
    except Exception as exc:
        cprint(f'Ошибка: {exc}', color='red')
        break