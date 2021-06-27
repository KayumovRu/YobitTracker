import sys
import os
import pandas as pd
import sqlite3
import plotly
import plotly.graph_objs as go
import json
import warnings

warnings.filterwarnings("ignore")

# it helps if the script folder and the current directory do not match
curdir = os.path.dirname(os.path.abspath(__file__))

# I/O is added manually to balance.csv. If there is no file or it is empty, then the graph is not plotted
def add_balance():
    fig.add_trace(go.Scatter(
        x = df_balance['date'],
        y = df_balance['in_usd'],
        mode='none',
        fill='tozeroy',
        line_shape='hv',
        fillcolor='rgba(255, 80, 80, 0.7)',
        opacity=0.5,
        name='Deposit: $' + str(df_balance['in_usd'].iloc[-1]) ))
    fig.add_trace(go.Scatter(
        x = df_balance['date'],
        y = df_balance['out_usd'],
        mode='none',
        fill='tozeroy',
        line_shape='hv',
        fillcolor='rgba(111,231,219, 0.5)',
        opacity=0.5,
        name='Withdrawal: $' + str(df_balance['out_usd'].iloc[-1]) ))

# saving the graph to a json file
def chart_save(fig, fileJSON):
    chartJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    with open(curdir+'/dashboard/'+fileJSON, 'w') as file:
        file.write('var graphs = {};'.format(chartJSON))

# replacing absolute changes with relative ones
def abs2rel(tmp_df):
    for col in tmp_df.columns:
        first_val = tmp_df[col].loc[~tmp_df[col].isnull()].iloc[0] # finding the first EXISTING value
        tmp_df[col] = tmp_df[col].map(lambda x: x / first_val - 1)

conn = sqlite3.connect('yotracker.db')

sql = '''
SELECT *
FROM funds
'''

df = pd.read_sql(sql, conn)
df['total_usd'] = (df['amount'] * df['usd']).round(2)

df_portf = df[['timestamp', 'total_usd']].groupby(by='timestamp', as_index=False).sum()
df_portf['timestamp'] = df_portf['timestamp'].astype(dtype='datetime64[s]') # convert it to a date

df_balance = None # to create a df for the balance, it will be useful for checking later

try:
    df_balance = pd.read_csv(curdir+'/balance.csv', sep=';')
    df_balance = df_balance[df_balance['currency'] == 'usd'] # temporary restriction - select only USD, because so far we are able to work only with it in balances
    df_balance['date'] = df_balance['date'].astype(dtype='datetime64[s]') # converting to date
    # add a zero line to overlay correctly on the portfolio chart
    row_current = {'date': df_portf['timestamp'].max(), 'currency':'usd', 'amount': 0, 'withdrawal':0}
    df_balance = df_balance.append(row_current, ignore_index=True)
    df_balance['withdrawal'] = df_balance['withdrawal'].astype(dtype='boolean')

    # cumulative amounts for deposits (IN) and withdrawals (OUT)
    df_balance['in_usd'] = (df_balance['amount']*~df_balance['withdrawal']).cumsum()
    df_balance['out_usd'] = (df_balance['amount']*df_balance['withdrawal']).cumsum()
except:
    sys.stderr.write("Warninmg: the balance.csv file does not exist or cannot be processed")

# CHART - CHANGING THE PORTFOLIO AND BALANCE
fig = go.Figure()
fig.add_trace(go.Scatter(
    x = df_portf['timestamp'],
    y = df_portf['total_usd'],
    mode='lines',
    name='Portfolio: $' + str(df_portf['total_usd'].iloc[-1].round(2)) ))
if df_balance is not None:
    add_balance()
    fig.update_xaxes(range=[df_portf['timestamp'].min(), df_portf['timestamp'].max()]) # restriction on the X-axis
fig.update_layout(
    margin=dict(l=10, r=10, t=10, b=10),
    template='plotly_dark',
    legend=dict(orientation='h', yanchor='bottom', y=1.02))
chart_save(fig, 'portfolio.JSON')

# CHART - PORTFOLIO COMPOSITION
# select the current portfolio according to the last timestamp, leave only the necessary columns, sort
df_last = df.loc[df['timestamp'] == df['timestamp'].max()]
df_last = df_last[['coin','total_usd']]
df_last = df_last.sort_values(by='total_usd', ascending=True).reset_index(drop=True)

# select the top 10 coins of the current portfolio by total usd (df_last sorting was earlier)
df_last_top = df_last.tail(10)
df_last_top['coin'] = df_last_top['coin'].str.upper() # the name of the coins in upper case
# and we sum up the cost of all the other coins in the portfolio with a separate line OTHER, add it
row_other = {'coin':'-other-', 'total_usd':df_last[:-10]['total_usd'].sum()}
df_last_top = df_last_top.append(row_other, ignore_index=True)
df_last_top = df_last_top.sort_values(by='total_usd', ascending=True).reset_index(drop=True)

fig = go.Figure()
fig.add_trace(go.Bar(
    y=df_last_top['coin'],
    x=df_last_top['total_usd'],
    orientation='h',
    text = df_last_top['total_usd'].round(2),
    textposition='auto'))
fig.update_layout(
    margin=dict(l=10, r=10, t=10, b=10),
    template='plotly_dark')
chart_save(fig, 'top_coin_usd.JSON')

# CHART - CHANGES IN THE EXCHANGE RATE OF THE TOP COINS (in %)
#  select coins from the top
df_select = df[['coin','usd','timestamp']]
df_select = df_select[df_select['coin'].isin(df_last_top['coin'].str.lower())]

# expand it in pivot by coins and dates
df_pivot = df_select.pivot_table(index='timestamp', columns='coin')['usd']
df_pivot = df_pivot.rename_axis(None, axis=1)
df_pivot.index = pd.to_datetime(df_pivot.index, unit='s') # to date

abs2rel(df_pivot)

pd.options.plotting.backend = "plotly"
fig = df_pivot.plot()
fig.update_layout(
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis_tickformat=',.0%', # convert the scale to the percentage format
    yaxis_title=None,
    xaxis_title=None,
    template='plotly_dark')
chart_save(fig, 'top_exchange.JSON')

# CHART - LEADERS OF GROWTH AND DECLINE
df_rate = df[['coin','usd','timestamp']]
# expand it in pivot
df_rate_pivot = df_rate.pivot_table(index='timestamp', columns='coin')['usd']
df_rate_pivot = df_rate_pivot.rename_axis(None, axis=1)

abs2rel(df_rate_pivot)

df_rate_pivot = df_rate_pivot.iloc[[-1]].transpose().reset_index() # leave the last line and transpose
df_rate_pivot.index.rename('index')
df_rate_pivot.columns = ['coin', 'change']
df_rate_pivot['coin'] = df_rate_pivot['coin'].str.upper()

# if there are more than 20 coins, then leave only the first 10 and the last 10
if len(df_rate_pivot) > 20:
    df_rate_pivot = pd.concat([df_rate_pivot.iloc[0:10],  df_rate_pivot.iloc[-11:-1]])

fig = go.Figure()
fig.add_trace(go.Bar(
    y=df_rate_pivot['coin'],
    x=df_rate_pivot['change'],
    marker_color = ['rgba(64, 220, 128, 0.7)' if x > 0 else 'rgba(255, 80, 80, 0.7)' for x in df_rate_pivot['change']],
    orientation='h',
    textposition='auto'))
fig.update_layout(
    margin=dict(l=10, r=10, t=10, b=10),
    xaxis_tickformat=',.0%', # convert the scale to the percentage format
    template='plotly_dark')
chart_save(fig, 'growth_leaders.JSON')