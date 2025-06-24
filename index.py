# Parallel Channel Strategy using Backtrader (Python-only)
import backtrader as bt
import numpy as np
from scipy import stats

class ParallelChannel(bt.Strategy):
    params = (
        ('window', 100),
        ('lookback', 10),
        ('min_width', 0.02),
        ('max_width', 0.15),
        ('boundary_threshold', 0.005),
        ('target_profit', 0.10),
        ('stop_loss', 0.08),
    )

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.high = self.datas[0].high
        self.low = self.datas[0].low
        self.order = None
        self.entry_price = None
        self.channel = None
        self.buyprice = None
        self.buycomm = None

    def next(self):
        if len(self) < self.params.window:
            return

        highs = list(self.high.get(size=self.params.window))
        lows = list(self.low.get(size=self.params.window))
        closes = list(self.dataclose.get(size=self.params.window))

        mins = self.find_local_extremes(lows, 'min', self.params.lookback)
        maxs = self.find_local_extremes(highs, 'max', self.params.lookback)

        if len(mins) < 2 or len(maxs) < 2:
            return

        channel = self.create_channel(mins, maxs, closes)
        if not channel:
            return

        self.channel = channel
        lower = channel['lower']
        upper = channel['upper']
        price = self.dataclose[0]

        if not self.position:
            if abs(price - lower) / price < self.params.boundary_threshold:
                self.order = self.buy()
                self.entry_price = price
            elif abs(price - upper) / price < self.params.boundary_threshold:
                self.order = self.sell()
                self.entry_price = price
        else:
            pnl_pct = (price - self.entry_price) / self.entry_price if self.position.size > 0 else (self.entry_price - price) / self.entry_price
            if pnl_pct >= self.params.target_profit or pnl_pct <= -self.params.stop_loss:
                self.close()

    def find_local_extremes(self, data, typ, lb):
        result = []
        for i in range(lb, len(data) - lb):
            if typ == 'min':
                if all(data[i] <= data[j] for j in range(i - lb, i + lb + 1)):
                    result.append((i, data[i]))
            else:
                if all(data[i] >= data[j] for j in range(i - lb, i + lb + 1)):
                    result.append((i, data[i]))
        return result[-4:] if len(result) >= 4 else result

    def create_channel(self, mins, maxs, closes):
        try:
            min_x, min_y = zip(*mins[-2:])
            max_x, max_y = zip(*maxs[-2:])

            min_slope, min_int, min_r, _, _ = stats.linregress(min_x, min_y)
            max_slope, max_int, max_r, _, _ = stats.linregress(max_x, max_y)

            if abs(max_slope - min_slope) > 0.05:
                return None

            avg_slope = min_slope
            offset = np.mean(max_y) - np.mean(min_y)

            lower = min_int + avg_slope * 0
            upper = lower + offset
            price = closes[-1]
            width = (upper - lower) / price

            if not (self.params.min_width <= width <= self.params.max_width):
                return None

            return {
                'upper': upper,
                'lower': lower,
                'width': width,
                'slope': avg_slope,
                'strength': (abs(min_r) + abs(max_r)) / 2
            }

        except Exception as e:
            print(f"Channel creation failed: {e}")
            return None


if __name__ == '__main__':
    import yfinance as yf
    data_df = yf.download('SPY', start='2022-01-01', end='2024-12-31', interval='1d')
    data_df.dropna(inplace=True)

# Convert to Backtrader format
    data = bt.feeds.PandasData(dataname=data_df)

# Add to Cerebro
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    
    datafeed = bt.feeds.PandasData(dataname=data)
    cerebro.addstrategy(ParallelChannel)
    cerebro.broker.set_cash(100000)
    cerebro.addobserver(bt.observers.BuySell)
    cerebro.addobserver(bt.observers.Value)
    
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.plot(style='candlestick')
