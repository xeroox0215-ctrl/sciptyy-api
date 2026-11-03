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
ADMIN_IDS = [1494459013, 7368843772]

LAVA_API_KEY = "bIsavHNsuOtX2t4ajkvVmC15baF3AezsLXVXdsFsQnt6IjPhiOAduyGiJhpxCq0R"
LAVA_TOPUP_OFFER_ID = "d937583a-6dc5-46e0-982d-8590351fa7bc"
LAVA_EMAIL = "test@mail.ru"

COUNTRIES = {
    "usa": {"name": "🇺🇸 США", "price": 46, "stars": 46}, "canada": {"name": "🇨🇦 Канада", "price": 99, "stars": 100},
    "colombia": {"name": "🇨🇴 Колумбия", "price": 99, "stars": 100}, "uk": {"name": "🇬🇧 Великобритания", "price": 125, "stars": 125},
    "bangladesh": {"name": "🇧🇩 Бангладеш", "price": 99, "stars": 100}, "argentina": {"name": "🇦🇷 Аргентина", "price": 125, "stars": 125},
    "uzbekistan": {"name": "🇺🇿 Узбекистан", "price": 175, "stars": 150}, "brazil": {"name": "🇧🇷 Бразилия", "price": 175, "stars": 175},
    "thailand": {"name": "🇹🇭 Таиланд", "price": 199, "stars": 199}, "france": {"name": "🇫🇷 Франция", "price": 199, "stars": 199},
    "germany": {"name": "🇩🇪 Германия", "price": 249, "stars": 249}, "kazakhstan": {"name": "🇰🇿 Казахстан", "price": 249, "stars": 249},
    "ukraine": {"name": "🇺🇦 Украина", "price": 249, "stars": 249}, "poland": {"name": "🇵🇱 Польша", "price": 249, "stars": 249},
    "mauritania": {"name": "🇲🇷 Мавритания", "price": 299, "stars": 300}
}

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, discount INTEGER DEFAULT 0, balance REAL DEFAULT 0, last_roll INTEGER DEFAULT 0, last_prize TEXT DEFAULT '', referrer_id INTEGER DEFAULT 0, ref_earnings REAL DEFAULT 0, cases INTEGER DEFAULT 0, vip_cases INTEGER DEFAULT 0)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, price REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS stock (country TEXT PRIMARY KEY, amount INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS promos (code TEXT PRIMARY KEY, discount INTEGER, limit_count INTEGER, used_count INTEGER DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS user_promos (user_id INTEGER, code TEXT, PRIMARY KEY (user_id, code))')
    cursor.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, question TEXT, answer TEXT DEFAULT NULL)')
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
        if calculated_hash == hash_value: return json.loads(parsed_data["user"])
        return None
    except Exception: return None

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT discount, balance, last_roll, cases, vip_cases FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row: return {"discount": row[0], "balance": float(row[1]), "last_roll": row[2], "cases": row[3], "vip_cases": row[4]}
    return {"discount": 0, "balance": 0.0, "last_roll": 0, "cases": 0, "vip_cases": 0}

async def send_admin_log(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": 1494459013, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session: await session.post(url, json=payload)
    except: pass

async def api_profile(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user["id"], user.get("username", "")))
    conn.commit()
    profile = get_user(user["id"])
    cursor.execute("SELECT item_name, price, date FROM purchases WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user["id"],))
    purchases = [{"name": r[0], "price": r[1], "date": r[2]} for r in cursor.fetchall()]
    cursor.execute("SELECT country, amount FROM stock")
    stock_dict = {row[0]: row[1] for row in cursor.fetchall()}
    shop_items = [{"code": k, "name": v["name"], "price": v["price"], "stock": stock_dict.get(k, 0)} for k, v in COUNTRIES.items()]
    tickets = []
    if user["id"] in ADMIN_IDS:
        cursor.execute("SELECT id, user_id, username, question, answer FROM tickets WHERE answer IS NULL ORDER BY id DESC")
        tickets = [{"id": r[0], "user_id": r[1], "username": r[2], "question": r[3], "answer": r[4]} for r in cursor.fetchall()]
    else:
        cursor.execute("SELECT id, question, answer FROM tickets WHERE user_id = ? ORDER BY id DESC", (user["id"],))
        tickets = [{"id": r[0], "question": r[1], "answer": r[2]} for r in cursor.fetchall()]
    conn.close()
    return web.json_response({"status": "ok", "profile": profile, "purchases": purchases, "shop": shop_items, "is_admin": user["id"] in ADMIN_IDS, "tickets": tickets})

async def api_roll(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    profile = get_user(user["id"])
    now = int(time.time())
    if user["id"] not in ADMIN_IDS and now - profile["last_roll"] < 86400:
        left = 86400 - (now - profile["last_roll"])
        return web.json_response({"error": f"Ждать: {left//3600} ч {(left%3600)//60} мин"}, status=400)
    amount = random.randint(1, 3)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ?, last_roll = ? WHERE user_id = ?", (amount, now, user["id"]))
    conn.commit()
    conn.close()
    return web.json_response({"status": "ok", "prize": f"{amount} ₽", "amount": amount})

async def api_buy(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    country = data.get("country")
    if country not in COUNTRIES: return web.json_response({"error": "Товар не найден"}, status=404)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT amount FROM stock WHERE country = ?", (country,))
    stock = cursor.fetchone()
    if not stock or stock[0] <= 0:
        conn.close()
        return web.json_response({"error": "Нет в наличии"}, status=400)
    info = COUNTRIES[country]
    profile = get_user(user["id"])
    final_price = int(info['price'] * (1 - profile['discount'] / 100))
    if final_price < 1: final_price = 1
    if profile['balance'] < final_price:
        conn.close()
        return web.json_response({"error": "Недостаточно средств"}, status=400)
    import uuid
    tx_id = str(uuid.uuid4())[:8].upper()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (final_price, user["id"]))
    cursor.execute("UPDATE stock SET amount = amount - 1 WHERE country = ?", (country,))
    cursor.execute("INSERT INTO purchases (user_id, item_name, price) VALUES (?, ?, ?)", (user["id"], f"{info['name']} (TX: {tx_id})", final_price))
    conn.commit()
    conn.close()
    await send_admin_log(f"🛒 <b>Покупка (Сайт, Баланс)</b>\n👤 @{user.get('username', '')}\n🌍 {info['name']}\n💰 {final_price} ₽\n🔢 TX: {tx_id}\n<i>Выдайте товар вручную!</i>")
    return web.json_response({"status": "ok", "message": "Деньги списаны! Ожидайте выдачи.", "item": info['name'], "tx_id": tx_id})

async def api_buy_stars_invoice(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    country = data.get("country")
    if country not in COUNTRIES: return web.json_response({"error": "Товар не найден"}, status=404)
    info = COUNTRIES[country]
    stars = info.get("stars", info["price"])
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createInvoiceLink"
    payload = {"title": f"Аккаунт {info['name']}", "description": "Оплата. Выдача вручную.", "payload": f"acc_stars_{country}", "currency": "XTR", "prices": [{"label": "Аккаунт", "amount": stars}]}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            res = await resp.json()
            if res.get("ok"): return web.json_response({"status": "ok", "url": res["result"]})
            return web.json_response({"error": "Ошибка Telegram API"}, status=500)

async def api_topup(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    amount = float(data.get("amount", 0))
    if amount < 50: return web.json_response({"error": "Минимум 50 рублей"}, status=400)
    headers = {"X-Api-Key": LAVA_API_KEY, "Content-Type": "application/json"}
    payload = {"email": LAVA_EMAIL, "offerId": LAVA_TOPUP_OFFER_ID, "currency": "RUB", "amount": amount, "clientUtm": {"source": "site", "clientId": str(user["id"])}}
    async with aiohttp.ClientSession() as session:
        async with session.post("https://gate.lava.top/api/v3/invoice", json=payload, headers=headers) as resp:
            if resp.status in (200, 201):
                res_data = await resp.json()
                return web.json_response({"url": res_data.get("url") or res_data.get("paymentUrl")})
            return web.json_response({"error": "Ошибка Lava API"}, status=500)

async def api_case_buy(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    case_type = data.get("type")
    price = 99 if case_type == "normal" else 249
    profile = get_user(user["id"])
    if profile["balance"] < price: return web.json_response({"error": "Недостаточно средств"}, status=400)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user["id"]))
    if case_type == "normal": cursor.execute("UPDATE users SET cases = cases + 1 WHERE user_id = ?", (user["id"],))
    else: cursor.execute("UPDATE users SET vip_cases = vip_cases + 1 WHERE user_id = ?", (user["id"],))
    conn.commit()
    conn.close()
    return web.json_response({"status": "ok", "message": "Кейс куплен!"})

async def api_case_open(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    case_type = data.get("type")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    profile = get_user(user["id"])
    if case_type == "normal" and profile["cases"] <= 0: return web.json_response({"error": "Нет кейсов"}, status=400)
    if case_type == "vip" and profile["vip_cases"] <= 0: return web.json_response({"error": "Нет кейсов"}, status=400)
    if case_type == "normal": cursor.execute("UPDATE users SET cases = cases - 1 WHERE user_id = ?", (user["id"],))
    else: cursor.execute("UPDATE users SET vip_cases = vip_cases - 1 WHERE user_id = ?", (user["id"],))
    roll = random.randint(1, 100)
    prize = {}
    if roll <= 40:
        amount = random.randint(5, 10) if case_type == "normal" else random.randint(30, 50)
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user["id"]))
        prize = {"type": "money", "value": f"{amount} ₽"}
        cursor.execute("INSERT INTO purchases (user_id, item_name, price) VALUES (?, ?, ?)", (user["id"], f"Кейс: {prize['value']}", 0))
    elif roll <= 70:
        disc = random.randint(5, 15) if case_type == "normal" else random.randint(15, 50)
        code = f"BOX-{disc}-{random.randint(1000, 9999)}"
        cursor.execute("INSERT INTO promos (code, discount, limit_count) VALUES (?, ?, ?)", (code, disc, 1))
        prize = {"type": "promo", "value": f"Промокод на {disc}%", "code": code}
        cursor.execute("INSERT INTO purchases (user_id, item_name, price) VALUES (?, ?, ?)", (user["id"], f"Кейс: Промокод {code}", 0))
    else:
        country = random.choice(list(COUNTRIES.keys()))
        prize = {"type": "account", "value": COUNTRIES[country]['name']}
        cursor.execute("INSERT INTO purchases (user_id, item_name, price) VALUES (?, ?, ?)", (user["id"], f"Кейс: Аккаунт {prize['value']}", 0))
    conn.commit()
    conn.close()
    await send_admin_log(f"📦 <b>Кейс (Сайт)</b>\n👤 @{user.get('username', '')}\n🎁 {prize['value']}")
    return web.json_response({"status": "ok", "prize": prize})

async def api_promo_activate(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    code = data.get("code", "").strip().upper()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT discount, limit_count, used_count FROM promos WHERE code = ?", (code,))
    promo = cursor.fetchone()
    if not promo:
        conn.close()
        return web.json_response({"error": "Такого промокода нет"}, status=400)
    discount, limit_count, used_count = promo
    if used_count >= limit_count:
        conn.close()
        return web.json_response({"error": "Лимит активаций исчерпан"}, status=400)
    cursor.execute("SELECT * FROM user_promos WHERE user_id = ? AND code = ?", (user["id"], code))
    if cursor.fetchone():
        conn.close()
        return web.json_response({"error": "Вы уже активировали этот код"}, status=400)
    cursor.execute("UPDATE users SET discount = ? WHERE user_id = ?", (discount, user["id"]))
    cursor.execute("INSERT INTO user_promos (user_id, code) VALUES (?, ?)", (user["id"], code))
    cursor.execute("UPDATE promos SET used_count = used_count + 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return web.json_response({"status": "ok", "message": f"Промокод активирован! Скидка {discount}%"})

async def api_admin_money(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user or user["id"] not in ADMIN_IDS: return web.json_response({"error": "Доступ запрещен"}, status=403)
    data = await request.json()
    amount = float(data.get("amount", 0))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user["id"]))
    conn.commit()
    conn.close()
    return web.json_response({"status": "ok", "message": f"Начислено {amount} ₽"})

async def api_admin_stock(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user or user["id"] not in ADMIN_IDS: return web.json_response({"error": "Доступ запрещен"}, status=403)
    data = await request.json()
    country = data.get("country")
    amount = int(data.get("amount", 0))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO stock (country, amount) VALUES (?, ?)", (country, amount))
    conn.commit()
    conn.close()
    return web.json_response({"status": "ok", "message": "Склад обновлен"})

async def api_admin_promo(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user or user["id"] not in ADMIN_IDS: return web.json_response({"error": "Доступ запрещен"}, status=403)
    data = await request.json()
    code = data.get("code", "").strip().upper()
    discount = int(data.get("discount", 5))
    limit = int(data.get("limit", 1))
    if not code: return web.json_response({"error": "Пустой код"}, status=400)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO promos (code, discount, limit_count) VALUES (?, ?, ?)", (code, discount, limit))
        conn.commit()
        res = {"status": "ok", "message": f"Промокод {code} создан"}
    except sqlite3.IntegrityError:
        res = {"error": "Такой промокод уже есть"}
    conn.close()
    return web.json_response(res)

async def api_create_ticket(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user: return web.json_response({"error": "Unauthorized"}, status=401)
    data = await request.json()
    question = data.get("question", "").strip()
    if not question: return web.json_response({"error": "Пустой вопрос"}, status=400)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tickets (user_id, username, question) VALUES (?, ?, ?)", (user["id"], user.get("username", ""), question))
    conn.commit()
    conn.close()
    await send_admin_log(f"📩 <b>Новый тикет!</b>\n👤 @{user.get('username', '')}\n💬 {question}")
    return web.json_response({"status": "ok", "message": "Тикет создан!"})

async def api_reply_ticket(request):
    init_data = request.headers.get("X-Telegram-Init-Data")
    user = validate_init_data(init_data)
    if not user or user["id"] not in ADMIN_IDS: return web.json_response({"error": "Доступ запрещен"}, status=403)
    data = await request.json()
    ticket_id = data.get("ticket_id")
    answer = data.get("answer", "").strip()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET answer = ? WHERE id = ?", (answer, ticket_id))
    cursor.execute("SELECT user_id FROM tickets WHERE id = ?", (ticket_id,))
    target_user = cursor.fetchone()
    conn.commit()
    conn.close()
    if target_user:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": target_user[0], "text": f"💬 <b>Ответ поддержки:</b>\n{answer}", "parse_mode": "HTML"}
        async with aiohttp.ClientSession() as session: await session.post(url, json=payload)
    return web.json_response({"status": "ok", "message": "Ответ отправлен!"})

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
app.router.add_post('/api/buy_stars', api_buy_stars_invoice)
app.router.add_post('/api/topup', api_topup)
app.router.add_post('/api/case/buy', api_case_buy)
app.router.add_post('/api/case/open', api_case_open)
app.router.add_post('/api/ticket/create', api_create_ticket)
app.router.add_post('/api/ticket/reply', api_reply_ticket)
app.router.add_post('/api/admin/money', api_admin_money)
app.router.add_post('/api/admin/stock', api_admin_stock)
app.router.add_post('/api/admin/promo', api_admin_promo)
app.router.add_post('/api/promo', api_promo_activate)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=PORT)
