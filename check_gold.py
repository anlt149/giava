import os
import json
import datetime
import requests
from gold_api import get_vietnam_gold_prices, build_gold_report_message
from stock_api import get_stock_price, build_stock_report_message, load_prefs

STATE_FILE = "gold_price_state.json"

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()

def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Skipping notification.")
        
    # Load state
    old_state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                old_state = json.load(f)
        except Exception as e:
            print(f"Could not read state file: {e}")
            
    new_state = old_state.copy()
    new_state["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"

    # --- 1. Gold Price Check ---
    gold_changed = False
    gold_msg = None
    try:
        current_prices = get_vietnam_gold_prices()
        if 'sjc' in current_prices:
            current_sjc_buy = current_prices['sjc']['buy']
            current_sjc_sell = current_prices['sjc']['sell']
            
            old_sjc_buy = old_state.get("sjc_buy", 0)
            old_sjc_sell = old_state.get("sjc_sell", 0)
            
            if current_sjc_buy != old_sjc_buy or current_sjc_sell != old_sjc_sell:
                print(f"Gold price changed! Old: {old_sjc_buy}/{old_sjc_sell} -> New: {current_sjc_buy}/{current_sjc_sell}")
                diff_buy = current_sjc_buy - old_sjc_buy if old_sjc_buy != 0 else None
                diff_sell = current_sjc_sell - old_sjc_sell if old_sjc_sell != 0 else None
                
                gold_msg = build_gold_report_message(diff_buy=diff_buy, diff_sell=diff_sell)
                gold_changed = True
                
                new_state["sjc_buy"] = current_sjc_buy
                new_state["sjc_sell"] = current_sjc_sell
            else:
                print("No change in Vietnam gold price.")
        else:
            print("SJC price not found in the API response.")
    except Exception as e:
        print(f"Error fetching gold prices: {e}")

    # --- 2. Stock Price Check ---
    stock_changed = False
    stock_msg = None
    try:
        prefs = load_prefs()
        favorite_stock = prefs.get("favorite_stock")
        if favorite_stock:
            print(f"Checking favorite stock: {favorite_stock}...")
            stock_data = get_stock_price(favorite_stock)
            if stock_data:
                current_stock_price = stock_data["price"]
                
                old_stock_ticker = old_state.get("stock_ticker")
                old_stock_price = old_state.get("stock_price", 0.0)
                
                if favorite_stock != old_stock_ticker or current_stock_price != old_stock_price:
                    print(f"Stock price changed! Old ({old_stock_ticker}): {old_stock_price} -> New ({favorite_stock}): {current_stock_price}")
                    stock_msg = build_stock_report_message(stock_data)
                    stock_changed = True
                    
                    new_state["stock_ticker"] = favorite_stock
                    new_state["stock_price"] = current_stock_price
                else:
                    print(f"No change in stock price for {favorite_stock}.")
            else:
                print(f"Failed to fetch stock data for {favorite_stock}.")
        else:
            print("No favorite stock configured.")
    except Exception as e:
        print(f"Error fetching stock prices: {e}")

    # --- 3. Send Notifications & Save State ---
    if gold_changed and gold_msg:
        if bot_token and chat_id:
            try:
                send_telegram_message(bot_token, chat_id, gold_msg)
                print("Gold notification sent to Telegram.")
                old_state["sjc_buy"] = new_state["sjc_buy"]
                old_state["sjc_sell"] = new_state["sjc_sell"]
            except Exception as e:
                print(f"Failed to send Gold Telegram message: {e}")
        else:
            # If no tokens, update local state anyway to simulate local run
            old_state["sjc_buy"] = new_state["sjc_buy"]
            old_state["sjc_sell"] = new_state["sjc_sell"]
            
    if stock_changed and stock_msg:
        if bot_token and chat_id:
            try:
                send_telegram_message(bot_token, chat_id, stock_msg)
                print("Stock notification sent to Telegram.")
                old_state["stock_ticker"] = new_state["stock_ticker"]
                old_state["stock_price"] = new_state["stock_price"]
            except Exception as e:
                print(f"Failed to send Stock Telegram message: {e}")
        else:
            # If no tokens, update local state anyway to simulate local run
            old_state["stock_ticker"] = new_state["stock_ticker"]
            old_state["stock_price"] = new_state["stock_price"]

    old_state["last_updated"] = new_state["last_updated"]
    
    # Save the updated state
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(old_state, f, indent=2)
        print("State file updated.")
    except Exception as e:
        print(f"Failed to save state file: {e}")

if __name__ == "__main__":
    main()
