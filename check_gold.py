import os
import json
import requests
import datetime

STATE_FILE = "gold_price_state.json"
API_URL = "http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3hP56Sv7%24%25"

def get_gold_prices():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(API_URL, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    results = {}
    items = data.get("DataList", {}).get("Data", [])
    for item in items:
        # The JSON keys are dynamic like @n_22, @pb_22, so we extract by values
        # Find the row ID
        row_id = item.get("@row", "")
        if not row_id:
            continue
            
        name = item.get(f"@n_{row_id}", "").upper()
        buy = item.get(f"@pb_{row_id}", "0")
        sell = item.get(f"@ps_{row_id}", "0")
        
        if "SJC" in name:
            results['sjc'] = {
                'name': item.get(f"@n_{row_id}", ""),
                'buy': int(buy) * 10,  # Multiply by 10 to get price per Lượng (tael)
                'sell': int(sell) * 10
            }
            break # Found SJC
            
    return results

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()

def escape_markdown(text):
    # Escape characters required for MarkdownV2 in Telegram
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in str(text))

def format_currency(amount):
    return "{:,.0f}".format(amount).replace(',', '.')

def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. Skipping notification.")
        
    try:
        current_prices = get_gold_prices()
    except Exception as e:
        print(f"Error fetching gold prices: {e}")
        return

    if 'sjc' not in current_prices:
        print("SJC price not found in the API response.")
        return
        
    current_sjc_buy = current_prices['sjc']['buy']
    current_sjc_sell = current_prices['sjc']['sell']
    name = current_prices['sjc']['name']
    
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
    
    # Compare
    if current_sjc_buy != old_sjc_buy or current_sjc_sell != old_sjc_sell:
        print(f"Price changed! Old: {old_sjc_buy}/{old_sjc_sell} -> New: {current_sjc_buy}/{current_sjc_sell}")
        
        # Calculate diff
        diff_buy = current_sjc_buy - old_sjc_buy
        diff_sell = current_sjc_sell - old_sjc_sell
        
        sign_buy = "+" if diff_buy > 0 else ""
        sign_sell = "+" if diff_sell > 0 else ""
        
        diff_buy_str = f"({sign_buy}{format_currency(diff_buy)})" if old_sjc_buy != 0 else ""
        diff_sell_str = f"({sign_sell}{format_currency(diff_sell)})" if old_sjc_sell != 0 else ""

        # Prepare message
        now_str = datetime.datetime.now().strftime("%H:%M %d/%m/%Y")
        msg = f"🔔 *GIÁ VÀNG THAY ĐỔI*\n\n"
        msg += f"*{escape_markdown(name)}*\n"
        msg += f"\\- Mua vào: {escape_markdown(format_currency(current_sjc_buy))} VND {escape_markdown(diff_buy_str)}\n"
        msg += f"\\- Bán ra: {escape_markdown(format_currency(current_sjc_sell))} VND {escape_markdown(diff_sell_str)}\n\n"
        msg += f"Cập nhật lúc: {escape_markdown(now_str)}"
        
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
        print("No change in gold price.")

if __name__ == "__main__":
    main()
