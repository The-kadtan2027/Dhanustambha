import yfinance as yf
import time
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)

start = time.time()
yf_symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS"] * 50 # 150 symbols
print(f"Downloading {len(yf_symbols)} symbols at 1m interval...")
data_1m = yf.download(yf_symbols, period="1d", interval="1m", progress=False, threads=True)
time_1m = time.time() - start
print(f"1m interval took: {time_1m:.2f}s")

start = time.time()
print(f"Downloading {len(yf_symbols)} symbols at 1d interval...")
data_1d = yf.download(yf_symbols, period="1d", interval="1d", progress=False, threads=True)
time_1d = time.time() - start
print(f"1d interval took: {time_1d:.2f}s")
