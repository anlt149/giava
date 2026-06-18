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
PREFS_CACHE = {}

def migrate_prefs(prefs):
    if "favorite_stocks" not in prefs:
        prefs["favorite_stocks"] = []
    
    old_fav = prefs.get("favorite_stock")
    if old_fav:
        if old_fav not in prefs["favorite_stocks"]:
            prefs["favorite_stocks"].append(old_fav)
            
def load_prefs():
    global PREFS_CACHE
    if PREFS_CACHE:
        return PREFS_CACHE

    import os
    import json
    import base64
    import requests

    github_token = os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("VERCEL_GIT_REPO_OWNER") or "anlt149"
    repo = os.environ.get("VERCEL_GIT_REPO_SLUG") or "giava"

    # Try fetching from GitHub API first if token is configured
    if github_token:
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{PREFS_FILE}"
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Telegram-Stock-Bot"
            }
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                content_b64 = resp.json().get("content", "")
                if content_b64:
                    content_bytes = base64.b64decode(content_b64)
                    PREFS_CACHE = json.loads(content_bytes.decode("utf-8"))
                    migrate_prefs(PREFS_CACHE)
                    print("Successfully loaded prefs from GitHub.")
                    return PREFS_CACHE
        except Exception as e:
            print(f"Error loading prefs from GitHub: {e}")

    # Fallback to local file
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                PREFS_CACHE = json.load(f)
                migrate_prefs(PREFS_CACHE)
                print("Successfully loaded prefs from local file.")
                return PREFS_CACHE
        except Exception as e:
            print(f"Error reading local prefs: {e}")
            
    return {}

def save_prefs(prefs):
    global PREFS_CACHE
    PREFS_CACHE = prefs

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

def add_transaction(asset_name: str, price: float, quantity: float, action: str):
    """
    Add a buy or sell transaction.
    action: 'buy' or 'sell'
    Returns (success: bool, error_message: str)
    """
    asset_name = asset_name.strip().upper()
    if quantity <= 0:
        return False, "Số lượng phải lớn hơn 0\\!"
    if price <= 0:
        return False, "Giá phải lớn hơn 0\\!"

    prefs = load_prefs()
    portfolio = prefs.get("portfolio", {})
    assets = portfolio.get("assets", {})

    asset_data = assets.get(asset_name, {
        "quantity": 0.0,
        "dca_price": 0.0,
        "realized_pnl": 0.0
    })

    old_qty = asset_data.get("quantity", 0.0)
    old_dca = asset_data.get("dca_price", 0.0)
    realized_pnl = asset_data.get("realized_pnl", 0.0)

    if action == "buy":
        new_qty = old_qty + quantity
        new_dca = ((old_qty * old_dca) + (price * quantity)) / new_qty if new_qty > 0 else 0.0
        
        asset_data["quantity"] = new_qty
        asset_data["dca_price"] = new_dca
    elif action == "sell":
        if quantity > old_qty:
            return False, f"Không đủ số lượng để bán\\! Bạn chỉ có `{escape_markdown(f'{old_qty:g}')}`."
        new_qty = old_qty - quantity
        realized_pnl += (price - old_dca) * quantity
        
        asset_data["quantity"] = new_qty
        asset_data["realized_pnl"] = realized_pnl
        # DCA price remains the same
    else:
        return False, "Hành động không hợp lệ\\!"

    assets[asset_name] = asset_data
    portfolio["assets"] = assets
    prefs["portfolio"] = portfolio
    save_prefs(prefs)
    return True, ""

def clear_portfolio():
    prefs = load_prefs()
    prefs["portfolio"] = {"assets": {}}
    save_prefs(prefs)
    return True

def get_portfolio_report():
    prefs = load_prefs()
    portfolio = prefs.get("portfolio", {})
    assets = portfolio.get("assets", {})

    if not assets:
        return "💼 *Danh mục đầu tư của bạn đang trống\\!*\nSử dụng `/buy` để thêm tài sản\\! Ví dụ: `/buy FPT 120000 100`"

    # Filter out assets with 0 quantity but keep their realized PnL in mind
    active_assets = {k: v for k, v in assets.items() if v.get("quantity", 0.0) > 0}
    realized_pnl_total = sum(v.get("realized_pnl", 0.0) for v in assets.values())

    if not active_assets and realized_pnl_total == 0.0:
        return "💼 *Danh mục đầu tư của bạn đang trống\\!*\nSử dụng `/buy` để thêm tài sản\\! Ví dụ: `/buy FPT 120000 100`"

    gold_prices = None
    total_cost = 0.0
    total_value = 0.0
    
    msg = "💼 *DANH MỤC TÀI SẢN*\n\n"
    
    for asset_name, data in sorted(assets.items()):
        qty = data.get("quantity", 0.0)
        dca = data.get("dca_price", 0.0)
        realized = data.get("realized_pnl", 0.0)
        
        # If we have realized PnL but no holdings, we just display the realized PnL at the end
        if qty <= 0:
            continue
            
        current_price = None
        if asset_name == "GOLD":
            try:
                from gold_api import get_vietnam_gold_prices
                if not gold_prices:
                    gold_prices = get_vietnam_gold_prices()
                if "sjc" in gold_prices:
                    current_price = float(gold_prices["sjc"]["buy"])
            except Exception as e:
                print(f"Error getting gold price for portfolio: {e}")
        else:
            stock_data = get_stock_price(asset_name)
            if stock_data:
                current_price = stock_data["price"]

        unit = "lượng" if asset_name == "GOLD" else "CP"
        cost_basis = qty * dca
        total_cost += cost_basis
        
        msg += f"⚫ *{escape_markdown(asset_name)}*\n"
        msg += f"\\- Số lượng: {escape_markdown(f'{qty:g}')} {unit}\n"
        msg += f"\\- Giá DCA: {escape_markdown(format_currency(dca))} VND\n"
        
        if current_price:
            current_val = qty * current_price
            total_value += current_val
            unrealized_pnl = current_val - cost_basis
            pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0
            
            pnl_sign = "+" if unrealized_pnl > 0 else ""
            indicator = "🟢" if unrealized_pnl > 0 else ("🔴" if unrealized_pnl < 0 else "⚪")
            
            msg += f"\\- Giá hiện tại: {escape_markdown(format_currency(current_price))} VND\n"
            msg += f"\\- Giá trị hiện tại: {escape_markdown(format_currency(current_val))} VND\n"
            msg += f"\\- Lợi nhuận: {indicator} {escape_markdown(pnl_sign)}{escape_markdown(format_currency(unrealized_pnl))} VND \\({escape_markdown(pnl_sign)}{escape_markdown(f'{pnl_percent:.2f}')}%\\)\n"
        else:
            total_value += cost_basis  # assume no change
            msg += "⚠️ *Không thể lấy giá hiện tại\\!*\n"
            msg += f"\\- Giá trị đầu tư: {escape_markdown(format_currency(cost_basis))} VND\n"
            
        msg += "\n"
        
    msg += "───────────────────\n"
    msg += "📊 *TỔNG KẾT TÀI SẢN*\n"
    msg += f"\\- Tổng vốn đầu tư: {escape_markdown(format_currency(total_cost))} VND\n"
    msg += f"\\- Tổng giá trị hiện tại: {escape_markdown(format_currency(total_value))} VND\n"
    
    total_unrealized_pnl = total_value - total_cost
    total_pnl_percent = (total_unrealized_pnl / total_cost * 100) if total_cost else 0.0
    total_pnl_sign = "+" if total_unrealized_pnl > 0 else ""
    total_indicator = "🟢" if total_unrealized_pnl > 0 else ("🔴" if total_unrealized_pnl < 0 else "⚪")
    
    msg += f"\\- Lợi nhuận chưa chốt: {total_indicator} {escape_markdown(total_pnl_sign)}{escape_markdown(format_currency(total_unrealized_pnl))} VND \\({escape_markdown(total_pnl_sign)}{escape_markdown(f'{total_pnl_percent:.2f}')}%\\)\n"
    
    realized_sign = "+" if realized_pnl_total > 0 else ("-" if realized_pnl_total < 0 else "")
    realized_indicator = "🟢" if realized_pnl_total > 0 else ("🔴" if realized_pnl_total < 0 else "⚪")
    msg += f"\\- Lợi nhuận đã chốt: {realized_indicator} {escape_markdown(realized_sign)}{escape_markdown(format_currency(abs(realized_pnl_total)))} VND\n"
    
    return msg

def add_favorite_stock(ticker: str):
    ticker = ticker.strip().upper()
    prefs = load_prefs()
    favs = prefs.get("favorite_stocks", [])
    if ticker not in favs:
        favs.append(ticker)
        prefs["favorite_stocks"] = favs
        save_prefs(prefs)
        return True, f"Đã thêm `{ticker}` vào danh sách theo dõi\\!"
    return False, f"`{ticker}` đã có sẵn trong danh sách theo dõi\\!"

def remove_favorite_stock(ticker: str):
    ticker = ticker.strip().upper()
    prefs = load_prefs()
    favs = prefs.get("favorite_stocks", [])
    if ticker in favs:
        favs.remove(ticker)
        prefs["favorite_stocks"] = favs
        save_prefs(prefs)
        return True, f"Đã xoá `{ticker}` khỏi danh sách theo dõi\\!"
    return False, f"`{ticker}` không có trong danh sách theo dõi\\!"

def build_watchlist_report(tickers):
    if not tickers:
        return "📈 *Danh sách theo dõi của bạn đang trống\\!*\nSử dụng `/set_stock <TICKER>` để thêm cổ phiếu\\!"
        
    now_str = datetime.datetime.now().strftime("%H:%M %d/%m/%Y")
    
    msg = "📈 *DANH SÁCH THEO DÕI CỔ PHIẾU*\n\n"
    
    for ticker in sorted(tickers):
        stock_data = get_stock_price(ticker)
        if stock_data:
            price = stock_data["price"]
            change = stock_data["change"]
            change_percent = stock_data["change_percent"]
            
            sign = "+" if change > 0 else ""
            indicator = "🟢" if change > 0 else ("🔴" if change < 0 else "⚪")
            
            price_str = format_currency(price)
            change_str = format_currency(change)
            
            msg += f"⚫ *{escape_markdown(ticker)}*\n"
            msg += f"💰 Giá: {escape_markdown(price_str)} VND\n"
            msg += f"📊 Biến động: {indicator} {escape_markdown(sign)}{escape_markdown(price_str if change == 0 else change_str)} VND \\({escape_markdown(sign)}{escape_markdown(f'{change_percent:.2f}')}%\\)\n\n"
        else:
            msg += f"⚫ *{escape_markdown(ticker)}*\n⚠️ Không thể lấy thông tin giá lúc này\\!\n\n"
            
    msg += f"Cập nhật lúc: {escape_markdown(now_str)}"
    return msg
