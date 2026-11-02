import asyncio
import sqlite3
import json
import hmac
import hashlib
import aiohttp
import os
from urllib.parse import parse_qsl
from aiohttp import web

BOT_TOKEN = "9238657777:AAEBrmS9VDOHsrqL8vAGXNVJP3Lrro3_Fzs"
DB_FILE = "shop.db"
PORT = int(os.environ.get("PORT", 8080))

LAVA_API_KEY = "bIsavHNsuOtX2t4ajkvVmC15baF3AezsLXVXdsFsQnt6IjPhiOAduyGiJhpxCq0R"
LAVA_TOPUP_OFFER_ID = "d937583a-6dc5-46e0-982d-8590351fa7bc"
LAVA_EMAIL = "test@mail.ru"

COUNTRIES = {
    "usa": {"name": "🇺🇸 США", "price": 46, "stars": 46},
    "canada": {"name": "🇨🇦 Канада", "price": 99, "stars": 100},
    "colombia": {"name": "🇨🇴 Колумбия", "price": 99, "stars": 100},
    "uk": {"name": "🇬🇧 Великобритания", "price": 125, "stars": 125},
    "bangladesh": {"name": "🇧🇩 Бангладеш", "price": 99, "stars": 100},
    "argentina": {"name": "🇦🇷 Аргентина", "price": 125, "stars": 125},
    "uzbekistan": {"name": "🇺🇿 Узбекистан", "price": 175, "stars": 150},
    "brazil": {"name": "🇧🇷 Бразилия", "price": 175, "stars": 175},
    "thailand": {"name": "🇹🇭 Таиланд", "price": 199, "stars": 199},
    "france": {"name": "🇫🇷 Франция", "price": 199, "stars": 199},
    "germany": {"name": "🇩🇪 Германия", "price": 249, "stars": 249},
    "kazakhstan": {"name": "🇰🇿 Казахстан", "price": 249, "stars": 249},
    "ukraine": {"name": "🇺🇦 Украина", "price": 249, "stars": 249},
    "poland": {"name": "🇵🇱 Польша", "price": 249, "stars": 249},
    "mauritania": {"name": "🇲🇷 Мавритания", "price": 299, "stars": 300}
}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, discount INTEGER DEFAULT 0, balance REAL DEFAULT 0, last_roll INTEGER DEFAULT 0, last_prize TEXT DEFAULT '', referrer_id INTEGER DEFAULT 0, ref_earnings REAL DEFAULT 0, cases INTEGER DEFAULT 0, vip_cases INTEGER DEFAULT 0)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, price REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS stock (country TEXT PRIMARY KEY, amount INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

# Инициализация базы при старте
init_db()

def validate_init_data(init_data: str) -> dict:
    try:
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data: return None
        hash_value = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if calculated_hash == hash_value:
            return json.loads(parsed_data["user"])
        return None
    except Exception:
        return None

def get_db_data(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT discount, balance, ref_earnings, cases, vip_cases FROM users WHERE user_id = ?", (user_id,))
    user_row = cursor.fetchone()
    if user_row:
        profile = {"discount": user_row[0], "balance": float(user_row[1]), "ref_earnings": float(user_row[2]), "cases": user_row[3], "vip_cases": user_row[4]}
    else:
        profile = {"discount": 0, "balance": 0.0, "ref_earnings": 0.0, "cases": 0, "vip_cases": 0}
    
    cursor.execute("SELECT item_name, price, date FROM purchases WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    purchases = [{"name": r[0], "price": r[1], "date": r[2]} for r in cursor.fetchall()]

    cursor.execute("SELECT country, amount FROM stock")
    stock_rows = cursor.fetchall()
    stock_dict = {row[0]: row[1] for row in stock_rows}
    
    shop_items = []
    for code, info in COUNTRIES.items():
        shop_items.append({
            "code": code,
            "name": info["name"],
            "price": info["price"],
            "stars": info["stars"],
            "stock": stock_dict.get(code, 0)
        })
        
    conn.close()
    return profile, purchases, shop_items

async def api_profile(request):
    try:
        init_data = request.headers.get("X-Telegram-Init-Data")
        user = validate_init_data(init_data)
        if not user: return web.json_response({"error": "Unauthorized"}, status=401)
            
        profile, purchases, shop_items = get_db_data(user["id"])
        return web.json_response({"status": "ok", "profile": profile, "purchases": purchases, "shop": shop_items})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def api_topup(request):
    try:
        init_data = request.headers.get("X-Telegram-Init-Data")
        user = validate_init_data(init_data)
        if not user: return web.json_response({"error": "Unauthorized"}, status=401)

        data = await request.json()
        amount = float(data.get("amount", 0))
        if amount < 50: return web.json_response({"error": "Минимум 50 рублей"}, status=400)

        headers = {"X-Api-Key": LAVA_API_KEY, "Content-Type": "application/json", "Accept": "application/json"}
        payload = {
            "email": LAVA_EMAIL, 
            "offerId": LAVA_TOPUP_OFFER_ID, 
            "currency": "RUB", 
            "amount": amount, 
            "clientUtm": {"source": "site_topup", "clientId": str(user["id"])}
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post("https://gate.lava.top/api/v3/invoice", json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    res_data = await resp.json()
                    url = res_data.get("url") or res_data.get("paymentUrl")
                    return web.json_response({"url": url})
                else:
                    return web.json_response({"error": "Ошибка Lava API"}, status=500)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

# Добавляем заголовки CORS, чтобы сайт с GitHub мог делать запросы
@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'X-Telegram-Init-Data, Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

app = web.Application(middlewares=[cors_middleware])
app.router.add_get('/api/profile', api_profile)
app.router.add_post('/api/topup', api_topup)

if __name__ == '__main__':
    print(f"API Server запущен на порту {PORT}")
    web.run_app(app, host='0.0.0.0', port=PORT)
