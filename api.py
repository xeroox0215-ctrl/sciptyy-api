import asyncio
import sqlite3
import json
import hmac
import hashlib
import aiohttp
import os
import random
import time
from urllib.parse import parse_qsl
from aiohttp import web

BOT_TOKEN = "9238657777:AAEBrmS9VDOHsrqL8vAGXNVJP3Lrro3_Fzs"
DB_FILE = "shop.db"
PORT = int(os.environ.get("PORT", 8080))

LAVA_API_KEY = "bIsavHNsuOtX2t4ajkvVmC15baF3AezsLXVXdsFsQnt6IjPhiOAduyGiJhpxCq0R"
LAVA_TOPUP_OFFER_ID = "d937583a-6dc5-46e0-982d-8590351fa7bc"
LAVA_EMAIL = "test@mail.ru"

COUNTRIES = {
    "usa": {"name": "🇺🇸 США", "price": 46},
    "canada": {"name": "🇨🇦 Канада", "price": 99},
    "colombia": {"name": "🇨🇴 Колумбия", "price": 99},
    "uk": {"name": "🇬🇧 Великобритания", "price": 125},
    "bangladesh": {"name": "🇧🇩 Бангладеш", "price": 99},
    "argentina": {"name": "🇦🇷 Аргентина", "price": 125},
    "uzbekistan": {"name": "🇺🇿 Узбекистан", "price": 175},
    "brazil": {"name": "🇧🇷 Бразилия", "price": 175},
    "thailand": {"name": "🇹🇭 Таиланд", "price": 199},
    "france": {"name": "🇫🇷 Франция", "price": 199},
    "germany": {"name": "🇩🇪 Германия", "price": 249},
    "kazakhstan": {"name": "🇰🇿 Казахстан", "price": 249},
    "ukraine": {"name": "🇺🇦 Украина", "price": 249},
    "poland": {"name": "🇵🇱 Польша", "price": 249},
    "mauritania": {"name": "🇲🇷 Мавритания", "price": 299}
}

# Создаем базу, если её нет
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, discount INTEGER DEFAULT 0, balance REAL DEFAULT 0, last_roll INTEGER DEFAULT 0, last_prize TEXT DEFAULT '', referrer_id INTEGER DEFAULT 0, ref_earnings REAL DEFAULT 0, cases INTEGER DEFAULT 0, vip_cases INTEGER DEFAULT 0)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, price REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS stock (country TEXT PRIMARY KEY, amount INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS promos (code TEXT PRIMARY KEY, discount INTEGER, limit_count INTEGER, used_count INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

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

async def send_admin_log(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": 1494459013, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload)
    except:
        pass

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT discount, balance, last_roll, cases, vip_cases FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row: return {"discount": row[0], "balance": float(row[1]), "last_roll": row[2], "cases": row[3], "vip_cases": row[4]}
    return {"discount": 0, "balance": 0.0, "last_roll": 0, "cases": 0, "vip_cases": 0}

async def api_profile(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user["id"]
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, user.get("username", "")))
    conn.commit()
    
    profile = get_user(user_id)
    
    cursor.execute("SELECT item_name, price, date FROM purchases WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    purchases = [{"name": r[0], "price": r[1], "date": r[2]} for r in cursor.fetchall()]

    cursor.execute("SELECT country, amount FROM stock")
    stock_dict = {row[0]: row[1] for row in cursor.fetchall()}
    
    shop_items = []
    for code, info in COUNTRIES.items():
        shop_items.append({"code": code, "name": info["name"], "price": info["price"], "stock": stock_dict.get(code, 0)})
        
    conn.close()
    return web.json_response({"status": "ok", "profile": profile, "purchases": purchases, "shop": shop_items})

async def api_roll(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user["id"]
    profile = get_user(user_id)
    now = int(time.time())
    
    if user_id != 1494459013 and now - profile["last_roll"] < 86400:
        left = 86400 - (now - profile["last_roll"])
        return web.json_response({"error": f"Ждать: {left//3600} ч {(left%3600)//60} мин"}, status=400)
        
    amount = random.randint(1, 3)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ?, last_roll = ? WHERE user_id = ?", (amount, now, user_id))
    conn.commit()
    conn.close()
    
    await send_admin_log(f"🎰 <b>Рулетка (Сайт)</b>\n👤 @{user.get('username', '')}\n💰 Выиграл: {amount} ₽")
    return web.json_response({"status": "ok", "prize": f"{amount} ₽", "amount": amount})

async def api_buy(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    
    data = await request.json()
    country = data.get("country")
    method = data.get("method")
    user_id = user["id"]
    
    if country not in COUNTRIES: return web.json_response({"error": "Товар не найден"}, status=404)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT amount FROM stock WHERE country = ?", (country,))
    stock = cursor.fetchone()
    if not stock or stock[0] <= 0:
        conn.close()
        return web.json_response({"error": "Нет в наличии"}, status=400)
        
    info = COUNTRIES[country]
    profile = get_user(user_id)
    final_price = int(info['price'] * (1 - profile['discount'] / 100))
    if final_price < 1: final_price = 1
    
    if method == "balance":
        if profile['balance'] < final_price:
            conn.close()
            return web.json_response({"error": "Недостаточно средств"}, status=400)
            
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (final_price, user_id))
        cursor.execute("UPDATE stock SET amount = amount - 1 WHERE country = ?", (country,))
        cursor.execute("INSERT INTO purchases (user_id, item_name, price) VALUES (?, ?, ?)", (user_id, info['name'], final_price))
        conn.commit()
        conn.close()
        
        await send_admin_log(f"🛒 <b>Покупка (Сайт)</b>\n👤 @{user.get('username', '')}\n🌍 {info['name']}\n💰 {final_price} ₽")
        return web.json_response({"status": "ok", "message": "Успешно куплено!", "item": info['name']})
        
    return web.json_response({"error": "Метод не поддерживается"}, status=400)

async def api_topup(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)

    data = await request.json()
    amount = float(data.get("amount", 0))
    if amount < 50: return web.json_response({"error": "Минимум 50 рублей"}, status=400)

    headers = {"X-Api-Key": LAVA_API_KEY, "Content-Type": "application/json", "Accept": "application/json"}
    payload = {"email": LAVA_EMAIL, "offerId": LAVA_TOPUP_OFFER_ID, "currency": "RUB", "amount": amount, "clientUtm": {"source": "site", "clientId": str(user["id"])}}
    
    async with aiohttp.ClientSession() as session:
        async with session.post("https://gate.lava.top/api/v3/invoice", json=payload, headers=headers) as resp:
            if resp.status in (200, 201):
                res_data = await resp.json()
                return web.json_response({"url": res_data.get("url") or res_data.get("paymentUrl")})
            return web.json_response({"error": "Ошибка Lava API"}, status=500)

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS": response = web.Response()
    else: response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'X-Telegram-Init-Data, Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

app = web.Application(middlewares=[cors_middleware])
app.router.add_get('/api/profile', api_profile)
app.router.add_post('/api/roll', api_roll)
app.router.add_post('/api/buy', api_buy)
app.router.add_post('/api/topup', api_topup)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=PORT)
