import telebot
import json
from telebot import types
import schedule
import time
import threading
import emoji
import sqlite3
import random
from datetime import datetime
from log import *
from sqlInteraction import *
import dataStructures
import OneCInteraction

# Load Config
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        log_sys('Config.json read to config')
except FileNotFoundError:
    log_sys("Config file not found! Please create config.json")
    exit()

szBotToken = config["botToken"]
bot = telebot.TeleBot(szBotToken)

scheduler_running = True

oneCConn = OneCInteraction.Connection() # Розкоментуйте, якщо є налаштована 1С

# ================ SESSION MANAGEMENT ================
# Замість глобальних змінних використовуємо словник сесій
user_sessions = {}


def get_user_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "currArt": "",
            "tempOrder": {
                "customerID": user_id,
                "date": "",
                "ifSended": False,
                "TTN": "",
                "orderTovarList": []
            },
            "tempUser": {"id": 0, "PIB": "", "phone": "", "address": ""},
            "currOrderCode": 0  # For admin usage logic within a session
        }
    return user_sessions[user_id]


def reset_user_order(user_id):
    if user_id in user_sessions:
        user_sessions[user_id]["tempOrder"] = {
            "customerID": user_id,
            "date": "",
            "ifSended": False,
            "TTN": "",
            "orderTovarList": []
        }
        user_sessions[user_id]["tempUser"] = {"id": 0, "PIB": "", "phone": "", "address": ""}


# ================ SUPPORT FUNCTION ================

def has_emoji(text: str) -> bool:
    return any(char in emoji.EMOJI_DATA for char in text)


def isInt(a):
    try:
        int(a)
        return True
    except ValueError:
        return False


def ifThisCorrectProduct(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)

    log(user_id, "ifThisCorrectProduct called")

    if message.text in ["/start", "🏠На головну"]:
        log(user_id, '"To main page" button pressed')
        reset_user_order(user_id)
        start(message)
        return

    found = False

    # Визначаємо артикул
    if message.caption and message.caption.startswith("🔥"):
        log(user_id, 'Forwarded message detected.')
        textList = message.caption.split("\n")
        for text in textList:
            if "Арт.: " in text:
                session["currArt"] = text.replace("Арт.: ", "").strip()
                break
    else:
        session["currArt"] = message.text.strip()

    currArt = session["currArt"]
    log(user_id, f'Current article: {currArt}')

    try:
        data_list = fetch_as_dicts('SELECT * FROM products WHERE art = ?', (currArt,))
        if not data_list:
            raise Exception("Article not found")

        data = data_list[0]
        data_prop = fetch_as_dicts('SELECT * FROM product_properties WHERE art = ?', (currArt,))
        found = True

        # Додаємо списки розмірів
        data["sizeList"] = []
        data["availabilityForProperties"] = {}
        data["priceForProperties"] = {}

        for i in data_prop:
            if i["availability"] > 0:
                data["sizeList"].append(i["property"])
                data["availabilityForProperties"][i["property"]] = i["availability"]
                data["priceForProperties"][i["property"]] = i["price"]

    except Exception as e:
        log(user_id, f'[ERROR] Can`t find article {currArt}: {e}')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✉Зв'язатися з менеджером"),
                   types.KeyboardButton("🏠На головну"))
        bot.send_message(message.chat.id, "❌ Помилка: Товар не знайдено або збій бази даних.", reply_markup=markup)
        return

    # Якщо це переслане повідомлення - одразу пропонуємо розмір
    if message.caption:
        session["tempOrder"]["orderTovarList"].append({"art": currArt, "prop": "", "count": 0})
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        row = []
        for idx, prop in enumerate(data["sizeList"]):
            row.append(types.KeyboardButton(prop))
            if (idx + 1) % 3 == 0:
                markup.row(*row)
                row = []
        if row: markup.row(*row)

        msg = bot.send_message(message.chat.id, "📏Виберіть розмір", reply_markup=markup)
        bot.register_next_step_handler(msg, handle_prop_selection)
        return

    # Якщо введено вручну - показуємо товар
    if found:
        szResultMessage = formMessageText(data, user_id)
        images = []
        try:
            if data.get("frontImage") and os.path.exists(data["frontImage"]):
                images.append(open(data["frontImage"], 'rb'))
            if data.get("backImage") and os.path.exists(data["backImage"]):
                images.append(open(data["backImage"], 'rb'))
        except Exception as e:
            log(user_id, f"Image loading error: {e}")

        if images:
            media = []
            for i, img in enumerate(images):
                caption = szResultMessage if i == 0 else None
                media.append(types.InputMediaPhoto(img, caption=caption, parse_mode='HTML'))
            bot.send_media_group(message.chat.id, media)
        else:
            bot.send_message(message.chat.id, szResultMessage, parse_mode='HTML')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✅Так"), types.KeyboardButton("❌Ні"))
        msg = bot.send_message(message.chat.id, "Чи це та форма яку ви хочете замовити?", reply_markup=markup)
        bot.register_next_step_handler(msg, handle_tovar_selection)


def handle_tovar_selection(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)
    currArt = session["currArt"]

    if message.text in ["/start", "🏠На головну"]:
        reset_user_order(user_id)
        start(message)
        return

    if message.text == "✅Так":
        try:
            # Отримуємо доступні розміри з бази
            data_prop = fetch_as_dicts(
                "SELECT property, availability as count FROM product_properties WHERE art = ?",
                (currArt,)
            )

            session["tempOrder"]["orderTovarList"].append({"art": currArt, "prop": "", "count": 0})

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            row = []
            for idx, prop in enumerate(data_prop):
                if prop['count'] > 0:
                    row.append(types.KeyboardButton(prop['property']))
                    if len(row) == 3:
                        markup.row(*row)
                        row = []
            if row: markup.row(*row)

            msg = bot.send_message(message.chat.id, "Виберіть розмір", reply_markup=markup)
            bot.register_next_step_handler(msg, handle_prop_selection)
        except Exception as e:
            log(user_id, f"Error selecting properties: {e}")
            bot.send_message(message.chat.id, "Сталася помилка при виборі розміру.")
    else:
        make_order(message)


def handle_prop_selection(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)
    currArt = session["currArt"]

    if message.text in ["/start", "🏠На головну"]:
        reset_user_order(user_id)
        start(message)
        return

    prop = message.text.strip()
    if not session["tempOrder"]["orderTovarList"]:
        bot.send_message(message.chat.id, "Помилка: кошик порожній.")
        start(message)
        return

    current_item = session["tempOrder"]["orderTovarList"][-1]  # Редагуємо останній доданий

    # Перевірка наявності в БД
    avail_data = fetch_as_dicts(
        "SELECT availability FROM product_properties WHERE art = ? AND property = ?",
        (currArt, prop)
    )

    if not avail_data:
        bot.send_message(message.chat.id, f"Розмір {prop} не знайдено.")
        return

    available_in_db = int(avail_data[0]['availability'])

    # Перевірка, чи ми вже додали цей товар раніше в це саме замовлення
    already_ordered_count = 0
    for item in session["tempOrder"]["orderTovarList"][:-1]:  # Всі крім поточного (який ще не заповнений)
        if item["art"] == currArt and item["prop"] == prop:
            already_ordered_count += item["count"]

    if (already_ordered_count + 1) > available_in_db:
        bot.send_message(message.chat.id, "На жаль, такої кількості немає в наявності.")
        # Видаляємо пустий запис
        session["tempOrder"]["orderTovarList"].pop()
        make_order(message)
        return

    # Зберігаємо вибір
    current_item["prop"] = prop
    current_item["count"] = 1

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Додати новий товар➕"), types.KeyboardButton("Продовжити➡"))

    msg = bot.send_message(message.chat.id, f"✅ Додано: {currArt} {prop}. Бажаєте додати ще?", reply_markup=markup)
    bot.register_next_step_handler(msg, handle_adding_tovar_to_order)


def handle_adding_tovar_to_order(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)

    if message.text in ["/start", "🏠На головну"]:
        reset_user_order(user_id)
        start(message)
        return

    if message.text == "Додати новий товар➕":
        make_order(message)
    else:
        # Продовжити оформлення
        # Перевіряємо чи юзер вже є в базі
        user_db = fetch_as_dicts("SELECT * FROM users WHERE id = ?", (user_id,))

        session["tempOrder"]["date"] = datetime.now().strftime("%H:%M %d.%m.%Y")

        if user_db:
            # Юзер є, одразу зберігаємо замовлення
            finalize_order(message, user_db[0])
        else:
            # Юзера немає, питаємо дані
            msg = bot.send_message(
                message.chat.id,
                "Давайте зберемо ваші дані. <b>Введіть ваше ПІБ:</b>",
                parse_mode='HTML',
                reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🏠На головну"))
            )
            bot.register_next_step_handler(msg, get_PIB)


def get_PIB(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)

    if message.text in ["🏠На головну", "/start"]:
        reset_user_order(user_id)
        start(message)
        return

    if not has_emoji(message.text):
        session["tempUser"]["id"] = user_id
        session["tempUser"]["PIB"] = message.text
        msg = bot.send_message(message.chat.id, "Введіть ваш номер телефону:", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_phone)
    else:
        msg = bot.send_message(message.chat.id, "ПІБ не може містити емодзі. Спробуйте ще раз:")
        bot.register_next_step_handler(msg, get_PIB)


def get_phone(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)

    if message.text in ["🏠На головну", "/start"]:
        reset_user_order(user_id)
        start(message)
        return

    phone = message.text.strip()
    valid = False

    if len(phone) >= 10 and len(phone) <= 13 and isInt(phone.replace("+", "")):
        session["tempUser"]["phone"] = phone
        valid = True

    if valid:
        msg = bot.send_message(message.chat.id, "Введіть адресу доставки (НП, Місто, Відділення):")
        bot.register_next_step_handler(msg, submit_data_colect)
    else:
        msg = bot.send_message(message.chat.id, "Некоректний номер. Спробуйте ще раз:")
        bot.register_next_step_handler(msg, get_phone)


def submit_data_colect(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)

    if message.text == "🏠На головну":
        reset_user_order(user_id)
        start(message)
        return

    session["tempUser"]["address"] = message.text

    # Зберігаємо юзера в БД
    SQLmake(
        'INSERT OR REPLACE INTO users (id, PIB, phone, address) VALUES (?, ?, ?, ?)',
        (session["tempUser"]["id"], session["tempUser"]["PIB"], session["tempUser"]["phone"],
         session["tempUser"]["address"])
    )

    finalize_order(message, session["tempUser"])


def finalize_order(message, user_data):
    user_id = message.from_user.id
    session = get_user_session(user_id)
    order_data = session["tempOrder"]

    try:
        # Створюємо замовлення
        order_code = SQLmake(
            'INSERT INTO orders (customerID, date, ifSended, TTN, status) VALUES (?, ?, ?, ?, ?)',
            (user_id, order_data["date"], 0, "", "Нове")
        )

        # Записуємо товари і списуємо наявність
        for item in order_data["orderTovarList"]:
            SQLmake(
                'INSERT INTO order_items (code, art, prop, count) VALUES (?, ?, ?, ?)',
                (order_code, item["art"], item["prop"], item["count"])
            )
            SQLmake(
                "UPDATE product_properties SET availability = availability - ? WHERE art = ? AND property = ?",
                (item["count"], item["art"], item["prop"])
            )

        # Прив'язка ID замовлення до юзера (для таблиці orderCodeToUserId, якщо вона використовується)
        # Хоча customerID в orders вже є, але згідно вашої схеми:
        SQLmake('INSERT INTO orderCodeToUserId (order_code, user_id) VALUES (?, ?)', (order_code, user_id))

        # Відправка юзеру
        bot.send_message(message.chat.id, f"✅ Замовлення №{order_code} успішно створено! Менеджер зв'яжеться з вами.")

        # Повідомлення адміну
        if config["adminIDs"]:
            admin_msg = f"🆕 <b>Нове замовлення №{order_code}</b>\n" \
                        f"👤 {user_data.get('PIB')} ({user_data.get('phone')})\n" \
                        f"🏠 {user_data.get('address')}\n\n"
            for item in order_data["orderTovarList"]:
                admin_msg += f"🔸 {item['art']} ({item['prop']}) x{item['count']}\n"

            try:
                bot.send_message(config["adminIDs"][0], admin_msg, parse_mode='HTML')
            except Exception as e:
                log_sys(f"Failed to send admin notification: {e}")

        reset_user_order(user_id)
        start(message)

    except Exception as e:
        log(user_id, f"Order save error: {e}")
        bot.send_message(message.chat.id, "Сталася помилка при збереженні замовлення. Спробуйте пізніше.")


# ================ USER MESSAGE HANDLERS ================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🛍️Зробити замовлення"))
    markup.add(types.KeyboardButton("🛒Мої замовлення"))
    markup.add(types.KeyboardButton("✉Зв'язатися з менеджером"))
    bot.send_message(message.chat.id, "👋Вітаємо! Оберіть опцію:", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "🛒Мої замовлення")
def my_orders(message):
    user_id = message.from_user.id

    # Створюємо об'єкт клієнта (як того очікує ваш метод _get_orders_by_customer)
    # Потрібно, щоб у структурі Customer було поле s_customerTelegramId
    customer = dataStructures.Customer(s_customerTelegramIdIn=user_id)

    # Отримуємо замовлення безпосередньо з 1С
    orders = one_c.getOrders(cus_orderCustomer=customer)

    if not orders:
        bot.send_message(message.chat.id, "У вас ще немає замовлень в базі 1С.")
        return

    text = "<b>🛒 Ваші замовлення з 1С:</b>\n\n"
    # Показуємо останні 5 (якщо метод повертає список)
    for order in orders[-5:]:
        text += f"📦 <b>Замовлення №{order.n_orderCode}</b> ({order.s_date})\n"
        text += f"Статус: <b>{order.s_status}</b>\n"
        if order.s_TTN:
            text += f"🚚 ТТН: <code>{order.s_TTN}</code>\n"

        text += "Товари:\n"
        for item in order.noml_orderItemList:
            # item — це об'єкт orderItem з вашого модуля dataStructures
            text += f"-- {item.article} ({item.s_productProperties}) x{item.count}\n"
        text += "\n"

    bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(func=lambda message: message.text == "🛍️Зробити замовлення")
def make_order(message):
    try:
        # Показуємо товари, які активні (activeProductPool або products)
        # Тут приклад з activeProductPool, як у вашому коді
        products = fetch_as_dicts("SELECT product_article FROM activeProductPool WHERE show = 1")

        # Якщо пул пустий, беремо просто з products
        if not products:
            products = fetch_as_dicts("SELECT art as product_article FROM products LIMIT 30")

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        row = []
        for idx, item in enumerate(products):
            row.append(types.KeyboardButton(item["product_article"]))
            if (idx + 1) % 3 == 0:
                markup.row(*row)
                row = []
        if row: markup.row(*row)
        markup.add(types.KeyboardButton("🏠На головну"))

        bot.send_message(
            message.chat.id,
            "Оберіть товар зі списку або надішліть код/перешліть пост з каналу:",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, ifThisCorrectProduct)
    except Exception as e:
        log_sys(f"make_order error: {e}")


@bot.message_handler(func=lambda message: message.text == "✉Зв'язатися з менеджером")
def contact_to_manager(message):
    if not config["adminIDs"]:
        bot.send_message(message.chat.id, "Налаштування менеджера відсутні.")
        return

    username = message.from_user.username
    msg = f"User @{username} (ID: {message.from_user.id}) ask for help."
    bot.send_message(config["adminIDs"][0], msg)
    bot.send_message(message.chat.id, "Менеджер отримав ваш запит і напише вам.")


# ================ ADMIN COMMANDS ================

@bot.message_handler(commands=['stop_sending'])
def stop_sending(message):
    global scheduler_running

    # Перевірка, чи користувач є адміном
    if message.from_user.id in config["adminIDs"]:
        scheduler_running = False
        log_sys(f'Scheduler stopped by admin {message.from_user.id}')
        bot.send_message(message.chat.id, "⛔ <b>Розсилка зупинена.</b>", parse_mode='HTML')
    else:
        # Можна нічого не відповідати або написати, що немає прав
        pass


@bot.message_handler(commands=['start_sending'])
def start_sending(message):
    global scheduler_running

    # Перевірка, чи користувач є адміном
    if message.from_user.id in config["adminIDs"]:
        scheduler_running = True
        log_sys(f'Scheduler started by admin {message.from_user.id}')
        bot.send_message(message.chat.id, "🏃‍♀️ <b>Розсилка відновлена.</b>", parse_mode='HTML')

@bot.message_handler(commands=['orderlist'])
def send_orderlist1(message):
    if message.from_user.id not in config["adminIDs"]: return

    # Отримуємо всі активні замовлення
    orders = fetch_as_dicts("SELECT * FROM orders ORDER BY code DESC LIMIT 20")

    if not orders:
        bot.send_message(message.chat.id, "Замовлень немає.")
        return

    text = "Список останніх замовлень:\n"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []

    for idx, order in enumerate(orders):
        status = "✅" if order['ifSended'] else "❌"
        text += f"{order['code']}. ID: {order['customerID']} - {status}\n"
        row.append(types.KeyboardButton(str(order['code'])))
        if (idx + 1) % 4 == 0:
            markup.row(*row)
            row = []
    if row: markup.row(*row)
    markup.add(types.KeyboardButton("🏠На головну"))

    msg = bot.send_message(message.chat.id, text, reply_markup=markup)
    bot.register_next_step_handler(msg, send_orderlist2)


def send_orderlist2(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)

    if message.text == "🏠На головну":
        start(message)
        return

    if not isInt(message.text):
        bot.send_message(message.chat.id, "Це не номер.")
        return

    order_code = int(message.text)
    session["currOrderCode"] = order_code

    order = fetch_as_dicts("SELECT * FROM orders WHERE code = ?", (order_code,))
    if not order:
        bot.send_message(message.chat.id, "Замовлення не знайдено.")
        return
    order = order[0]

    user = fetch_as_dicts("SELECT * FROM users WHERE id = ?", (order['customerID'],))
    user_info = user[0] if user else {'PIB': 'Unknown', 'phone': 'Unknown', 'address': 'Unknown'}

    items = fetch_as_dicts("SELECT * FROM order_items WHERE code = ?", (order_code,))

    info = f"Замовлення #{order_code}\nКлієнт: {user_info['PIB']}\nТел: {user_info['phone']}\nАдреса: {user_info['address']}\nТТН: {order['TTN']}\n\nТовари:\n"
    for item in items:
        info += f"- {item['art']} {item['prop']} x{item['count']}\n"

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Додати ТТН"), types.KeyboardButton("🏠На головну"))

    msg = bot.send_message(message.chat.id, info, reply_markup=markup)
    bot.register_next_step_handler(msg, send_orderlist3)


def send_orderlist3(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)

    if message.text == "Додати ТТН":
        msg = bot.send_message(message.chat.id, "Введіть номер ТТН:")
        bot.register_next_step_handler(msg, add_TTN)
    else:
        start(message)


def add_TTN(message):
    user_id = message.from_user.id
    session = get_user_session(user_id)
    ttn = message.text

    SQLmake("UPDATE orders SET TTN = ?, ifSended = 1, status = 'Відправлено' WHERE code = ?",
            (ttn, session["currOrderCode"]))

    # Спробувати повідомити клієнта
    order = fetch_as_dicts("SELECT customerID FROM orders WHERE code = ?", (session["currOrderCode"],))[0]
    try:
        bot.send_message(order['customerID'], f"Ваше замовлення #{session['currOrderCode']} відправлено!\nТТН: {ttn}")
    except:
        pass

    bot.send_message(message.chat.id, "ТТН збережено.")
    start(message)


# ================ UTILS ================
def formMessageText(data, user_id):
    # (Функція формування тексту товару з вашого коду, трохи спрощена для надійності)
    name = data.get('name', 'Товар')
    art = data.get('art', '---')
    price_str = "Уточнюйте"

    if data.get("priceForProperties"):
        vals = list(data["priceForProperties"].values())
        if vals: price_str = f"{min(vals)} грн"

    txt = f"🔥 <b>{name}</b>\nАрт: {art}\n\n"
    txt += f"Розміри: {', '.join(data.get('sizeList', []))}\n"
    txt += f"💰 Ціна: {price_str}"
    return txt


def sendMessage():
    global config
    import os

    try:
        log_sys("Scheduler: Starting sendMessage routine (Full 1C integration)...")

        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        start_index = config.get("LastSendedIndex", 0)

        # 1. Беремо ТІЛЬКИ артикули з локальної бази (картинки тепер з 1С)
        query = "SELECT product_article FROM activeProductPool WHERE show = 1"
        active_pool = fetch_as_dicts(query)
        total_products = len(active_pool)

        if total_products == 0:
            log_sys("Scheduler: activeProductPool is empty.")
            return

        if start_index >= total_products:
            start_index = 0
            log_sys("Scheduler: Index reset to 0")

        current_item = active_pool[start_index]
        current_art = current_item["product_article"]

        log_sys(f"Scheduler: Fetching data for {current_art} from 1C...")

        # 2. Отримуємо ВСІ дані (в т.ч. шляхи до збережених темп-картинок) з 1С
        try:
            if oneCConn.v8 is None:
                oneCConn.initiateConnection()

            product_data = oneCConn.getProductData(current_art)
        except Exception as e:
            log_sys(f"[ERROR] 1C Connection failed: {e}")
            return

        # Перевірка чи товар знайдений і чи є розміри
        if not product_data or not product_data["sizeList"]:
            log_sys(f"Scheduler: Product {current_art} not found/empty in 1C. Skipping.")
            config["LastSendedIndex"] = start_index + 1
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return

        # 3. Формуємо текст
        szResultMessage = formMessageText(product_data, 'system')
        if szResultMessage == "NULL":
            log_sys(f"Scheduler: Failed to form text. Skipping.")
            return

        # 4. Підготовка зображень (шляхи тепер ведуть у папку temp_images)
        images = []
        media = []

        # Список шляхів для подальшого видалення
        paths_to_cleanup = []
        if product_data.get("frontImage"): paths_to_cleanup.append(product_data["frontImage"])
        if product_data.get("backImage"): paths_to_cleanup.append(product_data["backImage"])

        try:
            for path in paths_to_cleanup:
                if os.path.exists(path):
                    images.append(open(path, 'rb'))
        except Exception as e:
            log_sys(f"Scheduler: Image open error: {e}")

        # 5. Відправка
        channel_id = config.get("channelID")

        if images:
            for i, img in enumerate(images):
                caption = szResultMessage if i == 0 else None
                media.append(types.InputMediaPhoto(img, caption=caption, parse_mode='HTML'))
            bot.send_media_group(channel_id, media)
        else:
            bot.send_message(channel_id, szResultMessage, parse_mode='HTML')

        log_sys(f"Scheduler: Sent {current_art}.")

        # 6. Закриття та видалення файлів
        for img in images:
            img.close()

        # Видаляємо тимчасові файли з диска, щоб не забивати пам'ять
        for path in paths_to_cleanup:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    log_sys(f"Deleted temp file: {path}")
            except Exception as e:
                log_sys(f"Error deleting temp file {path}: {e}")

        # 7. Оновлення індексу
        config["LastSendedIndex"] = start_index + 1
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    except Exception as e:
        log_sys(f"[ERROR] Scheduler routine failed: {e}")


def run_scheduler():
    global scheduler_running
    log_sys("Scheduler thread started.")
    while True:
        # Виконуємо розсилку тільки якщо прапорець True
        if scheduler_running:
            schedule.run_pending()

        # Затримка (береться з конфігу або за замовчуванням 60 секунд)
        time.sleep(config.get('timeToSleep', 60))
# Run
if __name__ == '__main__':
    log_sys("Bot started")
    try:
        bot.infinity_polling()
    except Exception as e:
        log_sys(f"CRITICAL ERROR: {e}")