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

import dataStructures
from dataStructures import Nomenclature
from log import *
from sqlInteraction import *
import OneCInteraction

with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    log_sys('Config.json read to config')

szBotToken = config["botToken"]
bot = telebot.TeleBot(szBotToken)

scheduler_running = True

currArt = ""
sl_orderStatusList = ["Прийнято", "Відправлено", "Виконано", "Скасовано"]
activeProductPool = []
lastSendedArticle = ""

oneCConn = OneCInteraction.Connection()

# ================ SUPPORT FUNCTION ================

def has_emoji(text: str) -> bool:
    return any(char in emoji.EMOJI_DATA for char in text)

def isInt(a):
    try:
        int(a)
        return True
    except ValueError:
        return False



# ================ USER MESSAGE HANDLERS ================
@bot.message_handler(commands=['start'])
def start(message):
    try:
        log(message.from_user.id, '"/start" command received')
        mainMenuButtonsCreate(message, "👋Вітаємо! Оберіть опцію:")
    except Exception as e:
        log(message.from_user.id, f"[ERROR] start(): {e}")


@bot.message_handler(func=lambda message: message.text == "🛒Мої замовлення")
def my_orders(message):
    try:
        log(message.from_user.id, '"My orders" button pressed')
        orderCodeList = fetch_as_dicts("SELECT * FROM orderIdToUserId WHERE user_id = ?", (message.from_user.id,))
        log(message.from_user.id, f"{len(orderCodeList)} ordersCode fetched from database")

        if not orderCodeList:
            log(message.from_user.id, f"User has no orders")
            bot.send_message(message.chat.id, "Наразі у вас відсутні замовлення", parse_mode='HTML')
            return

        s_ResultMessage = f'\t<b>🧾 МОЇ ЗАМОВЛЕННЯ</b>\n'
        for orderCode in orderCodeList.keys():
            log(message.from_user.id, 'Trying to get order from 1C.')
            cor_currOrder = oneCConn.getOrderByCode(orderCode)

            if not cor_currOrder:
                log(message.from_user.id, f"Cannot find order with code {orderCode}.")
                continue

            log(message.from_user.id, f"Processing order #{orderCode}")
            s_ResultMessage += f'''
<b>📦 Замовлення №{cor_currOrder.n_orderCode}</b>
    📅 <b>Дата:</b> {cor_currOrder.s_date}
    📩 <b>Відправлено:</b> {cor_currOrder.s_status}
        🔢 <b>ТТН:</b> {cor_currOrder.s_TTN}
    🛍️ <b>Список покупок:</b>\n'''
            coritl_orderItemsList = cor_currOrder.coritl_orderItemsList
            log(message.from_user.id, f"{len(coritl_orderItemsList)} items found for order #{cor_currOrder.n_orderCode}")
            for orderItem in coritl_orderItemsList:
                s_ResultMessage += f'\t\t\t\t\t\t •🛒 <b>{orderItem.s_productArticle}</b>: {orderItem.s_productProperties} — {orderItem.n_productCount} шт.\n'
        bot.send_message(message.chat.id, s_ResultMessage, parse_mode='HTML')
        log(message.from_user.id, "Order list sent to user")

    except Exception as e:
        log(message.from_user.id, f"[ERROR] my_orders(): {e}")
        bot.send_message(message.chat.id, "⚠ Сталася помилка при спробі отримати список замовлень.", parse_mode='HTML')


@bot.message_handler(func=lambda message: message.text == "🛍️Зробити замовлення")
def make_order1(message):
    log(message.from_user.id, "make_order1 called")
    try:
        log(message.from_user.id, '"Make order" button pressed')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("<- Назад")

        newOrder = dataStructures.Order()
        s_msgText = (
            "🤔 <b>Перешліть</b> повідомлення з нашого каналу з товаром який ви хочете купити 📨\n\n"
            "📲 Перешліть повідомлення прямо сюди — і я все оброблю автоматично!"
        )
        msg = bot.send_message(message.chat.id, s_msgText, reply_markup=markup, parse_mode='HTML')
        log(message.from_user.id, "Product selection message sent")

        bot.register_next_step_handler(msg, make_order2,newOrder)

    except Exception as e:
        log(message.from_user.id, f"[ERROR] make_order(): {e}")
        bot.send_message(message.chat.id, "⚠ Сталася помилка при початку оформлення замовлення")

def make_order2(message, newOrder):
    log(message.from_user.id, "make_order2 called")
    if message.text in ["/start", "🏠️️На головну"]:
        log(message.from_user.id, '"To main page" button pressed or "/start" command used')
        back_to_main(message)
        return

    articleMode = False


    if message.caption:
        log(message.from_user.id, 'Forwarded message detected. Getting product article.')
        textList = message.caption.split("\n")
        for text in textList:
            if "Арт.: " in text:
                currArt = text.replace("Арт.: ", "").strip()
                log(message.from_user.id, f'Current article: {currArt}')
                log(message.from_user.id, 'Trying getting data from database')
    else:
        log(message.from_user.id, 'Forwarded message not detected. Working in default mode')
        articleMode = True
        log(message.from_user.id, 'ArticleMode bool switched to True.')
        currArt = message.text.strip()

    currProduct = None

    try:
        log(message.from_user.id, 'Trying to get nomenclature by article from 1C.')
        currProduct = oneCConn.getNomenclature(s_articleIn=currArt)
        log(message.from_user.id, 'Nomenclature was successfully got')
    except Exception as e:
        log(message.from_user.id, f'[ERROR] Can`t find Nomenclature( Article : {currArt} ) in 1c: {e}')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✉Зв'язатися з менеджером"),
                   types.KeyboardButton("🏠На головну"))
        bot.send_message(message.chat.id, "❌ Помилка: отримання даних про цей товар на даний момент неможливе.",
                         reply_markup=markup)
        return


    if currProduct:
        currProductProp = currProduct.sl_productProperties
        currProductCount = currProduct.nl_productCount
        log(message.from_user.id, 'Creating newOrderItem.')
        newOrderItem = dataStructures.orderItem(s_productArticleIn=currProduct.s_productArticle)
        log(message.from_user.id, 'Trying to add newOrderItem to orderItemList.')
        newOrder.coritl_orderItemsList.append(newOrderItem)
        if articleMode:
            log(message.from_user.id, 'Switching to articleMode.')
            s_ResultMessage = formMessageText(currProduct, message.from_user.id)
            imgList = []
            log(message.from_user.id, 'Trying to get nomenclature images from 1c.')
            try:
                imgList = oneCConn.get_images(currProduct)
            except Exception as e:
                log(message.from_user.id, f'[ERROR] Images getting failure: {e}')

            if imgList:
                media = []
                for i, img in enumerate(imgList):
                    log(message.from_user.id, 'Trying to add images to Telegram message.')
                    if i == 0:
                        if s_ResultMessage != "NULL":
                            media.append(types.InputMediaPhoto(img, caption=s_ResultMessage, parse_mode='HTML'))
                        else:
                            log(message.from_user.id, '[ERROR] Can`t send unformed message')
                            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                            markup.add(types.KeyboardButton("✉Зв'язатися з менеджером"),
                                       types.KeyboardButton("🏠На головну"))
                            bot.send_message(message.chat.id, "❌ Помилка: Помилка форматування тексту.",
                                             reply_markup=markup)
                            return
                    else:
                        media.append(types.InputMediaPhoto(img))
                bot.send_media_group(message.chat.id, media)
                log(message.from_user.id, 'Telegram message was successfully sent')
            else:
                bot.send_message(message.chat.id, s_ResultMessage, parse_mode='HTML')
                log(message.from_user.id, 'Telegram message was sent without images')

        workingPropetiesPool = []
        log(message.from_user.id, 'Creating workingPropetiesPool.')
        for i in range(len(currProductProp)):
            if currProductCount[i] > 0:
                log(message.from_user.id, f'Property {currProductProp[i]} was added to workingPropetiesPool.')
                workingPropetiesPool.append(currProductProp[i])
        if len(currProductProp) == 0:
            return

        log(message.from_user.id, 'Adding properties from workingPropetiesPool to ReplyKeyboardMarkup.')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        row = []
        counter = 0
        for prop in workingPropetiesPool:
            row.append(types.KeyboardButton(prop))
            counter += 1
            if counter % 3 == 0:
                markup.row(*row)
                row = []
        if row:
            markup.row(*row)

        msg = bot.send_message(message.chat.id, "📏Виберіть характеристику товару", reply_markup=markup)
        bot.register_next_step_handler(msg, make_order3, newOrder, currProduct)
        return

def make_order3(message, newOrder, currProduct):
    log(message.from_user.id, "make_order3 called")

    if message.text in ["/start", "🏠На головну"]:
        log(message.from_user.id, '"To main page" button pressed or "/start" command used')
        back_to_main(message)
        return

    prop = message.text.strip()
    currProductProp = currProduct.sl_productProperties
    currProductCount = currProduct.nl_productCount
    currProductPrice = currProduct.nl_productPrice
    if prop in currProductProp:
        propIndex = currProductProp.index(prop)
        for orderIt in currProduct.coritl_orderItemsList:
            if {f"{currProduct.s_productArticle}" : prop } == dict(orderIt):
                currProductCount[propIndex] -= orderIt.count

        if currProductCount[propIndex] > 0:
            newOrder.coritl_orderItemsList[-1].price = currProductPrice[propIndex]
            newOrder.coritl_orderItemsList[-1].count += 1

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("Додати новий товар➕"), types.KeyboardButton("Продовжити➡"))
            log(message.from_user.id, f'{currProduct.s_productArticle} {prop} додано до замовлення')
            msg = bot.send_message(message.chat.id, f"✅ Додано: {currProduct.s_productArticle} {prop}. Бажаєте додати ще товар?",
                                   reply_markup=markup)
            bot.register_next_step_handler(msg, make_order4, newOrder)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(types.KeyboardButton("✉Зв'язатися з менеджером"), types.KeyboardButton("🏠На головну"))
            log(message.from_user.id, f'[ERROR] Товар {currProduct.s_productArticle} {prop} не доступний')
            bot.send_message(message.chat.id, "❌ Помилка: Вибір не наявного товару.", reply_markup=markup)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("✉Зв'язатися з менеджером"), types.KeyboardButton("🏠На головну"))
        log(message.from_user.id, f'[ERROR] Can`t find {prop} for {currProduct.s_productArticle} in database')
        bot.send_message(message.chat.id, "❌ Помилка: Характеристику не знайдено.", reply_markup=markup)


def make_order4(message,newOrder):
    log(message.from_user.id, "make_order4 called")

    if message.text in ["/start", "🏠На головну"]:
        log(message.from_user.id, '"To main page" button pressed')
        back_to_main(message)
        return

    elif message.text == "Додати новий товар➕":
        make_order1(message)

    else:
        newOrder.cus_orderCustomer = dataStructures.Customer(message.from_user.id)
        log(message.from_user.id, "Checking user personal information")
        if len(newOrder.cus_orderCustomer.PIB) < 3:
            log(message.from_user.id, "Starting personal information collecting")
            msg = bot.send_message(
                message.chat.id,
                "Давайте зберемо ваші дані для відправки. <b>Введіть ваше ПІБ:</b>",
                parse_mode='HTML',
                reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(types.KeyboardButton("🏠На головну"))
            )
            bot.register_next_step_handler(msg, get_PIB, newOrder)

        try:
            oneCConn.pushOrder(newOrder)
        except Exception as e:
            pass

        finish_data_colect(message, newOrder)

def get_PIB(message, newOrder):
    log(message.from_user.id, "get_PIB called")

    if message.text in ["🏠На головну", "/start"]:
        log(message.from_user.id, '"To main page" button pressed')
        back_to_main(message)
        return

    if not has_emoji(message.text):
        newOrder.cus_orderCustomer.s_customerPIB = message.text
        msg = bot.send_message(message.chat.id, "Введіть ваш номер телефону:", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_phone, newOrder)
    else:
        msg = bot.send_message(message.chat.id, "Введіть ще раз ваше ПІБ без емодзі:", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_PIB, newOrder)

def get_phone(message, newOrder):
    if message.text in ["🏠На головну", "/start"]:
        log(message.from_user.id, '"To main page" button pressed')
        back_to_main(message)
        return

    if has_emoji(message.text):
        log(message.from_user.id, '[ERROR] Message with phone number has emoji. Asking to re-enter number')
        msg = bot.send_message(message.chat.id, "Номер телефону введено неправильно. Введіть ваш номер ще раз, будь ласка:", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_phone)
        return

    phone = message.text.strip()
    log(message.from_user.id, 'Phone number was got')
    valid = False

    if len(phone) == 10 and phone.startswith("0") and isInt(phone):
        newOrder.cus_orderCustomer.s_customerPhone = f"+38{phone}"
        valid = True
    elif len(phone) == 13 and phone.startswith("+") and isInt(phone[1:]):
        newOrder.cus_orderCustomer.s_customerPhone = phone
        valid = True
    elif len(phone) == 12 and phone.startswith("3") and isInt(phone):
        newOrder.cus_orderCustomer.s_customerPhone = f"+{phone}"
        valid = True

    if valid:
        log(message.from_user.id, 'Phone number was succssefully read')
        msg = bot.send_message(message.chat.id, "Введіть адресу відділення:", parse_mode='HTML')
        bot.register_next_step_handler(msg, finish_data_colect, newOrder)
    else:
        log(message.from_user.id, '[ERROR] Phonr number is not valid. Asking to re-enter number')
        msg = bot.send_message(message.chat.id, "Номер телефону введено неправильно. Спробуйте ще раз:", parse_mode='HTML')
        bot.register_next_step_handler(msg, get_phone, newOrder)

def finish_data_colect(message, newOrder):
    log(message.from_user.id, "finish_data_colect called")

    if message.text == "🏠На головну":
        log(message.from_user.id, '"To main page" button pressed')
        back_to_main(message)
        return

    if not has_emoji(message.text):
        newOrder.cus_orderCustomer.s_customerAddress = message.text
        log(message.from_user.id, f"Address received")
    else:
        log(message.from_user.id, f"[ERROR] Address contains emoji: {message.text}")
        msg = bot.send_message(message.chat.id, "Будь ласка, введіть адресу ще раз без емодзі:", parse_mode='HTML')
        log(message.from_user.id, "Asking user to re-enter address without emoji")
        bot.register_next_step_handler(msg, finish_data_colect)

    try:
        customer = newOrder.cus_orderCustomer
        log(message.from_user.id, "Attempting to insert user into database")
        SQLmake(
            'INSERT INTO users (id, PIB, phone, address) VALUES (?, ?, ?, ?)',
            (customer.s_customerTelegramId, customer.s_customerPIB, customer.s_customerPhone,
             customer.s_customerAddress)
        )
        log(message.from_user.id, "User successfully inserted into database")
        newOrder.n_orderCode = oneCConn.pushOrder(newOrder)
        submit_order_making(message, newOrder)
    except Exception as e:
        log(message.from_user.id, f"[ERROR] Failed to insert user: {e}")


def submit_order_making(message, newOrder):
    log(message.from_user.id, '"To main page" button pressed')

    log(message.from_user.id, 'Forming confirmation message')
    s_ResultMessage = (
        "✅<b>Ваше замовлення відправлено на обробку.</b>\n\n"
        "Ми зв'яжемося з вами щодо доставки протягом дня.\n\n"
        "<b>💛Дякуємо, що вибрали нас!💛</b>"
    )


    log(message.from_user.id , "Sending confirmation message and resetting menu buttons")
    mainMenuButtonsCreate(message, s_ResultMessage)

    try:
        log(message.from_user.id, 'Trying send notification to manager')
        adminChat = bot.get_chat(config["adminIDs"][0])
        log(message.from_user.id, f"Manager id: {config["adminIDs"][0]}")
        username = bot.get_chat(message.from_user.id).username
        szResultMessage = f'‼НОВЕ ЗАМОВЛЕННЯ ВІД КОРИСТУВАЧА <a href="https://t.me/{username}">{username}</a>‼\n'
        szResultMessage += str(newOrder)
        bot.send_message(
            adminChat.id,
            s_ResultMessage,
            parse_mode='HTML'
        )
        log(message.from_user.id, "Notification was sent to manager")
    except Exception as e:
        adminChat = bot.get_chat(config["adminIDs"][0])
        bot.send_message(
            adminChat.id,
            f"Через помилку не можу відправити сповіщення про нове замовлення. Перепровірте список замовлень. Користувач = {username}",
            parse_mode='HTML'
        )

@bot.message_handler(func=lambda message: message.text == "✉Зв'язатися з менеджером")
def contact_to_manager(message):
    log(message.from_user.id, '"Contact to manager" button pressed')
    try:
        adminChat = bot.get_chat(config["adminIDs"][0])
        username = bot.get_chat(message.from_user.id).username
        log(message.from_user.id, f"User username resolved: {username}")

        bot.send_message(
            adminChat.id,
            f'‼‼Запит на зворотній зв\'язок з користувачем <a href="https://t.me/{username}">{username}</a>‼‼',
            parse_mode='HTML'
        )
        log(message.from_user.id, "Contact request sent to admin")

        msg = (
            "🧾 <b>Ваше звернення прийнято!</b>\n\n"
            "Наш менеджер звʼяжеться з вами найближчим часом для уточнення деталей.\n"
            "Якщо у вас є додаткові питання — не соромтеся написати напряму.\n\n"
            f"📞 <b>Контакт менеджера:</b> 🧓 <a href=\"tg://user?id={config['adminIDs'][0]}\">Менеджер</a>\n\n"
            "📦 Дякуємо, що обрали нас! Ми завжди готові допомогти 🤝"
        )
        bot.send_message(message.chat.id, msg, parse_mode='HTML')
        log(message.from_user.id, "Confirmation message sent to user")

    except Exception as e:
        log(message.from_user.id, f"[ERROR] contact_to_manager(): {e}")
        bot.send_message(message.chat.id, "⚠ Не вдалося звʼязатися з менеджером")


@bot.message_handler(func=lambda message: message.text == "🏠На головну")
def back_to_main(message):
    try:
        log(message.from_user.id, '"To main page" button pressed')
        start(message)
        log(message.from_user.id, "start() called from back_to_main")
    except Exception as e:
        log(message.from_user.id, f"[ERROR] back_to_main(): {e}")
        bot.send_message(message.chat.id, "⚠ Не вдалося повернутись на головну сторінку")

def mainMenuButtonsCreate(message, messageText):
    log(message.from_user.id, 'mainMenuButtonsCreate called')

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🛍️Зробити замовлення"))
    markup.add(types.KeyboardButton("🛒Мої замовлення"))
    markup.add(types.KeyboardButton("✉Зв'язатися з менеджером"))
    log(message.from_user.id, "Main menu buttons created")
    bot.send_message(message.chat.id, messageText, reply_markup=markup)
    log(message.from_user.id, "Main menu message sent")

# ================ ADMIN COMMANDS ================
@bot.message_handler(commands=['start_sending'])
def start_sending(message):
    global scheduler_running, activeProductPool , lastSendedArticle
    log(message.from_user.id, 'Command /start_sending used')
    if message.from_user.id in config["adminIDs"]:
        scheduler_running = True
        log_sys('Scheduler started by admin')
        activeProductPoolDict = fetch_as_dicts("SELECT * FROM active_products WHERE show = ?", (1,))
        tempActiveProductPool = [i["product_article"] for i in activeProductPoolDict]
        if tempActiveProductPool:
            activeProductPool = tempActiveProductPool
            lastSendedArticle = ""
        bot.send_message(message.chat.id, "Розсилка запущена🏃‍♀️")

@bot.message_handler(commands=['stop_sending'])
def stop_sending(message):
    global scheduler_running
    log(message.from_user.id, 'Command /stop_sending used')
    if message.from_user.id in config["adminIDs"]:
        scheduler_running = False
        log_sys('Scheduler stopped by admin')
        bot.send_message(message.chat.id, "Розсилка зупинена⛔")

@bot.message_handler(commands=['add_article_to_pool'])
def add_article_to_pool(message):
    log(message.from_user.id, '/add_article_to_pool called')
    if message.from_user.id in config["adminIDs"]:
        msg = bot.send_message(message.chat.id, "Введіть артикул: ")
        bot.register_next_step_handler(msg, submit_adding_article_to_pool)

def submit_adding_article_to_pool(message):
    log(message.from_user.id, '/submit_adding_article_to_pool called')
    showFlag = reCheckShowFlag(message, message.text)
    if showFlag >= 0:
        SQLmake("INSERT INTO activeProductPool VALUES (?, ?)", (message.text, showFlag))
        bot.send_message(message.chat.id, "Артикул додано")
    else:
        bot.send_message(message.chat.id, "⚠ Артикул не знайдено")


def reCheckShowFlag(message, article):
    if message:
        log(message.from_user.id, '/reCheckShowFlag called')
    else:
        log_sys('/reCheckShowFlag called')
    showFlag = 0
    try:
        tempProduct = oneCConn.getNomenclature(article)
        for count in tempProduct.nl_productCount:
            if count == 1:
                showFlag = 1
    except Exception as e:
        showFlag = -1
        if message:
            log(message.from_user.id, f"[ERROR] reCheckShowFlag(): {e}")
        else:
            log_sys(f"[ERROR] reCheckShowFlag(): {e}")

    return showFlag

@bot.message_handler(commands=['today_orders_list'])
def send_orderlist1(message):
    log(message.from_user.id, '/send_orderlist1 called')

    if message.from_user.id in config["adminIDs"]:
        s_ResultMessage = "📃Список замовлень:\n"
        try:
            orderList = oneCConn.getTodayOrders()
            log(message.from_user.id, f'{len(orderList)} orders fetched from 1C')
        except Exception as e:
            log(message.from_user.id, f'[ERROR] Failed to fetch orders: {e}')
            bot.send_message(message.chat.id, "⚠️ Невдалось отрмати список сьогоднішніх замовлень.")
            return

        if not orderList:
            log(message.from_user.id, f'Order list - empty')
            bot.send_message(message.chat.id, "Замовлення відсутні!")
            return

        for order in orderList:
            try:
                username = bot.get_chat(order.cus_orderCustomer.s_customerTelegramId)
            except:
                username = "Unknown"
            s_ResultMessage += f'{order.n_orderCode}. <a href="tg://user?id={order.cus_orderCustomer.s_customerTelegramId}">{username}</a> : {order.s_status}\n'

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        row = []
        for idx, order in enumerate(orderList):
            row.append(types.KeyboardButton(order.n_orderCode))
            if (idx + 1) % 3 == 0:
                markup.row(*row)
                row = []
        if row:
            markup.row(*row)
        log(message.from_user.id, 'Order list buttons generated')
        msg = bot.send_message(message.chat.id, s_ResultMessage, parse_mode='HTML', reply_markup=markup)
        log(message.from_user.id, 'Order list message sent')
        bot.register_next_step_handler(msg, send_orderlist2, None)

def send_orderlist2(message, currOrder):
    log(message.from_user.id, '/send_orderlist2 called')

    if message.text in ["/start", "🏠На головну"]:
        log(message.from_user.id, '"To main page" button pressed')
        start(message)
        return

    if not currOrder:
        log(message.from_user.id, f'Requesting order #{message.text}')
        try:
            currOrder = oneCConn.getOrder(int(message.text))
        except Exception as e:
            log(message.from_user.id, f'[ERROR] Failed to get order: {e}')
            msg = bot.send_message(message.chat.id, "Замовлення не знайдено. Виберіть замовлення ще раз:")
            bot.register_next_step_handler(msg, send_orderlist2)
        if not currOrder:
            log(message.from_user.id, f'[ERROR] Failed to get order: {e}')
            bot.send_message(message.chat.id, "Замовлення не знайдено.")

    currOrderCode = currOrder.n_orderCode

    log(message.from_user.id, f'Order #{currOrderCode} loaded')
    s_ResultMessage = str(currOrder)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Змінити статус"))
    if len(currOrder.TTN) != 0:
        markup.add(types.KeyboardButton("Змінити ТТН"))
    else:
        markup.add(types.KeyboardButton("Додати ТТН"))
    markup.add(types.KeyboardButton("⬅Назад"))

    msg = bot.send_message(message.chat.id, s_ResultMessage, parse_mode='HTML', reply_markup=markup)
    log(message.from_user.id, f'Detailed order #{currOrderCode} message sent')
    bot.register_next_step_handler(msg, send_orderlist3, currOrder)



def send_orderlist3(message, currOrder):
    log(message.from_user.id, '/send_orderlist3 called')

    if message.text == "⬅Назад":
        log(message.from_user.id, 'Back button pressed in order detail view')
        send_orderlist1(message)
        return

    elif message.text in ["/start", "🏠На головну"]:
        log(message.from_user.id, '"To main page" button pressed')
        start(message)
        return

    elif message.text == "Змінити статус":
        log(message.from_user.id, 'Requesting status input')
        msg = bot.send_message(message.chat.id, "🔢Введіть статус", parse_mode='HTML')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        row = []
        for idx, status in enumerate(sl_orderStatusList):
            row.append(types.KeyboardButton(status))
            if (idx + 1) % 3 == 0:
                markup.row(*row)
                row = []
        if row:
            markup.row(*row)
        markup.add(types.KeyboardButton("⬅Назад"))
        bot.register_next_step_handler(msg, change_order_status, currOrder)

    elif message.text in ["Додати ТТН", "Змінити ТТН"]:
        log(message.from_user.id, 'Requesting TTN input')
        msg = bot.send_message(message.chat.id, "🔢Введіть ТТН", parse_mode='HTML')
        bot.register_next_step_handler(msg, add_TTN, currOrder)

def change_order_status(message, currOrder):
    if message.text == "⬅Назад":
        log(message.from_user.id, 'Back button pressed in order detail view')
        send_orderlist2(message, currOrder)
        return

    elif message.text in ["/start", "🏠На головну"]:
        log(message.from_user.id, '"To main page" button pressed')
        start(message)
        return

    elif message.text in sl_orderStatusList:
        log(message.from_user.id, f'Order #{currOrder.n_orderCode} status updated')
        currOrder.s_status = message.text
        oneCConn.updateOrderInfo(currOrder)  # add status TTN to 1c order comments

    else:
        log(message.from_user.id, 'Incorrect status input')
        msg = bot.send_message(message.chat.id, "Введено не правильний статус. Спробуйте ще раз:", parse_mode='HTML')
        bot.register_next_step_handler(msg, change_order_status, currOrder)

def add_TTN(message, currOrder):
    if message.text == "⬅Назад":
        log(message.from_user.id, 'Back button pressed in order detail view')
        send_orderlist2(message, currOrder)
        return

    elif message.text in ["/start", "🏠На головну"]:
        log(message.from_user.id, '"To main page" button pressed')
        start(message)
        return

    try:
        log(message.from_user.id, f'Updating TTN for order #{currOrder.n_orderCode} to "{message.text}"')
        currOrder.s_status = message.text
        oneCConn.updateOrderInfo(currOrder) # add status TTN to 1c order comments
        bot.send_message(message.chat.id, "ТТН успішно оновлено!", parse_mode='HTML')
        send_orderlist2(message, currOrder)
    except Exception as e:
        log(message.from_user.id, f'[ERROR] Failed to update TTN: {e}')


@bot.message_handler(commands=['recheckstatus'])
def reCheckStatus(message):
    try:
        log(message.from_user.id, 'Command /recheckstatus used')
        DataList = fetch_as_dicts("SELECT code, frontImage, backImage FROM orders")
        log(message.from_user.id, f'{len(DataList)} orders fetched for status recheck')

        for data in DataList:
            if len(data["frontImage"]) < 2 and len(data["backImage"]) < 2:
                SQLmake("UPDATE orders SET active = 0 WHERE code = ?", (data['code'],))
                log(message.from_user.id, f'Order #{data["code"]} marked inactive')
            else:
                SQLmake("UPDATE orders SET active = 1 WHERE code = ?", (data['code'],))
                log(message.from_user.id, f'Order #{data["code"]} marked active')
        bot.send_message(message.chat.id, "Статуси товарів були повторно перевірені")
        log(message.from_user.id, 'Order statuses rechecked and message sent')
    except Exception as e:
        log_sys(f"[ERROR] Failed in reCheckStatus: {e}")

# ================ SCHEDULER ================

def formMessageText(article, user_id):
    try:
        nomenclature = oneCConn.getNomenclature(article)
    except:
        log(user_id, f'[ERROR] Failed to form message for {article}: {e}')
        return "NULL"


    log(user_id, f'Start forming message for article: {article}')

    s_properties = ""
    propertiesList = nomenclature.sl_productProperties
    propertiesPriceList = nomenclature.sl_productPrice
    propertiesCountList = nomenclature.nl_productCount
    for i in range(len(nomenclature.sl_productProperties)):
        if propertiesList[i].lower() != "null" and propertiesList[i].strip():
            if propertiesCountList[i] != 0:
                s_properties += f"⬛️ {propertiesList[i].strip()}\n"

    if not s_properties:
        log(user_id, f'{article} is unavailable')
        props = "Немає в наявності"
    else:
        log(user_id, f'{article} availability parsed')

    if len(propertiesPriceList) == 1:
        price_str = f"{propertiesPriceList[0]} грн"
    elif propertiesPriceList:
        try:
            min_price = min([int(p) for p in propertiesPriceList if str(p).isdigit()])
            price_str = f"від {min_price} грн"
        except:
            log(user_id, f'{article} contains non-digit prices')
            price_str = "Ціну уточнюйте"
    else:
        log(user_id, f'{article} has no prices for properties')
        price_str = "Ціну уточнюйте"

    s_ResultMessage = (
        f"🔥<b>{nomenclature.s_productName}</b>🔥\n\n"
        f"Арт.: {article}\n\n"
        f"{nomenclature.s_productDescription}\n\n"
        f"Доступні розміри:\n{props}\n"
        f"💲 Ціна: <b>{price_str}</b> 💲\n\n"
        f'Для замовлення пишіть - <a href="tg://user?id={bot.get_me().id}">Бот🤖</a>\n\n'
    )
    log(user_id, f'Message formed successfully for {article}')
    return s_ResultMessage

def sendMessage():
    try:

        log_sys(f'{len(DataList)} products fetched from database')

        for idx, data in enumerate(DataList):
            if idx == config["LastSendedIndex"]:
                art = data.get("art", "---")
                if data.get('active', False):
                    log_sys(f'Processing active product: {art}')
                    items = fetch_as_dicts(f'SELECT * FROM product_properties WHERE art = ?', (art,))
                    data['availabilityForProperties'] = {}
                    data['priceForProperties'] = {}
                    for item in items:
                        data['availabilityForProperties'][item["property"]] = item['availability']
                        data['priceForProperties'][item["property"]] = item['price']
                    log_sys(f'Properties loaded for {art}')

                    szResultMessage = formMessageText(data, 'system')
                    images = []

                    try:
                        if data.get("frontImage"):
                            images.append(open(data["frontImage"], 'rb'))
                            log_sys(f'Front image added for {art}')
                        if data.get("backImage"):
                            images.append(open(data["backImage"], 'rb'))
                            log_sys(f'Back image added for {art}')
                    except Exception as e:
                        log_sys(f'[ERROR] Failed to open image for {art}: {e}')

                    if images:
                        media = []
                        for i, img in enumerate(images):
                            if i == 0:
                                media.append(types.InputMediaPhoto(img, caption=szResultMessage, parse_mode='HTML'))
                            else:
                                media.append(types.InputMediaPhoto(img))
                        bot.send_media_group(config["channelID"], media)
                        log_sys(f'Message with images sent for {art}')
                    else:
                        bot.send_message(config["channelID"], szResultMessage, parse_mode='HTML')
                        log_sys(f'Message without images sent for {art}')

                    config["LastSendedIndex"] += 1
                    log_sys(f'LastSendedIndex updated to {config["LastSendedIndex"]}')

                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                        log_sys(f'Config saved after sending {art}')
                    return
                else:
                    log_sys(f'{art} is inactive, skipping')
                    config["LastSendedIndex"] += 1
                    with open("config.json", "w", encoding="utf-8") as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                    sendMessage()

        log_sys(f'All products processed. Restarting index')
        config["LastSendedIndex"] = 0
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        log_sys(f'LastSendedIndex reset to 0')
        sendMessage()

    except Exception as e:
        log_sys(f'[ERROR] Failed to send message: {e}')

for hour in range(config["fromHour"], config["toHour"]):
    time_str = f"{hour:02d}:00"
    schedule.every().day.at(time_str).do(sendMessage)

def run_scheduler():
    global scheduler_running
    while True:
        if scheduler_running:
            schedule.run_pending()
        time.sleep(config['timeToSleep'])

scheduler_thread = threading.Thread(target=run_scheduler)
scheduler_thread.start()

try:
    bot.infinity_polling()
except Exception as e:
    log_sys(f"[ERROR] Bot polling failed: {e}")
    input("Press Enter to exit...")