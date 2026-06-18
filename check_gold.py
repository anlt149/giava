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
    stock_changed_items = []
    new_stock_prices = old_state.get("stock_prices", {}).copy()
    
    # Handle old state migration
    if "stock_ticker" in old_state and "stock_price" in old_state:
        t = old_state["stock_ticker"]
        p = old_state["stock_price"]
        if t and p and t not in new_stock_prices:
            new_stock_prices[t] = p
            
    try:
        prefs = load_prefs()
        watchlist = prefs.get("favorite_stocks", [])
        if watchlist:
            print(f"Checking watchlist stocks: {watchlist}...")
            for ticker in watchlist:
                stock_data = get_stock_price(ticker)
                if stock_data:
                    current_price = stock_data["price"]
                    old_price = new_stock_prices.get(ticker, 0.0)
                    
                    if current_price != old_price:
                        print(f"Stock {ticker} price changed! Old: {old_price} -> New: {current_price}")
                        stock_changed_items.append({
                            "ticker": ticker,
                            "price": current_price,
                            "old_price": old_price,
                            "change": stock_data["change"],
                            "change_percent": stock_data["change_percent"]
                        })
                        new_stock_prices[ticker] = current_price
                    else:
                        print(f"No change in stock price for {ticker}.")
                else:
                    print(f"Failed to fetch stock data for {ticker}.")
        else:
            print("No watchlist stocks configured.")
    except Exception as e:
        print(f"Error fetching stock prices: {e}")

    # Build stock changes message
    stock_msg = None
    if stock_changed_items:
        from stock_api import format_currency, escape_markdown
        now_str = datetime.datetime.now().strftime("%H:%M %d/%m/%Y")
        stock_msg = "🔔 *BÁO CÁO BIẾN ĐỘNG CỔ PHIẾU*\n\n"
        for item in stock_changed_items:
            ticker = item["ticker"]
            price = item["price"]
            old_p = item["old_price"]
            
            price_str = format_currency(price)
            
            if old_p > 0:
                diff = price - old_p
                sign = "+" if diff > 0 else ""
                diff_percent = (diff / old_p * 100) if old_p else 0.0
                indicator = "🟢" if diff > 0 else ("🔴" if diff < 0 else "⚪")
                diff_str = format_currency(diff)
                
                stock_msg += f"⚫ *{escape_markdown(ticker)}*\n"
                stock_msg += f"💰 Giá mới: {escape_markdown(price_str)} VND\n"
                stock_msg += f"📊 Biến động: {indicator} {escape_markdown(sign)}{escape_markdown(price_str if diff == 0 else diff_str)} VND \\({escape_markdown(sign)}{escape_markdown(f'{diff_percent:.2f}')}%\\)\n\n"
            else:
                stock_msg += f"⚫ *{escape_markdown(ticker)}*\n"
                stock_msg += f"💰 Giá hiện tại: {escape_markdown(price_str)} VND \\(Bắt đầu theo dõi\\)\n\n"
                
        stock_msg += f"Cập nhật lúc: {escape_markdown(now_str)}"

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
            
    if stock_changed_items and stock_msg:
        if bot_token and chat_id:
            try:
                send_telegram_message(bot_token, chat_id, stock_msg)
                print("Stock notification sent to Telegram.")
                old_state["stock_prices"] = new_stock_prices
            except Exception as e:
                print(f"Failed to send Stock Telegram message: {e}")
        else:
            # If no tokens, update local state anyway to simulate local run
            old_state["stock_prices"] = new_stock_prices

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
