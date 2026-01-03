import os
import threading
import telebot
from telebot import types
from flask import Flask

# === 1. ТОКЕН ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ Переменная TELEGRAM_BOT_TOKEN не задана! Укажите её в Render.")

bot = telebot.TeleBot(BOT_TOKEN)

# === 2. ТВОЯ ЛОГИКА (БЕЗ ИЗМЕНЕНИЙ) ===
user_sessions = {}

CAR_MODELS = {
    "Toyota": ["Corolla", "Camry", "RAV4", "Hilux"],
    "Chevrolet": ["Cobalt", "Lacetti", "Nexia", "Gentra"],
    "Hyundai": ["Solaris", "Elantra", "Creta", "Tucson"],
    "Kia": ["Rio", "Cerato", "Sportage"],
    "Honda": ["Civic", "Accord", "CR-V"]
}

BASE_PRICES = {
    "Toyota": {"Corolla": 11000, "Camry": 16000, "RAV4": 20000, "Hilux": 23000},
    "Chevrolet": {"Cobalt": 9400, "Lacetti": 8000, "Nexia": 6200, "Gentra": 9800},
    "Hyundai": {"Solaris": 8800, "Elantra": 10000, "Creta": 13500, "Tucson": 14000},
    "Kia": {"Rio": 8500, "Cerato": 10000, "Sportage": 15000},
    "Honda": {"Civic": 11500, "Accord": 12500, "CR-V": 16000}
}

def calculate_price(make: str, model: str, year: int, mileage: int) -> int:
    base = BASE_PRICES.get(make, {}).get(model, 8000)
    age = 2025 - year

    if year <= 2018:
        if age <= 3:
            base *= 0.8
        else:
            base *= 0.8 * (0.90 ** (age - 3))

    expected_mileage = (2025 - year) * 15_000
    extra_km = max(0, mileage - expected_mileage)

    if make == "Chevrolet" and model == "Cobalt":
        deduction = extra_km * 0.015
    elif make in ["Toyota", "Honda"]:
        deduction = extra_km * 0.02
    else:
        deduction = extra_km * 0.018

    final_price = base - deduction

    min_prices = {
        ("Chevrolet", "Cobalt"): 7000,
        ("Hyundai", "Solaris"): 5500,
        ("Kia", "Rio"): 6000,
        ("Toyota", "Corolla"): 7500,
        ("Honda", "Civic"): 8500
    }
    min_price = min_prices.get((make, model), 5000)

    return max(min_price, int(final_price))

def get_make_from_text(text: str) -> str | None:
    for make in CAR_MODELS:
        if text.strip().lower() == make.lower():
            return make
    return None

def get_model_from_text(make: str, text: str) -> str | None:
    models = CAR_MODELS.get(make, [])
    for model in models:
        if text.strip().lower() == model.lower():
            return model
    return None

# === 3. ОБРАБОТЧИКИ (БЕЗ ИЗМЕНЕНИЙ) ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user_sessions[chat_id] = {"step": "make"}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for make in CAR_MODELS:
        markup.add(make)
    bot.send_message(chat_id, "🚗 Привет! Выберите марку авто:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id].get("step") == "make")
def handle_make(message):
    chat_id = message.chat.id
    make = get_make_from_text(message.text)
    if not make:
        bot.send_message(chat_id, "❌ Марка не найдена. Выберите из списка:")
        return
    user_sessions[chat_id] = {"step": "model", "make": make}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for model in CAR_MODELS[make]:
        markup.add(model)
    bot.send_message(chat_id, f"Вы выбрали {make}. Теперь выберите модель:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id].get("step") == "model")
def handle_model(message):
    chat_id = message.chat.id
    session = user_sessions.get(chat_id, {})
    make = session.get("make")
    model = get_model_from_text(make, message.text) if make else None
    if not model:
        bot.send_message(chat_id, "❌ Модель не найдена. Выберите из списка:")
        return
    user_sessions[chat_id] = {"step": "year", "make": make, "model": model}
    bot.send_message(chat_id, "Введите год выпуска (2000–2025):")

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id].get("step") == "year")
def handle_year(message):
    chat_id = message.chat.id
    if not message.text.isdigit():
        bot.send_message(chat_id, "❌ Год должен быть числом. Попробуйте снова:")
        return
    year = int(message.text)
    if not (2000 <= year <= 2025):
        bot.send_message(chat_id, "❌ Год должен быть от 2000 до 2025:")
        return
    session = user_sessions[chat_id]
    user_sessions[chat_id] = {**session, "step": "mileage", "year": year}
    bot.send_message(chat_id, "Введите пробег в километрах:")

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id].get("step") == "mileage")
def handle_mileage(message):
    chat_id = message.chat.id
    if not message.text.isdigit():
        bot.send_message(chat_id, "❌ Пробег должен быть числом:")
        return
    mileage = int(message.text)
    session = user_sessions[chat_id]
    user_sessions[chat_id] = {**session, "step": "photo", "mileage": mileage}
    bot.send_message(chat_id, "Отправьте фото автомобиля (можно одно):")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    if chat_id not in user_sessions or user_sessions[chat_id].get("step") != "photo":
        bot.send_message(chat_id, "❌ Сначала запустите оценку через /start")
        return
    session = user_sessions[chat_id]
    make = session["make"]
    model = session["model"]
    year = session["year"]
    mileage = session["mileage"]
    price = calculate_price(make, model, year, mileage)
    bot.send_message(
        chat_id,
        f"✅ **Оценка завершена!**\n\n"
        f"Марка: {make}\n"
        f"Модель: {model}\n"
        f"Год: {year}\n"
        f"Пробег: {mileage:,} км\n\n"
        f"💰 **Стоимость: ${price:,} USD**\n\n"
        f"📅 Данные актуальны на 02.12.2025\n"
        f"📈 Источник: OLX.uz + Avtoelon.uz",
        parse_mode="Markdown"
    )
    user_sessions.pop(chat_id, None)

@bot.message_handler(func=lambda msg: msg.chat.id in user_sessions and user_sessions[msg.chat.id].get("step") == "photo")
def handle_non_photo(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "📸 Пожалуйста, отправьте фото автомобиля!")

@bot.message_handler(func=lambda msg: msg.chat.id not in user_sessions)
def handle_new_session(message):
    handle_start(message)

# === 4. ФУНКЦИЯ ЗАПУСКА БОТА В ФОНЕ ===
def run_bot():
    bot.delete_webhook()
    print("[OK] Bot started! Send /start in Telegram.")
    bot.infinity_polling(none_stop=True)

# === 5. FLASK-ЗАГЛУШКА ДЛЯ RENDER ===
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Телеграм-бот оценки авто работает!", 200

# === 6. ЗАПУСК ===
if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Запускаем веб-сервер на порту от Render
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
