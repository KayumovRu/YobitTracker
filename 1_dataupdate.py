import sys
import os
import time
import requests
import hmac
import hashlib
from urllib.parse import urlencode
from math import ceil, floor
import pandas as pd
import sqlite3
import numpy as np

API_URL = 'https://yobit.net/api/3/'
TAPI_URL = 'https://yobit.net/tapi/'

timestamp = int(time.time()) # is used as a "nonce" and later for writing timestamp to the database, number of seconds, GMT
depo_currency = 'usd' # deposit currency

# reading the key and secret from a file
curdir = os.path.dirname(os.path.abspath(__file__)) # used if there are problems with displaying the progress bar below
try:
    f = open(curdir + '\key.txt', 'w+')
    key_list = f.read().splitlines()
    KEY = key_list[0]
    SECRET = key_list[1]
except:
    sys.exit("Key reading error. Check the file key.txt")

# Yobit API trade
def api_trade(method, nonce):
    params_dict = {}
    params_dict['method'] = method
    params_dict['nonce'] = str(nonce)
    params = urlencode(params_dict)
    sign = hmac.new(SECRET.encode(), params.encode(), hashlib.sha512).hexdigest()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Key': KEY,
        'Sign': sign
    }
    try:
        return requests.post(TAPI_URL, data=params, headers=headers)
    except:
        sys.exit("POST (getInfo) request error. Check that the KEY/SECRET is correct and that the site is available.")

# Yobit API ticker
def api_ticker(depo_currency, pair_lst):
    part_len = 40 # to divide by 40 in 1 request
    parts = ceil(len(pair_lst)/part_len)
    pair_lst_parts = [pair_lst[part_len*x : part_len*(x+1)] for x in range(parts)]
    ticker_json = {}
    try:
        for part in pair_lst_parts:
            url = API_URL + 'ticker/' + '-'.join(part) + '?ignore_invalid=1'
            ticker_json.update(requests.get(url).json())
            sys.stdout.write('.') # progress bar mini
            time.sleep(2) # antiban protect
        return ticker_json
    except:
        sys.exit("GET (ticker) request error. Check that the site is available.")

res = api_trade('getInfo', timestamp)

funds_dict = res.json()['return']['funds_incl_orders']
coin_lst = list(funds_dict.keys()) # list of coins
pair_lst = [x + '_' + depo_currency for x in coin_lst] # list of pairs
df_funds = pd.DataFrame.from_dict(funds_dict, orient='index', columns = ['amount'])
df_funds[depo_currency] = np.nan

ticker_json = api_ticker(depo_currency, pair_lst)

for coin in coin_lst:
    if coin != depo_currency:
        pair_coin = coin+'_'+depo_currency
        df_funds.loc[coin, depo_currency] = ticker_json[pair_coin]['buy'] # exchange purchase price
    else: 
        df_funds.loc[coin, depo_currency] = 1 # if usd = usd, then 1

df_funds = df_funds.rename_axis('coin').reset_index()
df_funds['timestamp'] = timestamp

# to db
conn = sqlite3.connect('yotracker.db')
df_funds.to_sql('funds', conn, if_exists='append', index = False)