import json
import os
import requests
from http.server import BaseHTTPRequestHandler
import sys

# Ensure Vercel can find gold_api in the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from gold_api import build_gold_report_message
except ImportError:
    pass # fallback if imported directly

def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    resp = requests.post(url, json=payload, timeout=10)
    print(f"Telegram response: {resp.status_code} - {resp.text}")
    resp.raise_for_status()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_response(200)
            self.end_headers()
            return
            
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
        # Parse Telegram message
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        print(f"Received Telegram webhook request. Text: '{text}', Chat ID: '{chat_id}', Bot Token Configured: {bot_token is not None}")
        
        if chat_id and bot_token:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            if text.startswith("/gold"):
                print("Processing /gold command...")
                try:
                    from gold_api import build_gold_report_message
                    msg = build_gold_report_message()
                except Exception as e:
                    print(f"Error building gold report message: {e}")
                    msg = "⚠️ *Đã xảy ra lỗi khi lấy giá vàng\\. Vui lòng thử lại sau\\!*"
                
                try:
                    send_telegram_message(bot_token, chat_id, msg)
                except Exception as e:
                    print(f"Error sending Telegram message: {e}")
                    
            elif text.startswith("/set_stock"):
                print("Processing /set_stock command...")
                parts = text.split()
                if len(parts) < 2:
                    msg = "⚠️ *Vui lòng nhập mã cổ phiếu\\! Ví dụ: `/set_stock FPT`*"
                else:
                    ticker = parts[1].strip().upper()
                    try:
                        from stock_api import get_stock_price, load_prefs, save_prefs
                        stock_data = get_stock_price(ticker)
                        if not stock_data:
                            msg = f"⚠️ *Không tìm thấy mã cổ phiếu `{ticker}` hoặc lỗi kết nối\\!*"
                        else:
                            prefs = load_prefs()
                            prefs["favorite_stock"] = ticker
                            save_prefs(prefs)
                            msg = f"✅ *Đã lưu `{ticker}` làm cổ phiếu yêu thích của bạn\\!*"
                    except Exception as e:
                        print(f"Error setting stock: {e}")
                        msg = "⚠️ *Đã xảy ra lỗi khi lưu mã cổ phiếu\\!*"
                
                try:
                    send_telegram_message(bot_token, chat_id, msg)
                except Exception as e:
                    print(f"Error sending Telegram message: {e}")
                    
            elif text.startswith("/stock"):
                print("Processing /stock command...")
                parts = text.split()
                ticker = None
                if len(parts) >= 2:
                    ticker = parts[1].strip().upper()
                
                try:
                    from stock_api import get_stock_price, load_prefs, build_stock_report_message
                    if not ticker:
                        prefs = load_prefs()
                        ticker = prefs.get("favorite_stock")
                        
                    if not ticker:
                        msg = "⚠️ *Bạn chưa cài đặt cổ phiếu yêu thích\\. Sử dụng `/set_stock <TICKER>` hoặc `/stock <TICKER>`\\!*"
                    else:
                        stock_data = get_stock_price(ticker)
                        msg = build_stock_report_message(stock_data)
                except Exception as e:
                    print(f"Error checking stock price: {e}")
                    msg = "⚠️ *Đã xảy ra lỗi khi lấy giá cổ phiếu\\. Vui lòng thử lại sau\\!*"
                    
                try:
                    send_telegram_message(bot_token, chat_id, msg)
                except Exception as e:
                    print(f"Error sending Telegram message: {e}")
        else:
            if not bot_token:
                print("Warning: TELEGRAM_BOT_TOKEN environment variable is not set!")
            if not chat_id:
                print("Warning: chat_id is missing from update!")
            if not (text.startswith("/gold") or text.startswith("/set_stock") or text.startswith("/stock")):
                print(f"Ignored message: '{text}' (unrecognized command)")
            
        # Always return 200 OK so Telegram knows we received the webhook
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
