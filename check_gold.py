import os
import json
import datetime
import requests
from gold_api import get_vietnam_gold_prices, build_gold_report_message

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
        
    try:
        current_prices = get_vietnam_gold_prices()
    except Exception as e:
        print(f"Error fetching gold prices: {e}")
        return

    if 'sjc' not in current_prices:
        print("SJC price not found in the API response.")
        return
        
    current_sjc_buy = current_prices['sjc']['buy']
    current_sjc_sell = current_prices['sjc']['sell']
    
    # Load state
    old_state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                old_state = json.load(f)
        except Exception as e:
            print(f"Could not read state file: {e}")
            
    old_sjc_buy = old_state.get("sjc_buy", 0)
    old_sjc_sell = old_state.get("sjc_sell", 0)
    
    # Compare (only Vietnam SJC price dictates if an alert is sent)
    if current_sjc_buy != old_sjc_buy or current_sjc_sell != old_sjc_sell:
        print(f"Price changed! Old: {old_sjc_buy}/{old_sjc_sell} -> New: {current_sjc_buy}/{current_sjc_sell}")
        
        diff_buy = current_sjc_buy - old_sjc_buy if old_sjc_buy != 0 else None
        diff_sell = current_sjc_sell - old_sjc_sell if old_sjc_sell != 0 else None
        
        msg = build_gold_report_message(diff_buy=diff_buy, diff_sell=diff_sell)
        
        if bot_token and chat_id:
            try:
                send_telegram_message(bot_token, chat_id, msg)
                print("Notification sent to Telegram.")
            except Exception as e:
                print(f"Failed to send Telegram message: {e}")
        
        # Save new state
        new_state = {
            "last_updated": datetime.datetime.utcnow().isoformat() + "Z",
            "sjc_buy": current_sjc_buy,
            "sjc_sell": current_sjc_sell
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(new_state, f, indent=2)
    else:
        print("No change in Vietnam gold price.")

if __name__ == "__main__":
    main()
