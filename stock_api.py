import requests
import datetime

def get_stock_price(ticker: str):
    """
    Fetch stock price from Yahoo Finance.
    Converts ticker to uppercase. Appends .VN if no extension is provided.
    """
    ticker = ticker.strip().upper()
    yahoo_ticker = ticker
    if "." not in yahoo_ticker:
        yahoo_ticker = f"{ticker}.VN"
        
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        result = data.get("chart", {}).get("result")
        if not result or len(result) == 0:
            return None
            
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose")
        
        if price is None:
            # Fallback to last close if regularMarketPrice is missing
            indicators = result[0].get("indicators", {})
            close_prices = indicators.get("quote", [{}])[0].get("close", [])
            # Filter out None values
            valid_closes = [c for c in close_prices if c is not None]
            if valid_closes:
                price = valid_closes[-1]
            else:
                return None
                
        if prev_close is None:
            prev_close = price
            
        change = price - prev_close
        change_percent = (change / prev_close * 100) if prev_close else 0.0
        
        return {
            "ticker": ticker,
            "yahoo_ticker": yahoo_ticker,
            "price": float(price),
            "prev_close": float(prev_close),
            "change": float(change),
            "change_percent": float(change_percent),
            "currency": meta.get("currency", "VND")
        }
    except Exception as e:
        print(f"Error fetching stock {ticker}: {e}")
        return None

def format_currency(amount):
    return "{:,.0f}".format(amount).replace(',', '.')

def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in str(text))

def build_stock_report_message(stock_data):
    if not stock_data:
        return "⚠️ *Không thể lấy thông tin cổ phiếu lúc này\\!*"
        
    now_str = datetime.datetime.now().strftime("%H:%M %d/%m/%Y")
    
    ticker = stock_data["ticker"]
    price = stock_data["price"]
    change = stock_data["change"]
    change_percent = stock_data["change_percent"]
    
    sign = "+" if change > 0 else ""
    # Format changes
    price_str = format_currency(price)
    change_str = format_currency(change)
    
    # We want indicators like 🟢 or 🔴
    indicator = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
    
    msg = f"📈 *BÁO CÁO CỔ PHIẾU VN*\n\n"
    msg += f"🔠 *Mã cổ phiếu:* {escape_markdown(ticker)}\n"
    msg += f"💰 *Giá hiện tại:* {escape_markdown(price_str)} VND\n"
    msg += f"📊 *Biến động:* {indicator} {escape_markdown(sign)}{escape_markdown(price_str if change == 0 else change_str)} VND \\({escape_markdown(sign)}{escape_markdown(f'{change_percent:.2f}')}%\\)\n\n"
    msg += f"Cập nhật lúc: {escape_markdown(now_str)}"
    return msg

PREFS_FILE = "user_prefs.json"

def load_prefs():
    import os
    import json
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading local prefs: {e}")
    return {}

def save_prefs(prefs):
    import os
    import json
    import base64
    import requests

    # Save locally
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except Exception as e:
        print(f"Error saving local prefs: {e}")

    github_token = os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("VERCEL_GIT_REPO_OWNER") or "anlt149"
    repo = os.environ.get("VERCEL_GIT_REPO_SLUG") or "giava"

    if github_token:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{PREFS_FILE}"
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Telegram-Stock-Bot"
        }
        
        # 1. Get current file SHA
        sha = None
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                sha = resp.json().get("sha")
        except Exception as e:
            print(f"Failed to get file SHA from GitHub: {e}")
            
        # 2. Update the file
        content_bytes = json.dumps(prefs, indent=2).encode("utf-8")
        content_b64 = base64.b64encode(content_bytes).decode("utf-8")
        
        payload = {
            "message": "chore: update user stock preferences via bot",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha
            
        try:
            resp = requests.put(url, headers=headers, json=payload, timeout=10)
            if resp.status_code in [200, 201]:
                print("Successfully updated user_prefs.json on GitHub.")
            else:
                print(f"Failed to update user_prefs.json on GitHub: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Error pushing user_prefs.json to GitHub: {e}")
