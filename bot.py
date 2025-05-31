import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
BITRIX_WEBHOOK_URL = os.getenv("BITRIX_WEBHOOK_URL")

NAME, CARGO, DIMENSIONS, ROUTE, CONTACT = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reply_keyboard = [["Оформить заявку"]]
    await update.message.reply_text(
        "Приветствуем!\n\n"
        "Чтобы оформить заявку, нажмите кнопку ниже 👇",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    ) 
    return NAME

async def name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Введите информацию о грузе:", reply_markup=ReplyKeyboardRemove())
    return CARGO

async def cargo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["cargo"] = update.message.text
    await update.message.reply_text("Укажите габариты груза (длина, ширина, высота, вес):")
    return DIMENSIONS

async def dimensions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["dimensions"] = update.message.text
    await update.message.reply_text("Укажите маршрут (откуда → куда):")
    return ROUTE

async def route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["route"] = update.message.text
    await update.message.reply_text("Оставьте номер телефона или Telegram для связи:")
    return CONTACT

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["contact"] = update.message.text
    user_data = context.user_data

    tg_user = update.message.from_user
    tg_name = f"{tg_user.first_name or ''} {tg_user.last_name or ''}".strip()
    tg_username = f"@{tg_user.username}" if tg_user.username else "—"
    user_data["tg_name"] = tg_name
    user_data["tg_username"] = tg_username

    message = (
        f"Новая заявка на перевозку 🚚\n\n"
        f"Имя клиента: {user_data['name']}\n"
        f"Telegram: {tg_name} ({tg_username})\n"
        f"Груз: {user_data['cargo']}\n"
        f"Габариты: {user_data['dimensions']}\n"
        f"Маршрут: {user_data['route']}\n"
        f"Контакт: {user_data['contact']}"
    )

    if ADMIN_CHAT_ID:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)

    if BITRIX_WEBHOOK_URL:
        contact_id = create_contact(user_data)
        if contact_id:
            create_deal(contact_id, user_data)

    await update.message.reply_text("Спасибо! Ваша заявка принята. Мы свяжемся с вами в ближайшее время.")
    return ConversationHandler.START

def create_contact(data):
    contact_payload = {
        "fields": {
            "NAME": data["name"],
            "PHONE": [{"VALUE": data["contact"], "VALUE_TYPE": "WORK"}],
            "COMMENTS": f"Груз: {data['cargo']}\nГабариты: {data['dimensions']}\nМаршрут: {data['route']}\nTelegram: {data['tg_name']} ({data['tg_username']})"
        }
    }
    try:
        response = requests.post(f"{BITRIX_WEBHOOK_URL}/crm.contact.add.json", json=contact_payload)
        if response.status_code == 200:
            return response.json().get("result")
    except Exception as e:
        print(f"Ошибка при создании контакта: {e}")
    return None

def create_deal(contact_id, data):
    deal_payload = {
        "fields": {
            "TITLE": f"Перевозка: {data['route']}",
            "CONTACT_ID": contact_id,
            "COMMENTS": f"Груз: {data['cargo']}\nГабариты: {data['dimensions']}\nКонтакт: {data['contact']}\nTelegram: {data['tg_name']} ({data['tg_username']})",
            "STAGE_ID": "NEW"
        }
    }
    try:
        response = requests.post(f"{BITRIX_WEBHOOK_URL}/crm.deal.add.json", json=deal_payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка при создании сделки: {e}")
    return False

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Заявка отменена.")
    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.Regex("^Оформить заявку$"), name)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            CARGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cargo)],
            DIMENSIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, dimensions)],
            ROUTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, route)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
