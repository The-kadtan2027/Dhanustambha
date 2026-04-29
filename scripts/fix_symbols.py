import sqlite3

def run():
    conn = sqlite3.connect('data/market.db')
    cur = conn.cursor()
    cur.execute("UPDATE ohlcv SET symbol='TMCV' WHERE symbol='TATAMOTORS'")
    cur.execute("UPDATE symbols SET symbol='TMCV' WHERE symbol='TATAMOTORS'")
    conn.commit()
    print("TATAMOTORS aliased to TMCV successfully.")

if __name__ == '__main__':
    run()
