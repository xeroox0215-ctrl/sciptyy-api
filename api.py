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
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, discount INTEGER DEFAULT 0, balance REAL DEFAULT 0, last_roll INTEGER DEFAULT 0, cases INTEGER DEFAULT 0, vip_cases INTEGER DEFAULT 0, gift_claimed INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item_name TEXT, price REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS stock (country TEXT PRIMARY KEY, amount INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS promos (code TEXT PRIMARY KEY, discount INTEGER, limit_count INTEGER, used_count INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS user_promos (user_id INTEGER, code TEXT, PRIMARY KEY (user_id, code))")
    cursor.execute("CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, question TEXT, answer TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, expire_time REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, text TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
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
    except Exception:
        return None

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT discount, balance, last_roll, cases, vip_cases, gift_claimed FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row: return {"discount": row[0], "balance": float(row[1]), "last_roll": row[2], "cases": row[3], "vip_cases": row[4], "gift_claimed": row[5]}
    return {"discount": 0, "balance": 0.0, "last_roll": 0, "cases": 0, "vip_cases": 0, "gift_claimed": 0}

async def send_admin_log(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": 1494459013, "text": text, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session: 
            await session.post(url, json=payload)
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
    
    if profile["balance"] >= 500 and profile["gift_claimed"] == 0:
        cursor.execute("UPDATE users SET cases = cases + 1, gift_claimed = 1 WHERE user_id = ?", (user["id"],))
        conn.commit()
        profile["cases"] += 1
        profile["gift_claimed"] = 1
        
    cursor.execute("SELECT item_name, price, date FROM purchases WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user["id"],))
    purchases = [{"name": r[0], "price": r[1], "date": r[2]} for r in cursor.fetchall()]
    
    cursor.execute("SELECT item_name FROM purchases WHERE user_id = ? AND item_name NOT LIKE '%Кейс%' AND item_name NOT LIKE '%Промокод%'", (user["id"],))
    my_accounts = [r[0] for r in cursor.fetchall()]
    
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
    return web.json_response({"status": "ok", "profile": profile, "purchases": purchases, "my_accounts": my_accounts, "shop": shop_items, "is_admin": user["id"] in ADMIN_IDS, "tickets": tickets})

# Остальные функции оставляем как были (events, roll, buy, topup, case, promo, ticket, admin, chat)
# ...
# В самом низу добавь эти роуты (если их нет):
# app.router.add_post('/api/admin/clear_events', api_clear_events)
# app.router.add_post('/api/chat', api_chat)
# app.router.add_get('/api/chat', api_chat)
const tg = window.Telegram?.WebApp;
if (tg) tg.expand();
const API_URL = "https://sciptyy-api.onrender.com";

let userProfile = { balance: 0, cases: 0, vip_cases: 0, discount: 0 };
let accountsData = [];
let myAccounts = []; // Список купленных аккаунтов для апгрейда
let selectedCountry = null;
let isAdmin = false;

// Загрузка данных
async function loadData() {
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
        const u = tg.initDataUnsafe.user;
        document.getElementById('user-name').innerText = u.first_name;
        document.getElementById('user-id').innerText = `ID: ${u.id}`;
        const avatar = document.getElementById('user-avatar');
        if (u.photo_url) { avatar.style.backgroundImage = `url('${u.photo_url}')`; avatar.innerText = ''; }
        else { avatar.innerText = u.first_name.charAt(0).toUpperCase(); }
    }

    try {
        const res = await fetch(`${API_URL}/api/profile`, { headers: { "X-Telegram-Init-Data": tg.initData } });
        const data = await res.json();
        if (data.status === "ok") {
            userProfile = data.profile;
            accountsData = data.shop;
            myAccounts = data.my_accounts || []; // Сохраняем аккаунты
            isAdmin = data.is_admin;
            
            if (isAdmin) {
                document.getElementById('admin-btn').style.display = 'block';
                document.getElementById('admin-tickets-btn').style.display = 'block';
            }
            if (userProfile.cases > 0) document.getElementById('open-normal-case').style.display = 'block';
            if (userProfile.vip_cases > 0) document.getElementById('open-vip-case').style.display = 'block';
            
            document.getElementById('profile-balance').innerText = `${userProfile.balance.toFixed(2)} ₽`;
            
            const pDiv = document.getElementById('profile-purchases');
            pDiv.innerHTML = data.purchases.length > 0 ? data.purchases.map(p => `
                <div class="purchase-item">
                    <div style="font-weight: bold; color: #00d2ff;">${p.name}</div>
                    <div style="color: #888;">${p.price} ₽ • ${p.date.split(' ')[0]}</div>
                </div>`).join('') : '<div style="color:#888;">Покупок нет</div>';
            renderTickets(data.tickets);
        }
    } catch(e) { console.log(e); }
}

// События (бегущая строка)
async function loadEvents() {
    try {
        const res = await fetch(`${API_URL}/api/events`);
        const data = await res.json();
        const track = document.getElementById('ticker-track');
        if (data.status === 'ok' && data.events.length > 0) track.innerText = data.events.join('  •  ') + '  •  ';
        else track.innerText = "Добро пожаловать в Sciptyy Store!  •  ";
    } catch(e) {}
}
setInterval(loadEvents, 10000);
loadEvents();

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    if(id === 'screen-profile' || id === 'screen-main' || id === 'screen-admin-tickets') loadData();
    if(id === 'screen-chat') loadChat();
}

// Каталог
function openCatalog() {
    const grid = document.getElementById('catalog-grid');
    grid.innerHTML = '';
    accountsData.forEach(item => {
        const stockColor = item.stock > 0 ? '#00d2ff' : '#ff4444';
        const stockText = item.stock > 0 ? `В наличии: ${item.stock}` : 'Нет в наличии';
        grid.innerHTML += `
            <div class="product-card">
                <div class="product-name">${item.name}</div>
                <div class="product-price">${item.price} ₽</div>
                <div style="color:${stockColor}; font-size:11px; margin-bottom:5px;">${stockText}</div>
                <button class="buy-btn" ${item.stock <= 0 ? 'disabled' : ''} onclick="openModal('${item.code}', '${item.name}', ${item.price}, ${item.stock})">Купить</button>
            </div>`;
    });
    showScreen('screen-catalog');
}

function openModal(code, name, price, stock) {
    if(stock <= 0) return;
    selectedCountry = code;
    document.getElementById('modal-title').innerText = name;
    document.getElementById('modal-price').innerText = `Цена: ${price} ₽`;
    document.getElementById('modal-buy').style.display = 'flex';
}
function closeModal() { document.getElementById('modal-buy').style.display = 'none'; }

async function buyItem(method) {
    closeModal();
    if (method === 'stars') {
        // Логика звезд
        return;
    }
    tg.showAlert("Списываем средства...");
    const res = await fetch(`${API_URL}/api/buy`, {
        method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" },
        body: JSON.stringify({ country: selectedCountry })
    });
    const data = await res.json();
    tg.showAlert(data.status === 'ok' ? "✅ Деньги списаны!" : `❌ ${data.error}`);
    loadData(); loadEvents();
}

// Рулетка
async function spinWheel() {
    const res = await fetch(`${API_URL}/api/roll`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData } });
    const data = await res.json();
    if(data.status === 'ok') {
        // Анимация и показ результата...
        document.getElementById('roll-result').innerText = `🎉 Вы выиграли: ${data.prize}`;
        loadData();
    } else tg.showAlert(data.error);
}

// Кейсы
async function buyCase(type) {
    tg.showConfirm(`Купить кейс?`, async (confirmed) => {
        if (!confirmed) return;
        const res = await fetch(`${API_URL}/api/case/buy`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ type }) });
        const data = await res.json();
        tg.showAlert(data.message || data.error);
        loadData();
    });
}

async function openCase(type) {
    const animDiv = document.getElementById('case-animation');
    const track = document.getElementById('roulette-track');
    const winContainer = document.getElementById('win-card-container');
    const winContent = document.getElementById('win-card-content');
    
    animDiv.style.display = 'block';
    winContainer.style.display = 'none';
    track.style.transition = 'none';
    track.style.transform = 'translateX(0)';
    track.innerHTML = '';
    
    const res = await fetch(`${API_URL}/api/case/open`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ type }) });
    const data = await res.json();
    
    if (data.status === 'ok') {
        const winIndex = 25; 
        let itemsHTML = '';
        for (let i = 0; i < 30; i++) {
            const prize = data.prize;
            if (i === winIndex) {
                if (prize.type === 'money') itemsHTML += `<div class="roulette-item money">💰<br>${prize.value}</div>`;
                else if (prize.type === 'promo') itemsHTML += `<div class="roulette-item promo">🎁<br>Скидка</div>`;
                else itemsHTML += `<div class="roulette-item account">🌍<br>${prize.value}</div>`;
            } else {
                const rnd = Math.random();
                if (rnd < 0.4) itemsHTML += `<div class="roulette-item money">💰<br>Рубли</div>`;
                else if (rnd < 0.7) itemsHTML += `<div class="roulette-item promo">🎁<br>Промо</div>`;
                else itemsHTML += `<div class="roulette-item account">🌍<br>Аккаунт</div>`;
            }
        }
        track.innerHTML = itemsHTML;
        
        setTimeout(() => {
            track.style.transition = 'transform 5s cubic-bezier(0.1, 0.8, 0.1, 1)';
            const finalX = -((winIndex * 100) - (window.innerWidth / 2) + 45);
            track.style.transform = `translateX(${finalX}px)`;
            
            setTimeout(() => {
                let prizeStr = "";
                if (data.prize.type === 'money') prizeStr = `<div style="font-size:18px; color:#00d2ff; margin-top:10px;">Вы выиграли <b>${data.prize.value}</b>!</div>`;
                if (data.prize.type === 'promo') prizeStr = `<div style="font-size:14px; margin-top:10px;">Промокод:<br><b style="font-size:20px; color:#ffd700;">${data.prize.code}</b></div>`;
                if (data.prize.type === 'account') prizeStr = `<div style="font-size:16px; margin-top:10px;">Аккаунт <b>${data.prize.value}</b><br><span style="font-size:11px; color:#aaa;">Напишите в поддержку!</span></div>`;
                
                winContent.innerHTML = `<div style="font-size:50px; text-align:center;">🎁</div><div style="font-size:18px; font-weight:900; color:#ffd700; text-align:center; margin-top:10px;">ПОЗДРАВЛЯЕМ!</div>`;
                document.getElementById('case-prize-text').innerHTML = prizeStr;
                winContainer.style.display = 'flex';
                tg.showAlert("Ваш приз получен!");
                loadData(); loadEvents();
            }, 5200); 
        }, 100);
    } else {
        tg.showAlert(data.error); animDiv.style.display = 'none';
    }
}

// ЧАТ
async function loadChat() {
    const res = await fetch(`${API_URL}/api/chat`, { headers: { "X-Telegram-Init-Data": tg.initData } });
    const data = await res.json();
    if(data.status === 'ok') {
        const chatBox = document.getElementById('chat-messages');
        chatBox.innerHTML = data.messages.map(m => `
            <div class="chat-msg ${m.user_id === tg.initDataUnsafe.user.id ? 'mine' : 'other'}">
                <div class="chat-author">${m.username}</div>
                <div>${m.text}</div>
            </div>
        `).join('');
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}
setInterval(() => { if(document.getElementById('screen-chat').classList.contains('active')) loadChat(); }, 5000);

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if(!text) return;
    input.value = "";
    await fetch(`${API_URL}/api/chat`, {
        method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" },
        body: JSON.stringify({ text })
    });
    loadChat();
}

// АПГРЕЙД
let upgradeSlot1 = null; let upgradeSlot2 = null;

function selectSlot(slotNum) {
    if(myAccounts.length === 0) return tg.showAlert("У вас нет аккаунтов для апгрейда.");
    
    let msg = "Выберите аккаунт:\n";
    myAccounts.forEach((acc, i) => msg += `${i + 1}. ${acc}\n`);
    const choice = prompt(msg + "\nВведите номер:");
    if(!choice) return;
    
    const acc = myAccounts[parseInt(choice) - 1];
    if(!acc) return tg.showAlert("Неверный номер.");
    
    tg.showConfirm(`Поставить "${acc}" в слот ${slotNum}?`, (confirmed) => {
        if(!confirmed) return;
        if(slotNum === 1) { upgradeSlot1 = acc; document.getElementById('slot-1').innerHTML = `<div style="font-size:12px; color:#ffd700;">${acc}</div>`; document.getElementById('slot-1').classList.add('filled'); }
        else { upgradeSlot2 = acc; document.getElementById('slot-2').innerHTML = `<div style="font-size:12px; color:#ffd700;">${acc}</div>`; document.getElementById('slot-2').classList.add('filled'); }
        checkUpgrade();
    });
}

function checkUpgrade() {
    const btn = document.getElementById('upgrade-btn');
    if(upgradeSlot1 && upgradeSlot2 && upgradeSlot1 === upgradeSlot2) {
        btn.disabled = false; btn.style.opacity = '1'; btn.style.background = 'linear-gradient(90deg, #00d2ff, #0052ff)';
    } else {
        btn.disabled = true; btn.style.opacity = '0.5'; btn.style.background = '#333';
    }
}

function startUpgrade() {
    tg.showAlert("Функция апгрейда в разработке (скоро будет)!");
}

// Админка и тикеты
async function createTicket() {
    const text = document.getElementById('ticket-input').value.trim();
    if(!text) return tg.showAlert("Напишите вопрос!");
    const res = await fetch(`${API_URL}/api/ticket/create`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ question: text }) });
    const data = await res.json();
    tg.showAlert(data.message || data.error);
    if(data.status === 'ok') { document.getElementById('ticket-input').value = ""; loadData(); }
}

function renderTickets(tickets) {
    const adminList = document.getElementById('admin-ticket-list');
    const list = document.getElementById('ticket-list');
    if (isAdmin) {
        adminList.innerHTML = tickets.length > 0 ? tickets.map(t => `<div class="purchase-item"><div>@${t.username}: ${t.question}</div><button onclick="replyTicket(${t.id})">Ответить</button></div>`).join('') : 'Нет тикетов.';
    } else {
        list.innerHTML = tickets.map(t => `<div class="purchase-item"><div>${t.question}</div><div>${t.answer ? 'Ответ: '+t.answer : 'Ожидает...'}</div></div>`).join('');
    }
}

async function replyTicket(id) {
    const answer = prompt("Ответ:");
    if(!answer) return;
    const res = await fetch(`${API_URL}/api/ticket/reply`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ ticket_id: id, answer }) });
    const data = await res.json(); tg.showAlert(data.message || data.error); loadData();
}

async function adminAction(action) {
    const resDiv = document.getElementById('admin-result');
    resDiv.innerText = "Загрузка...";
    if (action === 'money') {
        const amount = prompt("Сумма:"); if(!amount) return;
        const res = await fetch(`${API_URL}/api/admin/money`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ amount: parseFloat(amount) }) });
        const data = await res.json(); resDiv.innerText = data.message || data.error; loadData();
    }
    if (action === 'promo') {
        const code = prompt("Код:"); const disc = prompt("Скидка:"); const limit = prompt("Лимит:");
        const res = await fetch(`${API_URL}/api/admin/promo`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ code, discount: parseInt(disc), limit: parseInt(limit) }) });
        const data = await res.json(); resDiv.innerText = data.message || data.error;
    }
    if (action === 'stock') {
        const country = prompt("Код страны:"); const amount = prompt("Кол-во:");
        const res = await fetch(`${API_URL}/api/admin/stock`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ country, amount: parseInt(amount) }) });
        const data = await res.json(); resDiv.innerText = data.message || data.error; loadData();
    }
    if (action === 'broadcast') {
        const text = prompt("Текст:"); if(!text) return;
        const res = await fetch(`${API_URL}/api/admin/broadcast`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ text, minutes: 60 }) });
        const data = await res.json(); resDiv.innerText = data.message || data.error; loadEvents();
    }
}

async function clearEvents() {
    const resDiv = document.getElementById('admin-result');
    resDiv.innerText = "Очистка...";
    const res = await fetch(`${API_URL}/api/admin/clear_events`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData } });
    const data = await res.json(); resDiv.innerText = data.message || data.error; loadEvents();
}

// Инфо и пополнение
function openInfo(type) {
    if(type === 'promo') {
        document.getElementById('info-title').innerText = "🎁 Промокод";
        document.getElementById('info-content').innerHTML = `<input type="text" id="promo-input" placeholder="Код" style="width:100%; padding:15px; margin-bottom:10px; background:rgba(255,255,255,0.1); border:none; color:white; border-radius:10px;"><button class="info-btn" onclick="activatePromo()">Активировать</button>`;
        showScreen('screen-info'); return;
    }
    // ... другие инфо ...
}

async function activatePromo() {
    const code = document.getElementById('promo-input').value.trim().toUpperCase();
    const res = await fetch(`${API_URL}/api/promo`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
    const data = await res.json(); tg.showAlert(data.status === 'ok' ? data.message : data.error); if(data.status === 'ok') loadData();
}

function showTopupModal() { document.getElementById('modal-topup').style.display = 'flex'; }
function closeTopup() { document.getElementById('modal-topup').style.display = 'none'; }
async function topupBalance() {
    const amount = parseFloat(document.getElementById('topup-amount').value);
    if(!amount || amount < 50) return tg.showAlert("Минимум 50 ₽");
    closeTopup(); tg.showAlert("Создаем счет...");
    const res = await fetch(`${API_URL}/api/topup`, { method: 'POST', headers: { "X-Telegram-Init-Data": tg.initData, "Content-Type": "application/json" }, body: JSON.stringify({ amount }) });
    const data = await res.json();
    if(data.url) tg.openLink(data.url); else tg.showAlert("Ошибка: " + data.error);
}

// Инициализация
if (tg) {
    tg.ready();
    loadData();
    loadEvents();
    setInterval(loadData, 15000);
}
