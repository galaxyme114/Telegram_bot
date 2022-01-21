import json
import re
import sys
import traceback
import asyncio

from ccxt import binance, errors
from pprint import pprint
from telethon.sync import TelegramClient, events

def get_binance_config():
    with open('binance.json') as f:
        return json.load(f)

def get_telegram_config():
    with open('telegram.json') as f:
        return json.load(f)

def init_binance():
    binance_config = get_binance_config()
    exchange = binance({
        'apiKey': binance_config['apiKey'],
        'secret': binance_config['secret'],
        'adjustForTimeDifference': True,
    })
    id_to_pair_map = {}
    markets = exchange.load_markets()
    for pair in markets: 
        id_to_pair_map[markets[pair]['id']] = pair
    return exchange, id_to_pair_map

def init_telegram():
    telegram_config = get_telegram_config()
    client = TelegramClient('kickass', telegram_config['appId'], telegram_config['appHash'])
    client.connect()
    if not client.is_user_authorized():
        client.send_code_request(telegram_config['phoneNumber'])
        me = client.sign_in(telegram_config['phoneNumber'], input('Enter code: '))
    return client, telegram_config

def format_order(order):
    ret = ''
    for key, value in order.items():
        ret += "{}: {}\n".format(key, value)
    return ret

exchange, id_to_pair_map = init_binance()
client, telegram_config = init_telegram()
#target_patterns = '^.* - ([A-Z]+)  .* - Signal (Up|Down)$'
target_patterns = '^.* - ([A-Z]+)  .* - (Signal Up|Signal Down|BUY|SELL)$'
regexp = re.compile(target_patterns)

@client.on(events.NewMessage(pattern = target_patterns))
async def handler(event):
    message = 'Order triggered by message "%s" from MT4 bot.\n' % event.message.message
    try:
        sender = await event.get_sender()
        if type(sender) != 'Channel' or sender.title != telegram_config['channel']:
            pass
        market, signal = regexp.match(event.message.message).groups()
        market = market.replace('USD', 'USDT')
        first, second = id_to_pair_map[market].split('/')
        if second == 'USDT':
            ticker = exchange.fetch_ticker(id_to_pair_map[market])
            price = (float(ticker['ask']) + float(ticker['bid'])) / 2
            amount_buy = 44 / price
            amount_sell = 62 / price
            if signal == 'Signal Down' or signal == "BUY":
                order = exchange.create_market_buy_order(id_to_pair_map[market], amount_buy)
                message += 'Buying %s of value 44USDT~\n' % first + format_order(order)   
            elif signal == 'Signal Up' or signal == "SELL":
                order = exchange.create_market_sell_order(id_to_pair_map[market], amount_sell)
                message += 'Selling %s of value 62USDT~\n' % first + format_order(order)
        else:
            balances = exchange.fetch_balance()
            if signal == 'Signal Down' or signal == "BUY":
                ticker = exchange.fetch_ticker(id_to_pair_map[market])
                price = (float(ticker['ask']) + float(ticker['bid'])) / 2
                amount = (.001 * balances['total'][second]) / price
                order = exchange.create_market_buy_order(id_to_pair_map[market], amount)
                message += 'Buying %s with .1%% of existing %s~\n' % (first, second) + format_order(order)   
            elif signal == 'Signal Up' or signal == "SELL":
                order = exchange.create_market_sell_order(id_to_pair_map[market], .001 * balances['total'][first])
                message += 'Selling .1%% of existing %s for %s~\n' % (first, second) + format_order(order)
    except Exception as e:
        message += 'Error: ' + str(e)
    finally:
        await client.send_message('me', message=message)

client.loop.run_forever()
