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
    requests.post(url, json=payload, timeout=10)

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
        
        if text.startswith("/check") and chat_id and bot_token:
            print("Processing /check command...")
            # Generate the report
            try:
                import sys
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from gold_api import build_gold_report_message
                
                msg = build_gold_report_message()
            except Exception as e:
                print(f"Error building gold report message: {e}")
                msg = f"Đã xảy ra lỗi khi lấy giá vàng: {e}"
                
            # Send message back
            try:
                send_telegram_message(bot_token, chat_id, msg)
                print("Sent message to Telegram successfully.")
            except Exception as e:
                print(f"Error sending Telegram message: {e}")
        else:
            if not bot_token:
                print("Warning: TELEGRAM_BOT_TOKEN environment variable is not set on Vercel!")
            if not text.startswith("/check"):
                print(f"Ignored message: text does not start with /check (got '{text}')")
            
        # Always return 200 OK so Telegram knows we received the webhook
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
