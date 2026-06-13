import requests
import datetime

BTMC_API_URL = "http://api.btmc.vn/api/BTMCAPI/getpricebtmc?key=3hP56Sv7%24%25"
YAHOO_FINANCE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"

def get_vietnam_gold_prices():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    response = requests.get(BTMC_API_URL, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    results = {}
    items = data.get("DataList", {}).get("Data", [])
    for item in items:
        row_id = item.get("@row", "")
        if not row_id:
            continue
            
        name = item.get(f"@n_{row_id}", "").upper()
        buy = item.get(f"@pb_{row_id}", "0")
        sell = item.get(f"@ps_{row_id}", "0")
        
        if "SJC" in name:
            results['sjc'] = {
                'name': item.get(f"@n_{row_id}", ""),
                'buy': int(buy) * 10,
                'sell': int(sell) * 10
            }
            break
            
    return results

def get_us_gold_price():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(YAHOO_FINANCE_URL, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    try:
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except (KeyError, IndexError, TypeError) as e:
        print(f"Error parsing Yahoo Finance data: {e}")
        return None

def format_currency(amount):
    return "{:,.0f}".format(amount).replace(',', '.')

def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in str(text))

def build_gold_report_message(diff_buy=None, diff_sell=None):
    vn_prices = get_vietnam_gold_prices()
    us_price = get_us_gold_price()
    
    if 'sjc' not in vn_prices:
        return "Không thể lấy được giá vàng SJC lúc này."
        
    sjc = vn_prices['sjc']
    now_str = datetime.datetime.now().strftime("%H:%M %d/%m/%Y")
    
    msg = f"🔔 *BÁO CÁO GIÁ VÀNG*\n\n"
    msg += f"🇻🇳 *{escape_markdown(sjc['name'])}*\n"
    
    # Buy line
    buy_str = f"\\- Mua vào: {escape_markdown(format_currency(sjc['buy']))} VND"
    if diff_buy:
        sign = "+" if diff_buy > 0 else ""
        buy_str += f" \\({escape_markdown(sign)}{escape_markdown(format_currency(diff_buy))}\\)"
    msg += buy_str + "\n"
    
    # Sell line
    sell_str = f"\\- Bán ra: {escape_markdown(format_currency(sjc['sell']))} VND"
    if diff_sell:
        sign = "+" if diff_sell > 0 else ""
        sell_str += f" \\({escape_markdown(sign)}{escape_markdown(format_currency(diff_sell))}\\)"
    msg += sell_str + "\n\n"
    
    # US Gold
    if us_price:
        msg += f"🇺🇸 *Vàng Thế Giới \\(USD/oz\\):* $\\{escape_markdown(format_currency(us_price))}\n\n"
        
    msg += f"Cập nhật lúc: {escape_markdown(now_str)}"
    return msg
