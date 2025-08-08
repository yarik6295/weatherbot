import os
import logging
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import telebot
import requests
from pymongo import MongoClient
import schedule
import time
from datetime import datetime, timedelta
from telebot import types
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
import pytz
import threading
import io
from typing import Dict, List, Optional
import urllib3
from datetime import timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weatherbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Затем в коде использовать разные уровни логирования:
logger.debug("Подробная информация для отладки")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка")


def self_ping():
    url = os.environ.get("SELF_URL")
    if not url:
        print("[PING] SELF_URL not set.")
        return
    while True:
        try:
            requests.get(url)
            print(f"[PING] Successfully pinged {url}")
        except Exception as e:
            print(f"[PING] Error: {e}")
        time.sleep(300)  # каждые 5 минут


# Получаем токены из переменных окружения для безопасности
TOKEN = os.getenv("BOT_TOKEN")
OWM_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# MongoDB Atlas connection string (вставьте свой)
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
MONGO_DB_NAME = "weatherbot"
MONGO_COLLECTION = "users"

REQUIRED_ENV_VARS = ["BOT_TOKEN", "OPENWEATHER_API_KEY", "MONGO_CONNECTION_STRING", "WEBHOOK_HOST"]
missing_vars = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
if missing_vars:
    logger.error(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    exit(1)

bot = telebot.TeleBot(TOKEN)
tf = TimezoneFinder()

try:
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    geolocator = Nominatim(user_agent="enhanced_weatherbot/1.0", timeout=15)
except Exception as e:
    logger.warning(f"SSL context creation failed: {e}")
    geolocator = Nominatim(user_agent="enhanced_weatherbot/1.0", timeout=15)

WEATHER_ICONS = {
    'clear sky': '☀️',
    'few clouds': '🌤️',
    'scattered clouds': '⛅',
    'broken clouds': '☁️',
    'overcast clouds': '☁️',
    'shower rain': '🌦️',
    'rain': '🌧️',
    'thunderstorm': '⛈️',
    'snow': '❄️',
    'mist': '🌫️',
    'fog': '🌫️',
    'haze': '🌫️'
}

ALERT_ICONS = {
    'hot': '🔥',
    'cold': '🥶',
    'rain': '☔',
    'storm': '⛈️',
    'snow': '❄️',
    'wind': '💨'
}

LANGUAGES = {
    'ru': {
        'weekdays': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'welcome': "👋 *Приветствуем в MeteoBox📦🌦️!*\n\n✨ Что я умею:\n⛈️ 🌤️ Прогноз погоды на 5 дней\n📊 🌡️ Графики температуры на 5 дней\n🏙️ 📍 Погода в любом городе \n🚨 🌪️ Погодные предупреждения\n🔔 💬 Авто-уведомления о погоде на завтра\n\nВыберите язык:",
        'ask_location': "📍 Отправьте геолокацию или введите название города:",
        'forecast_button': "🌦️ Прогноз",
        'cities_button': "🏙️ Мои города",
        'settings_button': "⚙️ Настройки",
        'chart_button': "📊 График",
        'send_location': "📍 Геолокация",
        'back': "🔙 Назад",
        'main_menu': "🏠 Главное меню",
        'forecast_title': "{icon} *Прогноз погоды в {city}*\n📅 {date}",
        'select_date': "📅 Выберите дату прогноза",
        'select_city_forecast': "🏙️ Выбор города для прогноза",
        'select_date_forecast': "📅 Выбор даты для прогноза",
        'select_city_chart': "🏙️ Выбор города для графика",
        'select_date_chart': "📅 Выбор даты для графика",
        'current_weather': "🌡️ *Сейчас:* {temp}°C (ощущается {feels}°C)\n{icon} {desc}\n💧 Влажность: {humidity}%\n💨 Ветер: {wind} м/с\n👁️ Видимость: {visibility} км",
        'hourly': "🕐 {hour}:00 — {icon} {desc}, {temp}°C",
        'daily_summary': "\n📊 *За день:* {min}°C → {max}°C",
        'alerts': "🚨 *Предупреждения:*\n{alerts}",
        'no_alerts': "✅ Без предупреждений",
        'not_found': "⚠️ Город не найден. Попробуйте снова.",
        'error': "❌ Ошибка: {error}",
        'confirm_clear_all': "⚠️ Вы уверены, что хотите удалить все сохраненные города?",
        'confirm_clear_all_yes': "✅ Да, удалить",
        'cancel': "❌ Отмена",
        'cancelled': "❌ Отменено",
        'invalid_time_format': "❌ Неверный формат времени. Используйте ЧЧ:ММ",
        'enter_city': "📍 Введите название города:",
        'enter_notification_time': "🕐 Введите время для уведомлений (ЧЧ:ММ):",
        'all_cities_removed': "🗑️ Все города удалены",
        'clear_cities_button': "🗑️ Очистить города",
        'city_added': "✅ Город {city} добавлен",
        'city_removed': "🗑️ Город {city} удален",
        'max_cities': "⚠️ Максимум 5 городов",
        'saved_cities': "🏙️ Сохраненные города:",
        'no_saved_cities': "📍 Нет сохраненных городов",
        'add_city': "➕ Добавить город",
        'notifications_on': "🔔 Отключить уведомления",
        'notifications_off': "🔔 Включить уведомления",
        'notification_time': "🕐 Время: {time}",
        'settings_menu': "⚙️ *Настройки*\n\n🔔 Уведомления: {notifications}\n🕐 Время: {time}\n🌐 Язык: {lang}\n🏙️ Городов сохранено: {cities}\n🕒 🌍 Часовой пояс: {timezone}",
        'choose_notification_city_button': "🌆 Город для уведомлений: {city}",
        'choose_notification_city': "🌆 Выберите город для ежедневных уведомлений:",
        'timezone_button': "🌍 Изменить часовой пояс",
        'on': "включены",
        'off': "отключены",
        'notifications_status': "🔔 Уведомления {status}",
        'help': "🤖 *WeatherBot 2.0 - Помощь*\n\n🌤️ *Основные функции:*\n• Текущая погода с подробной информацией\n• Прогноз погоды на несколько дней\n• Графики температуры\n• Погодные предупреждения\n• До 5 сохраненных городов\n• Автоматические уведомления\n\n📱 *Как пользоваться:*\n• Отправьте геолокацию или название города\n• Используйте кнопки для быстрого доступа\n• Настройте уведомления в настройках\n• Добавляйте города в избранное\n\n🔧 *Команды:*\n/start - Запуск бота\n/help - Эта справка\n\n💡 *Совет:* Добавьте несколько городов для быстрого доступа к прогнозу!",
        'only_text_location': "🤖 Я понимаю только текст и геолокацию. Отправьте название города или нажмите кнопку 📍 Геолокация",
        'hourly_forecast': "🕐 **Почасовой прогноз:**",
        'enter_city_or_location': "📍 Введите город или отправьте геолокацию:",
        'enter_notification_time_full': "🕐 Введите время для уведомлений в формате ЧЧ:ММ (например, 08:30):",
        'notifications_scheduled': "🔔 🕐 Уведомления будут приходить в {time}",
        'invalid_time_format_full': "❌ Неверный формат времени. Используйте ЧЧ:ММ",
        'choose_language': "🌍 Выберите язык:",
        'help_full': "🤖 *WeatherBot 2.0 - Помощь*\n\n🌤️ *Основные функции:*\n• Текущая погода с подробной информацией\n• Прогноз погоды на несколько дней\n• Графики температуры\n• Погодные предупреждения\n• До 5 сохраненных городов\n• Автоматические уведомления\n\n📱 *Как пользоваться:*\n• Отправьте геолокацию или название города\n• Используйте кнопки для быстрого доступа\n• Настройте уведомления в настройках\n• Добавляйте города в избранное\n\n🔧 *Команды:*\n/start - Запуск бота\n/help - Эта справка\n\n💡 *Совет:* Добавьте несколько городов для быстрого доступа к прогнозу!",
        'city_tokyo': "Токио",
        'city_london': "Лондон",
        'city_washington': "Вашингтон",
        'city_newyork': "Нью-Йорк",
        'alert_hot': "{icon} Очень жарко! Температура: {temp}°C",
        'alert_cold': "{icon} Очень холодно! Температура: {temp}°C",
        'alert_wind': "{icon} Сильный ветер: {wind} м/с",
        'alert_visibility': "👁️ Плохая видимость: {visibility} км",
        'weather_chart': "График температуры",
        'share_button': "🌟 Рекомендовать бота", 
        'share_message': "Попробуйте этого бота для погоды — он присылает точные прогнозы и уведомления: 👇",  
        'language_tab': "🌐 Язык",
        'language_title': "Выберите язык:",
        'current_language': "Текущий язык: Русский",
        'language_changed': "✅ Язык изменен на Русский",
        'settings_title': "⚙️ Настройки",
        'notifications_tab': "🔔 Уведомления",
        'back_button': "🔙 Назад",
        'choose_timezone': "🌍 Выберите часовой пояс:",
        'timezone_set': "✅ Часовой пояс установлен: {timezone}",
        'uv_index': "☀️ UV индекс: {uv} ({risk})",
        'sun_info': "🌅 Восход: {sunrise} | 🌇 Закат: {sunset}",
        'wind_info': "💨 Ветер: {speed} м/с {direction} (порывы до {gust} м/с)",
        'precipitation_chart': "📊 График осадков и температуры",
        'notification_settings': "🔔 Настройки уведомлений",
        'enable_notifications': "🔔 Включить уведомления",
        'disable_notifications': "🔕 Выключить уведомления",
        'set_notification_city': "🏙 Выбрать город для уведомлений",
        'set_notification_time': "⏰ Установить время уведомлений",
        'location_button': "📍 Мои локации", 
        'wind_directions': ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'],
        'uv_risk': {
            'low': 'низкий',
            'moderate': 'умеренный',
            'high': 'высокий',
            'very_high': 'очень высокий',
            'extreme': 'экстремальный'
        },
        'timezones': {
            'Pacific/Midway': 'Остров Мидуэй',
            'Pacific/Honolulu': 'Гонолулу',
            'America/Anchorage': 'Анкоридж',
            'America/Los_Angeles': 'Лос-Анджелес',
            'America/Denver': 'Денвер',
            'America/Chicago': 'Чикаго',
            'America/New_York': 'Нью-Йорк',
            'America/Halifax': 'Галифакс',
            'America/St_Johns': "Сент-Джонс",
            'America/Sao_Paulo': 'Сан-Паулу',
            'America/Argentina/Buenos_Aires': 'Буэнос-Айрес',
            'America/Noronha': 'Фернанду-ди-Норонья',
            'Atlantic/Azores': 'Азорские острова',
            'Europe/London': 'Лондон',
            'Europe/Paris': 'Париж',
            'Europe/Berlin': 'Берлин',
            'Europe/Moscow': 'Москва',
            'Asia/Dubai': 'Дубай',
            'Asia/Karachi': 'Карачи',
            'Asia/Kolkata': 'Калькутта',
            'Asia/Bangkok': 'Бангкок',
            'Asia/Shanghai': 'Шанхай',
            'Asia/Tokyo': 'Токио',
            'Australia/Sydney': 'Сидней'
        }
    },
    'en': {
        'weekdays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'welcome': "👋 *Welcome to MeteoBox📦🌦️!*\n\n✨ What I can do:\n⛈️ 🌤️ 5-day weather forecast\n📊 🌡️ 5-day temperature charts\n🏙️ 📍 Weather in any city\n🚨 🌪️ Weather warnings\n🔔 💬 Auto-notifications about tomorrow's weather\n\nSelect language:",
        'ask_location': "📍 Send your location or enter a city name:",
        'forecast_button': "🌦️ Forecast",
        'cities_button': "🏙️ My Cities",
        'settings_button': "⚙️ Settings",
        'chart_button': "📊 Chart",
        'send_location': "📍 Location",
        'back': "🔙 Back",
        'main_menu': "🏠 Main menu",
        'forecast_title': "{icon} *Weather forecast in {city}*\n📅 {date}",
        'select_date': "📅 Select forecast date",
        'select_city_forecast': "🏙️ Select city for forecast",
        'select_date_forecast': "📅 Select date for forecast",
        'select_city_chart': "🏙️ Select city for chart",
        'select_date_chart': "📅 Select date for chart",
        'current_weather': "🌡️ *Now:* {temp}°C (feels like {feels}°C)\n{icon} {desc}\n💧 Humidity: {humidity}%\n💨 Wind: {wind} m/s\n👁️ Visibility: {visibility} km",
        'hourly': "🕐 {hour}:00 — {icon} {desc}, {temp}°C",
        'daily_summary': "\n📊 *Today:* {min}°C → {max}°C",
        'alerts': "🚨 *Weather Alerts:*\n{alerts}",
        'no_alerts': "✅ No alerts",
        'not_found': "⚠️ City not found. Try again.",
        'error': "❌ Error: {error}",
        'confirm_clear_all': "⚠️ Are you sure you want to delete all saved cities?",
        'confirm_clear_all_yes': "✅ Yes, clear",
        'cancel': "❌ Cancel",
        'cancelled': "❌ Cancelled",
        'invalid_time_format': "❌ Invalid time format. Use HH:MM",
        'enter_city': "📍 Enter city name:",
        'enter_notification_time': "🕐 Enter notification time (HH:MM):",
        'all_cities_removed': "🗑️ All cities removed",
        'clear_cities_button': "🗑️ Clear cities",
        'city_added': "✅ City {city} added",
        'city_removed': "🗑️ City {city} removed",
        'max_cities': "⚠️ Maximum 5 cities",
        'saved_cities': "🏙️ *Saved Cities:*",
        'no_saved_cities': "📍 No saved cities",
        'add_city': "➕ Add city",
        'notifications_on': "🔔 Turn off notifications",
        'notifications_off': "🔔 Turn on notifications",
        'notification_time': "🕐 Time: {time}",
        'settings_menu': "⚙️ *Settings*\n\n🔔 Notifications: {notifications}\n🕐 Time: {time}\n🌐 Language: {lang}\n🏙️ Saved cities: {cities}\n🕒 🌍 Timezone: {timezone}",
        'choose_notification_city_button': "🌆 Notification city: {city}",
        'choose_notification_city': "🌆 Choose a city for daily notifications:",
        'timezone_button': "🌍 Change timezone",
        'on': "on",
        'off': "off",
        'notifications_status': "🔔 Notifications {status}",
        'help': "🤖 *WeatherBot 2.0 - Help*\n\n🌤️ *Main features:*\n• Current weather with details\n• Weather forecast for several days\n• Temperature charts\n• Weather alerts\n• Up to 5 saved cities\n• Automatic notifications\n\n📱 *How to use:*\n• Send your location or city name\n• Use buttons for quick access\n• Set up notifications in settings\n• Add cities to favorites\n\n🔧 *Commands:*\n/start - Start bot\n/help - This help\n\n💡 *Tip:* Add several cities for quick access to the forecast!",
        'only_text_location': "🤖 I only understand text and location. Send a city name or press 📍 Location",
        'hourly_forecast': "🕐 **Hourly forecast:**",
        'enter_city_or_location': "📍 Enter a city or send your location:",
        'enter_notification_time_full': "🕐 Enter notification time in HH:MM format (e.g., 08:30):",
        'notifications_scheduled': "🔔 Notifications will be sent at {time}",
        'invalid_time_format_full': "❌ Invalid time format. Use HH:MM",
        'choose_language': "🌍 Choose language:",
        'help_full': "🤖 *WeatherBot 2.0 - Help*\n\n🌤️ *Main features:*\n• Current weather with details\n• Weather forecast for several days\n• Temperature charts\n• Weather alerts\n• Up to 5 saved cities\n• Automatic notifications\n\n📱 *How to use:*\n• Send your location or city name\n• Use buttons for quick access\n• Set up notifications in settings\n• Add cities to favorites\n\n🔧 *Commands:*\n/start - Start bot\n/help - This help\n\n💡 *Tip:* Add several cities for quick access to the forecast!",
        'city_tokyo': "Tokyo",
        'city_london': "London",
        'city_washington': "Washington",
        'city_newyork': "New York",
        'alert_hot': "{icon} Very hot! Temperature: {temp}°C",
        'alert_cold': "{icon} Very cold! Temperature: {temp}°C",
        'alert_wind': "{icon} Strong wind: {wind} m/s",
        'alert_visibility': "👁️ Low visibility: {visibility} km",
        'weather_chart': "Temperature chart",
        'share_button': "🌟 Share Bot",  
        'share_message': "Try this weather bot — it sends accurate forecasts and alerts: 👇",  
        'language_tab': "🌐 Language", 
        'language_title': "Select language:",
        'current_language': "Current language: English",
        'language_changed': "✅ Language changed to English",
        'settings_title': "⚙️ Settings",
        'notifications_tab': "🔔 Notifications",
        'back_button': "🔙 Back",
        'choose_timezone': "🌍 Select timezone:",
        'timezone_set': "✅ Timezone set: {timezone}",
        'uv_index': "☀️ UV index: {uv} ({risk})",
        'sun_info': "🌅 Sunrise: {sunrise} | 🌇 Sunset: {sunset}",
        'wind_info': "💨 Wind: {speed} m/s {direction} (gusts to {gust} m/s)",
        'precipitation_chart': "📊 Precipitation and temperature chart",
        'notification_settings': "🔔 Notification settings",
        'enable_notifications': "🔔 Enable notifications",
        'disable_notifications': "🔕 Disable notifications",
        'set_notification_city': "🏙 Set notification city",
        'set_notification_time': "⏰ Set notification time",
        'location_button': "📍 My locations",
        'wind_directions': ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
        'uv_risk': {
            'low': 'low',
            'moderate': 'moderate',
            'high': 'high',
            'very_high': 'very high',
            'extreme': 'extreme'
        },
        'timezones': {
            'Pacific/Midway': 'Midway Island',
            'Pacific/Honolulu': 'Honolulu',
            'America/Anchorage': 'Anchorage',
            'America/Los_Angeles': 'Los Angeles',
            'America/Denver': 'Denver',
            'America/Chicago': 'Chicago',
            'America/New_York': 'New York',
            'America/Halifax': 'Halifax',
            'America/St_Johns': "St. John's",
            'America/Sao_Paulo': 'Sao Paulo',
            'America/Argentina/Buenos_Aires': 'Buenos Aires',
            'America/Noronha': 'Fernando de Noronha',
            'Atlantic/Azores': 'Azores',
            'Europe/London': 'London',
            'Europe/Paris': 'Paris',
            'Europe/Berlin': 'Berlin',
            'Europe/Moscow': 'Moscow',
            'Asia/Dubai': 'Dubai',
            'Asia/Karachi': 'Karachi',
            'Asia/Kolkata': 'Kolkata',
            'Asia/Bangkok': 'Bangkok',
            'Asia/Shanghai': 'Shanghai',
            'Asia/Tokyo': 'Tokyo',
            'Australia/Sydney': 'Sydney'
        }
    },
    'uk': {
        'weekdays': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'],
        'welcome': "👋 *Вітаємо в MeteoBox📦🌦️!*\n\n✨ Що я можу зробити:\n⛈️ 🌤️ 5-денний прогноз погоди\n📊 🌡️ 5-денні графіки температури\n🏙️ 📍 Погода в будь-якому місті\n🚨 🌪️ Погодні попередження\n🔔 💬 Автоматичні сповіщення про погоду на завтра\n\nОберіть мову:",
        'ask_location': "📍 Надішліть геолокацію або введіть назву міста:",
        'forecast_button': "🌦️ Прогноз",
        'cities_button': "🏙️ Мої міста",
        'settings_button': "⚙️ Налаштування",
        'chart_button': "📊 Графік",
        'send_location': "📍 Геолокація",
        'back': "🔙 Назад",
        'main_menu': "🏠 Головне меню",
        'forecast_title': "{icon} *Прогноз погоди в {city}*\n📅 {date}",
        'select_date': "📅 Оберіть дату прогнозу",
        'select_city_forecast': "🏙️ Вибір міста для прогнозу",
        'select_date_forecast': "📅 Вибір дати для прогнозу",
        'select_city_chart': "🏙️ Вибір міста для графіка",
        'select_date_chart': "📅 Вибір дати для графіка",
        'current_weather': "🌡️ *Зараз:* {temp}°C (відчувається {feels}°C)\n{icon} {desc}\n💧 Вологість: {humidity}%\n💨 Вітер: {wind} м/с\n👁️ Видимість: {visibility} км",
        'hourly': "🕐 {hour}:00 — {icon} {desc}, {temp}°C",
        'daily_summary': "\n📊 *За день:* {min}°C → {max}°C",
        'alerts': "🚨 *Попередження:*\n{alerts}",
        'no_alerts': "✅ Без попереджень",
        'not_found': "⚠️ Місто не знайдено. Спробуйте ще раз.",
        'error': "❌ Помилка: {error}",
        'confirm_clear_all': "⚠️ Ви впевнені, що хочете видалити всі збережені міста?",
        'confirm_clear_all_yes': "✅ Так, очистити",
        'cancel': "❌ Скасування",
        'cancelled': "❌ Скасовано",
        'invalid_time_format': "❌ Неправильний формат часу. Використовуйте ГГ:ХХ",
        'enter_city': "📍 Введіть назву міста:",
        'enter_notification_time': "🕐 Введіть час для сповіщень у форматі ГГ:ХХ (наприклад, 08:30):",
        'all_cities_removed': "🗑️ Усі міста видалені",
        'clear_cities_button': "🗑️ Очистити міста",
        'city_added': "✅ Місто {city} додано",
        'city_removed': "🗑️ Місто {city} видалено",
        'max_cities': "⚠️ Максимум 5 міст",
        'saved_cities': "🏙️ *Збережені міста:*",
        'no_saved_cities': "📍 Немає збережених міст",
        'add_city': "➕ Додати місто",
        'notifications_on': "🔔 Вимкнути сповіщення",
        'notifications_off': "🔔 Увімкнути сповіщення",
        'notification_time': "🕐 Час: {time}",
        'settings_menu': "⚙️ *Налаштування*\n\n🔔 Сповіщення: {notifications}\n🕐 Час: {time}\n🌐 Мова: {lang}\n🏙️ Збережено міст: {cities}\n🕒 🌍 Часовий пояс: {timezone}",
        'choose_notification_city_button': "🌆 Місто для сповіщень: {city}",
        'choose_notification_city': "🌆 Оберіть місто для щоденних сповіщень:",
        'timezone_button': "🌍 Змінити часовий пояс",
        'on': "увімкнено",
        'off': "вимкнено",
        'notifications_status': "🔔 Сповіщення {status}",
        'help': "🤖 *WeatherBot 2.0 - Довідка*\n\n🌤️ *Основні функції:*\n• Поточна погода з деталями\n• Прогноз погоди на кілька днів\n• Графіки температури\n• Погодні попередження\n• До 5 збережених міст\n• Автоматичні сповіщення\n\n📱 *Як користуватись:*\n• Надішліть геолокацію або назву міста\n• Використовуйте кнопки для швидкого доступу\n• Налаштуйте сповіщення в налаштуваннях\n• Додавайте міста в обране\n\n🔧 *Команди:*\n/start - Запуск бота\n/help - Ця довідка\n\n💡 *Порада:* Додайте кілька міст для швидкого доступу до прогнозу!",
        'only_text_location': "🤖 Я розумію лише текст і геолокацію. Надішліть назву міста або натисніть кнопку 📍 Геолокація",
        'hourly_forecast': "🕐 **Погодинний прогноз:**",
        'enter_city_or_location': "📍 Введіть місто або надішліть геолокацію:",
        'enter_notification_time_full': "🕐 Введіть час для сповіщень у форматі ГГ:ХХ (наприклад, 08:30):",
        'notifications_scheduled': "🔔 Сповіщення будуть надсилатися о {time}",
        'invalid_time_format_full': "❌ Неправильний формат часу. Використовуйте ГГ:ХХ",
        'choose_language': "🌍 Оберіть мову:",
        'help_full': "🤖 *WeatherBot 2.0 - Довідка*\n\n🌤️ *Основні функції:*\n• Поточна погода з деталями\n• Прогноз погоди на кілька днів\n• Графіки температури\n• Погодні попередження\n• До 5 збережених міст\n• Автоматичні сповіщення\n\n📱 *Як користуватись:*\n• Надішліть геолокацію або назву міста\n• Використовуйте кнопки для швидкого доступу\n• Налаштуйте сповіщення в налаштуваннях\n• Додавайте міста в обране\n\n🔧 *Команди:*\n/start - Запуск бота\n/help - Ця довідка\n\n💡 *Порада:* Додайте кілька міст для швидкого доступу до прогнозу!",
        'city_tokyo': "Токіо",
        'city_london': "Лондон",
        'city_washington': "Вашингтон",
        'city_newyork': "Нью-Йорк",
        'alert_hot': "{icon} Дуже спекотно! Температура: {temp}°C",
        'alert_cold': "{icon} Дуже холодно! Температура: {temp}°C",
        'alert_wind': "{icon} Сильний вітер: {wind} м/с",
        'alert_visibility': "👁️ Погана видимість: {visibility} км",
        'weather_chart': "Графік температури",
        'share_button': "🌟 Порекомендувати бота",  
        'share_message': "Спробуйте цього бота для погоди — він надсилає точні прогнози та сповіщення: 👇",
        'language_tab': "🌐 Мова",
        'language_title': "Оберіть мову:",
        'current_language': "Поточна мова: Українська",
        'language_changed': "✅ Мову змінено на Українську",
        'settings_title': "⚙️ Налаштування",
        'notifications_tab': "🔔 Сповіщення", 
        'back_button': "🔙 Назад",
        'choose_timezone': "🌍 Виберіть часовий пояс:",
        'timezone_set': "✅ Часовий пояс встановлено: {timezone}",
        'uv_index': "☀️ UV індекс: {uv} ({risk})",
        'sun_info': "🌅 Схід: {sunrise} | 🌇 Захід: {sunset}",
        'wind_info': "💨 Вітер: {speed} м/с {direction} (пориви до {gust} м/с)",
        'precipitation_chart': "📊 Графік опадів і температури",
        'notification_settings': "🔔 Налаштування сповіщень",
        'enable_notifications': "🔔 Увімкнути сповіщення",
        'disable_notifications': "🔕 Вимкнути сповіщення",
        'set_notification_city': "🏙 Обрати місто для сповіщень",
        'set_notification_time': "⏰ Встановити час сповіщень",
        'location_button': "📍 Мої локації",
        'wind_directions': ['Пн', 'ПнСх', 'Сх', 'ПдСх', 'Пд', 'ПдЗх', 'Зх', 'ПнЗх'],
        'uv_risk': {
            'low': 'низький',
            'moderate': 'помірний',
            'high': 'високий',
            'very_high': 'дуже високий',
            'extreme': 'екстремальний'
        },
        'timezones': {
            'Pacific/Midway': 'Острів Мідвей',
            'Pacific/Honolulu': 'Гонолулу',
            'America/Anchorage': 'Анкоридж',
            'America/Los_Angeles': 'Лос-Анджелес',
            'America/Denver': 'Денвер',
            'America/Chicago': 'Чикаго',
            'America/New_York': 'Нью-Йорк',
            'America/Halifax': 'Галіфакс',
            'America/St_Johns': "Сент-Джонс",
            'America/Sao_Paulo': 'Сан-Паулу',
            'America/Argentina/Buenos_Aires': 'Буенос-Айрес',
            'America/Noronha': 'Фернанду-ді-Норонья',
            'Atlantic/Azores': 'Азорські острови',
            'Europe/London': 'Лондон',
            'Europe/Paris': 'Париж',
            'Europe/Berlin': 'Берлін',
            'Europe/Moscow': 'Москва',
            'Asia/Dubai': 'Дубай',
            'Asia/Karachi': 'Карачі',
            'Asia/Kolkata': 'Калькутта',
            'Asia/Bangkok': 'Бангкок',
            'Asia/Shanghai': 'Шанхай',
            'Asia/Tokyo': 'Токіо',
            'Australia/Sydney': 'Сідней'
        }
    
    }
}
import logging

# -- Data Management --
class DataManager:
    def __init__(self, MONGO_CONNECTION_STRING: str, db_name: str, collection_name: str):
        try:
            if "retryWrites=true" not in MONGO_CONNECTION_STRING.lower():
                MONGO_CONNECTION_STRING += "?retryWrites=true&w=majority"  # Автодобавление, если отсутствует
            self.client = MongoClient(MONGO_CONNECTION_STRING, serverSelectionTimeoutMS=5000)  # Таймаут 5 сек
            self.client.server_info()  # Проверка подключения
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]
            self.collection.create_index("chat_id", unique=True)
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            exit(1)

    def connect(self, MONGO_CONNECTION_STRING: str, db_name: str, collection_name: str):
        try:
            if "retryWrites=true" not in MONGO_CONNECTION_STRING.lower():
                MONGO_CONNECTION_STRING += "?retryWrites=true&w=majority"
            
            self.client = MongoClient(
                MONGO_CONNECTION_STRING,
                serverSelectionTimeoutMS=5000,
                ssl=True,
                ssl_cert_reqs=ssl.CERT_REQUIRED
            )
            self.client.admin.command('ping')  # Проверка подключения
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]
            self.collection.create_index("chat_id", unique=True)
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise

    def reconnect(self):
        try:
            self.client.admin.command('ping')
            return True
        except:
            try:
                self.connect(self.client.HOST, self.db.name, self.collection.name)
                return True
            except:
                return False
        
    def get_user_settings(self, chat_id: int) -> dict:
        doc = self.collection.find_one({"chat_id": chat_id})
        defaults = {
            "chat_id": chat_id,
            'language': 'ru',
            'notifications': False,
            'notification_time': '20:00',
            'saved_cities': [],
            'timezone': 'Europe/Minsk',
            'last_activity': datetime.now().isoformat(),
            'notification_city': None
        }
        if not doc:
            self.collection.insert_one(defaults)
            return defaults
        # Миграция для старых пользователей: добавляем недостающие поля
        updated = False
        for k, v in defaults.items():
            if k not in doc:
                doc[k] = v
                updated = True
        if updated:
            self.collection.update_one({"chat_id": chat_id}, {"$set": doc})
        return doc

    def update_user_setting(self, chat_id: int, key: str, value):
        # Обновляем только одно поле, но last_activity всегда обновляем
        update = {key: value, 'last_activity': datetime.now().isoformat()}
        self.collection.update_one(
            {"chat_id": chat_id},
            {"$set": update},
            upsert=True
        )

# -- Weather API Manager --
class WeatherAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    def normalize_city_name(self, city: str) -> str:
        """Нормализация названия города для избежания дубликатов"""
        return city.strip().title()
    
    def get_current_weather(self, city: str, lang: str = 'en') -> Optional[Dict]:
        if not city or len(city) > 100:
            return None
            
        try:
            params = {
                'q': city,
                'appid': self.api_key,
                'units': 'metric',
                'lang': lang
            }
            response = requests.get(
                f"{self.base_url}/weather",
                params=params,
                timeout=15,
                verify=True  # Включена проверка SSL
            )
            
            if response.status_code != 200:
                logger.error(f"OWM API Error: {response.status_code} - {response.text}")
                return None
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API Request failed: {e}")
            return None
        except ValueError as e:
            logger.error(f"API JSON decode error: {e}")
            return None
    
    def get_forecast(self, city: str, lang: str = 'en') -> Optional[Dict]:
        try:
            params = {
                'q': city,
                'appid': self.api_key,
                'units': 'metric',
                'lang': lang
            }
            response = requests.get(f"{self.base_url}/forecast", params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching forecast: {e}")
            return None
    
    def get_weather_alerts(self, lat: float, lon: float, lang: str = 'en') -> List[str]:
        """Генерирует погодные предупреждения на основе текущих условий"""
        try:
            current = self.get_current_weather_by_coords(lat, lon, lang)
            if not current:
                return []
            alerts = []
            temp = current['main']['temp']
            wind_speed = current['wind']['speed']
            visibility = current.get('visibility', 10000) / 1000  # км
            # Температурные предупреждения
            if temp > 35:
                alerts.append(LANGUAGES[lang]['alert_hot'].format(icon=ALERT_ICONS['hot'], temp=temp))
            elif temp < -20:
                alerts.append(LANGUAGES[lang]['alert_cold'].format(icon=ALERT_ICONS['cold'], temp=temp))
            # Ветер
            if wind_speed > 15:
                alerts.append(LANGUAGES[lang]['alert_wind'].format(icon=ALERT_ICONS['wind'], wind=wind_speed))
            # Видимость
            if visibility < 1:
                alerts.append(LANGUAGES[lang]['alert_visibility'].format(visibility=visibility))
            return alerts
        except Exception as e:
            logger.error(f"Error getting weather alerts: {e}")
            return []
    
    def get_current_weather_by_coords(self, lat: float, lon: float, lang: str = 'en') -> Optional[Dict]:
        try:
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric',
                'lang': lang
            }
            response = requests.get(f"{self.base_url}/weather", params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching weather by coords: {e}")
            return None

# -- Chart Generator --
class ChartGenerator:
    @staticmethod
    def create_temperature_precipitation_chart(forecast_data, city, lang):
        try:
            plt.style.use('dark_background')
            fig, ax1 = plt.subplots(figsize=(12, 6))
            
            times = []
            temps = []
            precip = []
            
            for item in forecast_data['list'][:24]:
                dt = datetime.fromtimestamp(item['dt'])
                times.append(dt)
                temps.append(item['main']['temp'])
                rain = item.get('rain', {}).get('3h', 0)
                snow = item.get('snow', {}).get('3h', 0)
                precip.append(rain + snow)
            
            # Температура
            ax1.plot(times, temps, color='#FFA500', linewidth=2, label='Температура')
            ax1.set_ylabel('Температура (°C)', color='#FFA500')
            ax1.tick_params(axis='y', colors='#FFA500')
            
            # Осадки
            ax2 = ax1.twinx()
            ax2.bar(times, precip, color='#1E90FF', alpha=0.5, width=0.05, label='Осадки')
            ax2.set_ylabel('Осадки (мм)', color='#1E90FF')
            ax2.tick_params(axis='y', colors='#1E90FF')
            
            ax1.set_title(f'{LANGUAGES[lang]["precipitation_chart"]} - {city}')
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax1.xaxis.set_major_locator(mdates.HourLocator(interval=3))
            
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150)
            buffer.seek(0)
            plt.close(fig)
            return buffer
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return None
    @staticmethod
    def create_temperature_chart(forecast_data: Dict, city: str, lang: str) -> io.BytesIO:
        matplotlib.use('Agg')
        plt.ioff()
        try:
            if not forecast_data or 'list' not in forecast_data:
                return None
                
            # Добавьте проверку данных:
            required_keys = ['dt', 'main', 'weather']
            if not all(key in item for item in forecast_data['list'] for key in required_keys):
                return None
            # Используем только стандартный шрифт, чтобы не было предупреждений
            plt.rcParams['font.family'] = ['DejaVu Sans']
            
            plt.style.use('dark_background')
            fig, ax = plt.subplots(figsize=(12, 6))
            
            times = []
            temps = []
            
            for item in forecast_data['list'][:24]:  # 24 часа
                dt = datetime.fromtimestamp(item['dt'])
                times.append(dt)
                temps.append(item['main']['temp'])
            
            ax.plot(times, temps, color='#00D4FF', linewidth=3, marker='o', markersize=4)
            ax.fill_between(times, temps, alpha=0.3, color='#00D4FF')
            
            # Убираем эмодзи из заголовка
            ax.set_title(f'Temperature Chart - {city}', fontsize=16, color='white', pad=20)
            ax.set_xlabel('Time', fontsize=12, color='white')
            ax.set_ylabel('Temperature (°C)', fontsize=12, color='white')
            
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
            plt.xticks(rotation=45)
            
            ax.grid(True, alpha=0.3)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            plt.tight_layout()
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', 
                       facecolor='#1a1a1a', edgecolor='none')
            buffer.seek(0)
            plt.close(fig)
            
            return buffer
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            return None



# Инициализация DataManager с MongoDB
data_manager = DataManager(MONGO_CONNECTION_STRING, MONGO_DB_NAME, MONGO_COLLECTION)
weather_api = WeatherAPI(OWM_API_KEY)

# -- Helper Functions --
def get_weather_icon(description: str) -> str:
    return WEATHER_ICONS.get(description.lower(), '🌤️')

def create_main_keyboard(chat_id):
    lang = data_manager.get_user_settings(chat_id)['language']
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        types.KeyboardButton(LANGUAGES[lang]['forecast_button']),
        types.KeyboardButton(LANGUAGES[lang]['chart_button'])
    )
    kb.row(
        types.KeyboardButton(LANGUAGES[lang]['share_button']),
        types.KeyboardButton(LANGUAGES[lang]['settings_button'])
    )
    
    if data_manager.get_user_settings(chat_id).get('saved_cities'):
        kb.row(types.KeyboardButton(LANGUAGES[lang]['location_button']))
        
    return kb

def safe_send_message(chat_id: int, text: str, **kwargs):
    try:
        msg = bot.send_message(chat_id, text, **kwargs)
        return msg
    except telebot.apihelper.ApiTelegramException as e:
        if e.result.status_code == 403:
            logger.info(f"User {chat_id} blocked the bot")
            # Можно удалить пользователя из БД:
            data_manager.collection.delete_one({"chat_id": chat_id})
        else:
            logger.error(f"Send error: {e}")
    except Exception as e:
        logger.error(f"Unexpected send error: {e}")

# -- Bot Handlers --
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    try:
        # При /start НЕ очищаем saved_cities, чтобы избранные города не терялись
        # Сбрасываем только настройки уведомлений, но не saved_cities
        data_manager.update_user_setting(msg.chat.id, 'notification_city', None)
        data_manager.update_user_setting(msg.chat.id, 'notification_time', '20:00')
        data_manager.update_user_setting(msg.chat.id, 'notifications', True)
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = []
        for code, lang_data in LANGUAGES.items():
            buttons.append(types.InlineKeyboardButton(
                code.upper(), callback_data=f"lang_{code}"
            ))
        markup.add(*buttons)
        safe_send_message(
            msg.chat.id, 
            LANGUAGES[lang]['welcome'], 
            parse_mode="Markdown", 
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def set_language(call):
    try:
        lang_code = call.data.split('_')[1]
        data_manager.update_user_setting(call.message.chat.id, 'language', lang_code)
        
        safe_send_message(
            call.message.chat.id,
            LANGUAGES[lang_code]['ask_location'],
            reply_markup=create_main_keyboard(lang_code)
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in set_language: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "notifications_settings")
def notification_settings(call):
    try:
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        
        markup = types.InlineKeyboardMarkup()
        
        # Кнопка вкл/выкл уведомлений
        if settings.get('notifications', False):
            markup.add(types.InlineKeyboardButton(
                LANGUAGES[lang]['disable_notifications'],
                callback_data="toggle_notifications"
            ))
        else:
            markup.add(types.InlineKeyboardButton(
                LANGUAGES[lang]['enable_notifications'],
                callback_data="toggle_notifications"
            ))
        
        # Кнопка выбора города
        markup.add(types.InlineKeyboardButton(
            LANGUAGES[lang]['set_notification_city'],
            callback_data="choose_notification_city"
        ))
        
        # Кнопка установки времени
        markup.add(types.InlineKeyboardButton(
            LANGUAGES[lang]['set_notification_time'],
            callback_data="set_notification_time"
        ))
        
        markup.add(types.InlineKeyboardButton(
            LANGUAGES[lang]['back_button'],
            callback_data="back_to_settings"
        ))
        
        bot.edit_message_text(
            LANGUAGES[lang]['notification_settings'],
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in notification_settings: {e}")

# --- Выбор города для уведомлений ---
@bot.callback_query_handler(func=lambda call: call.data == "choose_notification_city")
def choose_notification_city(call):
    try:
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        saved_cities = settings.get('saved_cities', [])
        if not saved_cities:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['no_saved_cities'])
            return
        markup = types.InlineKeyboardMarkup(row_width=2)
        for city in saved_cities:
            markup.add(types.InlineKeyboardButton(city, callback_data=f"set_notification_city_{city}"))
        safe_send_message(call.message.chat.id, "🔔 Выберите город для ежедневных уведомлений:", reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in choose_notification_city: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_notification_city_'))
def set_notification_city(call):
    try:
        city = call.data.split('_', 3)[3]
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        saved_cities = settings.get('saved_cities', [])
        if city not in saved_cities:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['not_found'])
            return
        data_manager.update_user_setting(call.message.chat.id, 'notification_city', city)
        safe_send_message(call.message.chat.id, f"✅ {city} теперь выбран для ежедневных уведомлений о прогнозе.")
        show_settings(call.message)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in set_notification_city: {e}")

@bot.message_handler(content_types=['location'])
def handle_location(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)  # Получаем настройки
        lang = settings['language']  # Извлекаем язык
        
        if not msg.location:
            return
            
        loc = msg.location
        weather_data = weather_api.get_current_weather_by_coords(loc.latitude, loc.longitude, lang)
        
        if not weather_data or 'name' not in weather_data:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['not_found'])
            return
            
        # Добавьте проверку ключей:
        city = weather_data.get('name', 'Unknown')
        timezone = tf.timezone_at(lat=loc.latitude, lng=loc.longitude) or 'UTC'
        
        city = weather_data['name']
        
        # Нормализуем название города
        normalized_city = weather_api.normalize_city_name(city)
        
        # Получить timezone
        try:
            tz = tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
            if tz:
                data_manager.update_user_setting(msg.chat.id, 'timezone', tz)
        except Exception as e:
            logger.warning(f"Error getting timezone: {e}")
        
        # Добавить город в сохраненные если его там нет
        saved_cities = settings.get('saved_cities', [])
        if normalized_city not in saved_cities:
            if len(saved_cities) < 5:
                saved_cities.append(normalized_city)
                data_manager.update_user_setting(msg.chat.id, 'saved_cities', saved_cities)
                safe_send_message(msg.chat.id, LANGUAGES[lang]['city_added'].format(city=normalized_city))
            else:
                safe_send_message(msg.chat.id, LANGUAGES[lang]['max_cities'])
        
        send_current_weather(msg.chat.id, normalized_city, lang, loc.latitude, loc.longitude)
        
    except Exception as e:
        logger.error(f"Error in handle_location: {e}")
        settings = data_manager.get_user_settings(msg.chat.id)
        safe_send_message(msg.chat.id, LANGUAGES[settings['language']]['error'].format(error="Ошибка обработки геолокации"))

@bot.message_handler(func=lambda m: m.text and any(m.text == LANGUAGES[lang]['share_button'] for lang in LANGUAGES.keys()))
def handle_share_button(msg):
    try:
        # Получаем данные
        bot_username = bot.get_me().username
        lang = data_manager.get_user_settings(msg.chat.id)['language']
        share_template = LANGUAGES[lang]['share_message']
        
        # Формируем текст (убедимся, что username без @)
        clean_username = bot_username.lstrip('@')
        final_text = share_template.format(bot_username=clean_username)
        
        # Кодируем текст для URL
        from urllib.parse import quote
        encoded_text = quote(final_text)
        
        # Создаем кнопку с правильным URL
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                text=LANGUAGES[lang].get('share_action', '📤 Отправить'),
                url=f"https://t.me/share/url?url=https://t.me/{clean_username}&text={encoded_text}"
            )
        )
        
        # Отправляем сообщение
        bot.send_message(
            msg.chat.id,
            final_text,
            reply_markup=markup,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Share error: {e}")
        bot.send_message(msg.chat.id, "⚠️ Произошла ошибка при создании ссылки")

@bot.message_handler(func=lambda m: m.text and any(m.text == LANGUAGES[lang]['cities_button'] for lang in LANGUAGES.keys()))
def show_saved_cities(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        
        saved_cities = settings.get('saved_cities', [])
        if not saved_cities:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['no_saved_cities'])
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for city in saved_cities:
            markup.add(
                types.InlineKeyboardButton(f"🌤️ {city}", callback_data=f"weather_{city}"),
                types.InlineKeyboardButton("🗑️", callback_data=f"remove_{city}")
            )
        markup.add(types.InlineKeyboardButton(LANGUAGES[lang]['add_city'], callback_data="add_city"))
        
        safe_send_message(
            msg.chat.id,
            LANGUAGES[lang]['saved_cities'],
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_saved_cities: {e}")

# --- Вместо функции show_chart_options ---
@bot.message_handler(func=lambda m: m.text and any(m.text == LANGUAGES[lang]['chart_button'] for lang in LANGUAGES.keys()))
def show_chart_options(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        saved_cities = settings.get('saved_cities', [])
        if not saved_cities:
            default_cities = [
                LANGUAGES[lang]['city_tokyo'],
                LANGUAGES[lang]['city_london'],
                LANGUAGES[lang]['city_washington'],
                LANGUAGES[lang]['city_newyork']
            ]
            cities = default_cities
        else:
            cities = saved_cities
        markup = types.InlineKeyboardMarkup(row_width=2)
        for city in cities:
            markup.add(types.InlineKeyboardButton(f"📊 {city}", callback_data=f"chartcity_{city}"))
        markup.add(types.InlineKeyboardButton(LANGUAGES[lang]['add_city'], callback_data="add_city"))
        safe_send_message(
            msg.chat.id,
            LANGUAGES[lang]['select_city_chart'],
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_chart_options: {e}")

# --- После show_chart_options ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("chartcity_"))
def handle_chart_city(call):
    try:
        city = call.data.split("_", 1)[1]
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        today = datetime.now()
        markup = types.InlineKeyboardMarkup(row_width=2)
        weekdays = LANGUAGES[lang]['weekdays']
        for i in range(5):
            date = today + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            weekday_idx = date.weekday() % 7
            label = f"{date.strftime('%d.%m')} ({weekdays[weekday_idx]})"
            markup.add(types.InlineKeyboardButton(text=label, callback_data=f"chartdate_{city}_{date_str}"))
        safe_send_message(call.message.chat.id, LANGUAGES[lang]['select_date_chart'], reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in handle_chart_city: {e}")        


@bot.message_handler(func=lambda m: m.text and any(m.text == LANGUAGES[lang]['forecast_button'] for lang in LANGUAGES.keys()))
def show_forecast_options(msg):
    settings = data_manager.get_user_settings(msg.chat.id)
    lang = settings['language']
    saved_cities = settings.get('saved_cities', [])
    if not saved_cities:
        safe_send_message(msg.chat.id, LANGUAGES[lang]['no_saved_cities'])
        return
    # Новый UX: сначала выбор города, потом даты
    markup = types.InlineKeyboardMarkup(row_width=2)
    for city in saved_cities:
        markup.add(types.InlineKeyboardButton(f"🌦️ {city}", callback_data=f"forecastcity_{city}"))
    markup.add(types.InlineKeyboardButton(LANGUAGES[lang]['add_city'], callback_data="add_city"))
    safe_send_message(
        msg.chat.id,
        LANGUAGES[lang]['select_city_forecast'],
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("forecastcity_"))
def handle_forecast_city(call):
    try:
        city = call.data.split("_", 1)[1]
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        today = datetime.now()
        markup = types.InlineKeyboardMarkup(row_width=2)
        weekdays = LANGUAGES[lang]['weekdays']
        for i in range(5):
            date = today + timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            weekday_idx = date.weekday() % 7
            label = f"{date.strftime('%d.%m')} ({weekdays[weekday_idx]})"
            markup.add(types.InlineKeyboardButton(text=label, callback_data=f"forecastdate_{city}_{date_str}"))
        safe_send_message(call.message.chat.id, LANGUAGES[lang]['select_date_forecast'], reply_markup=markup)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in handle_forecast_city: {e}")
    except Exception as e:
        logger.error(f"Error in show_forecast_options: {e}")     

# --- После handle_forecast_city ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("forecastdate_"))
def handle_forecast_date(call):
    try:
        _, city, date_str = call.data.split("_", 2)
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        send_forecast_for_date(call.message.chat.id, city, lang, date_str)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in handle_forecast_date: {e}")

# --- После handle_chart_city ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("chartdate_"))
def handle_chart_date(call):
    try:
        _, city, date_str = call.data.split("_", 2)
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        forecast_data = weather_api.get_forecast(city, lang)
        if not forecast_data:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['not_found'])
            return
        # Фильтруем только по выбранной дате
        filtered = {'list': [item for item in forecast_data['list'] if datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d') == date_str]}
        if not filtered['list']:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['not_found'])
            return
        chart_buffer = ChartGenerator.create_temperature_chart(filtered, city, lang)
        if chart_buffer:
            bot.send_photo(
                call.message.chat.id,
                chart_buffer,
                caption=f"📊 {LANGUAGES[lang]['weather_chart']} - {city} ({date_str})"
            )
        else:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['error'].format(error="Chart generation failed"))
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in handle_chart_date: {e}")


# --- После handle_forecast_date ---
def send_forecast_for_date(chat_id: int, city: str, lang: str, selected_date: str):
    try:
        forecast_data = weather_api.get_forecast(city, lang)
        if not forecast_data:
            safe_send_message(chat_id, LANGUAGES[lang]['not_found'])
            return
        # Формируем динамический заголовок
        try:
            date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
        except Exception:
            date_obj = None
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        if date_obj:
            date_str = date_obj.strftime('%d.%m.%Y')
            if date_obj.date() == today:
                day_text = 'на сегодня'
            elif date_obj.date() == tomorrow:
                day_text = 'на завтра'
            else:
                weekday = LANGUAGES[lang]['weekdays'][date_obj.weekday()] if 'weekdays' in LANGUAGES[lang] else date_obj.strftime('%A')
                day_text = f"на {weekday} ({date_str})"
        else:
            day_text = f"на {selected_date}"
        header = f"🌤️ Прогноз погоды {day_text} в городе {city}:\n\n"
        message = ""
        for item in forecast_data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            if dt.strftime('%Y-%m-%d') != selected_date:
                continue
            hour = dt.strftime('%H')
            temp = round(item['main']['temp'])
            desc = item['weather'][0]['description'].title()
            icon = get_weather_icon(item['weather'][0]['description'])
            message += LANGUAGES[lang]['hourly'].format(
                hour=hour,
                icon=icon,
                desc=desc,
                temp=temp
            ) + "\n"
        if not message.strip():
            message = LANGUAGES[lang]['not_found']
        else:
            message = header + message
        logger.info(f"[NOTIFY] chat_id={chat_id} city={city} lang={lang} date={selected_date} message_len={len(message)} message_preview={message[:100]}")
        safe_send_message(chat_id, message)
    except Exception as e:
        logger.error(f"Error in send_forecast_for_date: {e} | chat_id={chat_id} city={city} lang={lang} date={selected_date}")
        safe_send_message(chat_id, LANGUAGES[lang]['error'].format(error=str(e)))


@bot.callback_query_handler(func=lambda call: call.data.startswith('weather_'))
def show_city_weather(call):
    try:
        city = call.data.split('_', 1)[1]
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        
        send_current_weather(call.message.chat.id, city, lang)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in show_city_weather: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('forecast_'))
def show_city_forecast(call):
    try:
        city = call.data.split('_', 1)[1]
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        
        send_forecast(call.message.chat.id, city, lang)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in show_city_forecast: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('chart_'))
def send_weather_chart(call):
    try:
        city = call.data.split('_', 1)[1]
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        
        forecast_data = weather_api.get_forecast(city, lang)
        if not forecast_data:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['not_found'])
            return
        
        chart_buffer = ChartGenerator.create_temperature_chart(forecast_data, city, lang)
        if chart_buffer:
            bot.send_photo(
                call.message.chat.id,
                chart_buffer,
                caption=f"📊 {LANGUAGES[lang]['weather_chart']} - {city}"
            )
        else:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['error'].format(error="Chart generation failed"))
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in send_weather_chart: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
def remove_city(call):
    try:
        city = call.data.split('_', 1)[1]
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        
        saved_cities = settings.get('saved_cities', [])
        if city in saved_cities:
            saved_cities.remove(city)
            data_manager.update_user_setting(call.message.chat.id, 'saved_cities', saved_cities)
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['city_removed'].format(city=city))
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in remove_city: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "add_city")
def request_new_city(call):
    try:
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        
        if len(settings.get('saved_cities', [])) >= 5:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['max_cities'])
        else:
            msg = bot.send_message(call.message.chat.id, "📍 Введите название города:")
            bot.register_next_step_handler(msg, process_new_city)
        
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in request_new_city: {e}")

def process_new_city(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        city = msg.text.strip()
        
        # Проверяем погоду для города
        weather_data = weather_api.get_current_weather(city, lang)
        if not weather_data:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['not_found'])
            return
        
        # Нормализуем название города
        normalized_city = weather_api.normalize_city_name(weather_data['name'])
        
        # Добавляем в сохраненные
        saved_cities = settings.get('saved_cities', [])
        if normalized_city not in saved_cities:
            saved_cities.append(normalized_city)
            data_manager.update_user_setting(msg.chat.id, 'saved_cities', saved_cities)
            # Если пользователь не выбирал город для уведомлений вручную, делаем этот город городом для уведомлений
            if not settings.get('notification_city'):
                data_manager.update_user_setting(msg.chat.id, 'notification_city', normalized_city)
                safe_send_message(msg.chat.id, f"✅ {normalized_city} теперь выбран для ежедневных уведомлений о прогнозе.")
            safe_send_message(msg.chat.id, LANGUAGES[lang]['city_added'].format(city=normalized_city))
            send_current_weather(msg.chat.id, normalized_city, lang)
        else:
            safe_send_message(msg.chat.id, f"⚠️ Город {normalized_city} уже добавлен")
            
    except Exception as e:
        logger.error(f"Error in process_new_city: {e}")

@bot.message_handler(func=lambda m: m.text in [LANGUAGES[lang]['settings_button'] for lang in LANGUAGES])
def show_settings(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(LANGUAGES[lang]['notifications_tab'], callback_data="notifications_settings"),
            types.InlineKeyboardButton(LANGUAGES[lang]['language_tab'], callback_data="language_settings")
        )
        markup.row(
            types.InlineKeyboardButton(LANGUAGES[lang]['timezone_button'], callback_data="timezone_settings")
        )
        
        safe_send_message(
            msg.chat.id,
            LANGUAGES[lang]['settings_title'],
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_settings: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "language_settings")
def show_languages(call):
    user_lang = data_manager.get_user_settings(call.message.chat.id)['language']
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Русский", callback_data="set_lang_ru"),
        types.InlineKeyboardButton("English", callback_data="set_lang_en")
    )
    markup.row(
        types.InlineKeyboardButton("Українська", callback_data="set_lang_uk"),
        types.InlineKeyboardButton(LANGUAGES[user_lang]['back_button'], callback_data="back_to_settings")
    )
    
    bot.edit_message_text(
        LANGUAGES[user_lang]['language_title'],
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )



# 3. Обработчик смены языка
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def set_language(call):
    lang = call.data.split("_")[2]  # ru/en/uk
    data_manager.update_user_setting(call.message.chat.id, 'language', lang)
    
    bot.answer_callback_query(call.id, LANGUAGES[lang]['language_changed'])
    show_settings(call.message)  # Возврат в меню настроек    
    
# --- Выбор часового пояса ---
def change_timezone_menu(call):
    try:
        bot.answer_callback_query(call.id)
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings.get('language', 'en')
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = []
        
        # Получаем переведенные названия часовых поясов
        timezones_translated = LANGUAGES[lang]['timezones']
        
        for tz_id, city_name in timezones_translated.items():
            try:
                tz = pytz.timezone(tz_id)
                now = datetime.now(pytz.utc)
                offset = tz.utcoffset(now)
                hours = int(offset.total_seconds() // 3600)
                minutes = abs(int((offset.total_seconds() % 3600) // 60))
                
                offset_str = f"UTC{hours:+d}"
                if minutes > 0:
                    offset_str += f":{minutes:02d}"
                
                buttons.append(types.InlineKeyboardButton(
                    f"{city_name} ({offset_str})",
                    callback_data=f"set_timezone_{tz_id}"
                ))
            except Exception as e:
                logger.error(f"Error processing timezone {tz_id}: {e}")
                continue
        
        # Разбиваем кнопки на два ряда для лучшего отображения
        half = len(buttons) // 2
        markup.add(*buttons[:half])
        markup.add(*buttons[half:])
        
        # Кнопка возврата с учетом языка
        markup.add(types.InlineKeyboardButton(
            LANGUAGES[lang]['back_button'],
            callback_data="back_to_settings"
        ))
        
        bot.edit_message_text(
            LANGUAGES[lang]['choose_timezone'],
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"Error in change_timezone_menu: {e}")
        safe_send_message(call.message.chat.id, LANGUAGES.get(lang, 'en')['error'].format(error=str(e)))

@bot.callback_query_handler(func=lambda call: call.data == "timezone_settings")
def timezone_settings(call):
    try:
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings.get('language', 'en')
        timezones_translated = LANGUAGES[lang]['timezones']
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        
        # Создаем список кортежей (tz_id, city_name) для сортировки
        tz_list = [(tz_id, city_name) for tz_id, city_name in timezones_translated.items()]
        
        # Сортируем по смещению UTC
        def get_utc_offset(tz_id):
            try:
                tz = pytz.timezone(tz_id)
                return tz.utcoffset(datetime.now(pytz.utc)).total_seconds()
            except:
                return 0
                
        tz_list.sort(key=lambda x: get_utc_offset(x[0]))
        
        # Создаем кнопки с учетом сортировки
        buttons = []
        for tz_id, city_name in tz_list:
            try:
                tz = pytz.timezone(tz_id)
                offset = tz.utcoffset(datetime.now(pytz.utc))
                hours = int(offset.total_seconds() // 3600)
                
                buttons.append(types.InlineKeyboardButton(
                    f"{city_name} (UTC{hours:+d})",
                    callback_data=f"set_timezone_{tz_id}"
                ))
            except Exception as e:
                logger.error(f"Error processing timezone {tz_id}: {e}")
                continue
        
        # Разбиваем на два ряда для лучшего отображения
        half = len(buttons) // 2
        markup.add(*buttons[:half])
        markup.add(*buttons[half:])
        
        markup.add(types.InlineKeyboardButton(
            LANGUAGES[lang]['back_button'],
            callback_data="back_to_settings"
        ))
        
        bot.edit_message_text(
            LANGUAGES[lang]['choose_timezone'],
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"Error in timezone_settings: {e}")
        safe_send_message(call.message.chat.id, LANGUAGES.get(lang, 'en')['error'].format(error=str(e)))

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_timezone_"))
def set_timezone(call):
    try:
        tz = call.data.replace("set_timezone_", "")
        data_manager.update_user_setting(call.message.chat.id, 'timezone', tz)
        safe_send_message(call.message.chat.id, f"✅ Часовой пояс установлен: {tz}")
        show_settings(call.message)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in set_timezone: {e}")

@bot.message_handler(func=lambda m: True)
def handle_text_message(msg):
    text = msg.text.strip()
    if not text or any(char in text for char in [';', '"', "'", '\\']):
        safe_send_message(msg.chat.id, "Недопустимые символы в запросе")
        return
    if len(text) > 100:  # Защита от длинных сообщений
        safe_send_message(msg.chat.id, "Слишком длинный запрос")
        return
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        text = msg.text.strip()
        
        # Проверяем, не является ли это кнопкой
        all_button_texts = []
        for l in LANGUAGES.keys():
            all_button_texts.extend([
                LANGUAGES[l]['forecast_button'],
                LANGUAGES[l]['cities_button'], 
                LANGUAGES[l]['settings_button'],
                LANGUAGES[l]['chart_button'],
                LANGUAGES[l]['send_location']
            ])
        
        # Если это текст кнопки - игнорируем (уже обработано выше)
        if text in all_button_texts:
            return
        
        # Проверяем на команды
        if text.startswith('/'):
            return
            
        # Проверяем длину и содержание - если слишком короткое или содержит много эмодзи
        if len(text) < 2 or len(text) > 100:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['enter_city_or_location'])
            return
        
        # Проверяем погоду для введенного города
        weather_data = weather_api.get_current_weather(text, lang)
        if not weather_data:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['not_found'])
            return
        
        # Нормализуем название города
        city_name = weather_api.normalize_city_name(weather_data['name'])
        saved_cities = settings.get('saved_cities', [])
        # Добавить город в сохраненные если его там нет
        if city_name not in saved_cities:
            if len(saved_cities) < 5:
                saved_cities.append(city_name)
                data_manager.update_user_setting(msg.chat.id, 'saved_cities', saved_cities)
                safe_send_message(msg.chat.id, LANGUAGES[lang]['city_added'].format(city=city_name))
            else:
                safe_send_message(msg.chat.id, LANGUAGES[lang]['max_cities'])
        send_current_weather(msg.chat.id, city_name, lang)
            
    except Exception as e:
        logger.error(f"Error in handle_text_message: {e}")

def send_current_weather(chat_id, city, lang, lat=None, lon=None):
    try:
        current_data = weather_api.get_current_weather(city, lang)
        if not current_data:
            safe_send_message(chat_id, LANGUAGES[lang]['not_found'])
            return
        
        # Основные данные
        temp = round(current_data['main']['temp'])
        feels_like = round(current_data['main']['feels_like'])
        description = current_data['weather'][0]['description'].title()
        icon = get_weather_icon(current_data['weather'][0]['description'])
        
        # Ветер
        wind_speed = current_data['wind']['speed']
        wind_gust = current_data['wind'].get('gust', wind_speed)
        wind_dir = get_wind_direction(current_data['wind'].get('deg'), lang)
        
        # Солнце
        sunrise = datetime.fromtimestamp(current_data['sys']['sunrise']).strftime('%H:%M')
        sunset = datetime.fromtimestamp(current_data['sys']['sunset']).strftime('%H:%M')
        
        # UV индекс
        uv_info = ""
        if lat and lon:
            uv, risk = get_uv_index(lat, lon)
            if uv is not None:
                uv_info = "\n" + LANGUAGES[lang]['uv_index'].format(uv=uv, risk=risk)
        
        message = (
            f"{icon} *Погода в {city}*\n"
            f"🌡️ {temp}°C (ощущается {feels_like}°C)\n"
            f"{description}\n\n"
            f"{LANGUAGES[lang]['wind_info'].format(speed=wind_speed, direction=wind_dir, gust=wind_gust)}\n"
            f"💧 Влажность: {current_data['main']['humidity']}%\n"
            f"📊 Давление: {current_data['main']['pressure']} гПа\n"
            f"{LANGUAGES[lang]['sun_info'].format(sunrise=sunrise, sunset=sunset)}"
            f"{uv_info}"
        )
        
        safe_send_message(chat_id, message, parse_mode="Markdown")
        
        # Отправляем график
        forecast_data = weather_api.get_forecast(city, lang)
        if forecast_data:
            chart_buffer = ChartGenerator.create_temperature_precipitation_chart(forecast_data, city, lang)
            if chart_buffer:
                bot.send_photo(chat_id, chart_buffer, caption=LANGUAGES[lang]['precipitation_chart'])
        
    except Exception as e:
        logger.error(f"Error in send_current_weather: {e}")

def get_uv_index(lat, lon, lang='en'):
    """Получает UV-индекс по координатам с переводом"""
    try:
        response = requests.get(
            f"https://api.openweathermap.org/data/2.5/uvi?lat={lat}&lon={lon}&appid={OWM_API_KEY}"
        )
        uv = response.json().get('value', 0)
        
        if uv <= 2:
            risk = LANGUAGES[lang]['uv_risk']['low']
        elif uv <= 5:
            risk = LANGUAGES[lang]['uv_risk']['moderate']
        elif uv <= 7:
            risk = LANGUAGES[lang]['uv_risk']['high']
        elif uv <= 10:
            risk = LANGUAGES[lang]['uv_risk']['very_high']
        else:
            risk = LANGUAGES[lang]['uv_risk']['extreme']
            
        return uv, risk
    except:
        return None, None

def get_wind_direction(degrees, lang='en'):
    """Возвращает направление ветра на указанном языке"""
    if lang == 'ru':
        directions = ['↓ С', '↙ СВ', '← В', '↖ ЮВ', '↑ Ю', '↗ ЮЗ', '→ З', '↘ СЗ']
    elif lang == 'uk':
        directions = ['↓ Пн', '↙ ПнСх', '← Сх', '↖ ПдСх', '↑ Пд', '↗ ПдЗх', '→ Зх', '↘ ПнЗх']
    else:  # en
        directions = ['↓ N', '↙ NE', '← E', '↖ SE', '↑ S', '↗ SW', '→ W', '↘ NW']
    
    return directions[round(degrees / 45) % 8] if degrees is not None else ""

def send_forecast(chat_id: int, city: str, lang: str):
    try:
        forecast_data = weather_api.get_forecast(city, lang)
        if not forecast_data:
            safe_send_message(chat_id, LANGUAGES[lang]['not_found'])
            return

        # Получаем текущую погоду тоже
        current_data = weather_api.get_current_weather(city, lang)
        if current_data:
            send_current_weather(chat_id, city, lang)

        # Формируем прогноз на несколько часов
        message = "\n\n" + LANGUAGES[lang]['hourly_forecast'] + "\n"

        for i, item in enumerate(forecast_data['list'][:8]):  # 8 записей = ~24 часа
            dt = datetime.fromtimestamp(item['dt'])
            hour = dt.strftime('%H')
            temp = round(item['main']['temp'])
            desc = item['weather'][0]['description'].title()
            icon = get_weather_icon(item['weather'][0]['description'])

            message += LANGUAGES[lang]['hourly'].format(
                hour=hour,
                icon=icon,
                desc=desc,
                temp=temp
            ) + "\n"

        safe_send_message(chat_id, message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in send_forecast: {e}")
        safe_send_message(chat_id, LANGUAGES[lang]['error'].format(error=str(e)))

# -- Notification System --
def send_notifications():
    """Send daily weather notifications to users at their preferred time"""
    try:
        logger.info("[NOTIFICATIONS] Starting notification cycle")
        
        # Get current UTC time (more reliable than local time)
        utc_now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        logger.debug(f"[NOTIFICATIONS] Current UTC time: {utc_now}")
        
        # Get all users with notifications enabled in one query
        users = data_manager.collection.find({
            'notifications': True,
            'saved_cities': {'$exists': True, '$ne': []}
        })
        
        notification_count = 0
        error_count = 0
        
        for user in users:
            try:
                chat_id = user["chat_id"]
                settings = data_manager.get_user_settings(chat_id)  # Get fresh settings
                lang = settings.get('language', 'en')
                
                # Skip if no saved cities or notifications disabled
                if not settings.get('notifications', False) or not settings.get('saved_cities'):
                    continue
                
                # Get user's timezone
                timezone_str = settings.get('timezone', 'UTC')
                try:
                    user_tz = pytz.timezone(timezone_str)
                except pytz.UnknownTimeZoneError:
                    logger.warning(f"[NOTIFICATIONS] Unknown timezone {timezone_str} for user {chat_id}, using UTC")
                    user_tz = pytz.UTC
                
                # Convert UTC to user's local time
                user_now = utc_now.astimezone(user_tz)
                today_str = user_now.strftime('%Y-%m-%d')
                
                # Parse notification time (default to 20:00)
                notification_time = settings.get('notification_time', '20:00')
                try:
                    notif_hour, notif_minute = map(int, notification_time.split(':'))
                except ValueError:
                    logger.warning(f"[NOTIFICATIONS] Invalid time format {notification_time} for user {chat_id}, using 20:00")
                    notif_hour, notif_minute = 20, 0
                
                # Check if it's time to send notification
                if (user_now.hour, user_now.minute) != (notif_hour, notif_minute):
                    continue
                
                # Check if we already sent notification today
                last_sent = settings.get('last_notification_date')
                if last_sent == today_str:
                    logger.debug(f"[NOTIFICATIONS] Already sent to {chat_id} today")
                    continue
                
                # Get notification city (default to first saved city)
                notification_city = settings.get('notification_city')
                saved_cities = settings.get('saved_cities', [])
                city = notification_city if notification_city in saved_cities else saved_cities[0]
                
                # Calculate tomorrow's date in user's timezone
                tomorrow_date = (user_now + timedelta(days=1)).strftime('%Y-%m-%d')
                
                logger.info(f"[NOTIFICATIONS] Sending to {chat_id} for {city} ({tomorrow_date})")
                
                # Send forecast
                send_forecast_for_date(chat_id, city, lang, tomorrow_date)
                
                # Update last sent date
                data_manager.update_user_setting(chat_id, 'last_notification_date', today_str)
                notification_count += 1
                
            except Exception as user_error:
                error_count += 1
                logger.error(f"[NOTIFICATIONS] Error for user {user.get('chat_id')}: {str(user_error)}", exc_info=True)
                continue
        
        logger.info(f"[NOTIFICATIONS] Completed. Sent: {notification_count}, Errors: {error_count}")
        
    except Exception as e:
        logger.critical(f"[NOTIFICATIONS] System error: {str(e)}", exc_info=True)

def notification_scheduler():
    """Планировщик уведомлений"""
    print("📡 Notification scheduler started.")
    schedule.every().minute.do(send_notifications)
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Проверяем каждые 30 секунд
        except Exception as e:
            logger.error(f"Error in notification scheduler: {e}")
            time.sleep(60)

@bot.callback_query_handler(func=lambda call: call.data == "toggle_notifications")
def toggle_notifications(call):
    try:
        bot.answer_callback_query(call.id)
        settings = data_manager.get_user_settings(call.message.chat.id)
        settings['notifications'] = not settings['notifications']
        data_manager.update_user_setting(call.message.chat.id, 'notifications', settings['notifications'])
        lang = settings['language']
        status = LANGUAGES[lang]['on'] if settings['notifications'] else LANGUAGES[lang]['off']
        safe_send_message(call.message.chat.id, LANGUAGES[lang]['notifications_status'].format(status=status))
        show_settings(call.message)  # Обновить меню
    except Exception as e:
        logger.error(f"Error in toggle_notifications: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "set_notification_time")
def request_notification_time(call):
    try:
        bot.answer_callback_query(call.id)
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']

        msg = bot.send_message(
            call.message.chat.id,
            LANGUAGES[lang]['enter_notification_time_full']
        )
        bot.register_next_step_handler(msg, process_notification_time)

    except Exception as e:
        logger.error(f"Error in request_notification_time: {e}")

def process_notification_time(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']

        time_text = msg.text.strip()

        # Проверить формат времени
        try:
            datetime.strptime(time_text, '%H:%M')
            data_manager.update_user_setting(msg.chat.id, 'notification_time', time_text)
            safe_send_message(
                msg.chat.id,
                LANGUAGES[lang]['notifications_scheduled'].format(time=time_text)
            )
            show_settings(msg)
        except ValueError:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['invalid_time_format_full'])

    except Exception as e:
        logger.error(f"Error in process_notification_time: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "change_language")
def change_language_menu(call):
    try:
        bot.answer_callback_query(call.id)
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = []
        for code in LANGUAGES.keys():
            buttons.append(types.InlineKeyboardButton(
                code.upper(), callback_data=f"setlang_{code}"
            ))
        markup.add(*buttons)

        safe_send_message(
            call.message.chat.id,
            LANGUAGES[lang]['choose_language'],
            reply_markup=markup
        )

    except Exception as e:
        logger.error(f"Error in change_language_menu: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
def change_language(call):
    try:
        new_lang = call.data.split('_')[1]
        data_manager.update_user_setting(call.message.chat.id, 'language', new_lang)
        safe_send_message(
            call.message.chat.id,
            LANGUAGES[new_lang]['language_changed'].format(lang=new_lang.upper()),
            reply_markup=create_main_keyboard(new_lang)
        )
        show_settings(call.message)  # Обновить меню
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Error in change_language: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "clear_cities")
def clear_all_cities(call):
    try:
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(LANGUAGES[lang]['confirm_clear_all_yes'], callback_data="confirm_clear"),
            types.InlineKeyboardButton(LANGUAGES[lang]['cancel'], callback_data="cancel_clear")
        )

        safe_send_message(
            call.message.chat.id,
            LANGUAGES[lang]['confirm_clear_all'],
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Error in clear_all_cities: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_clear", "cancel_clear"])
def handle_clear_confirmation(call):
    try:
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        if call.data == "confirm_clear":
            data_manager.update_user_setting(call.message.chat.id, 'saved_cities', [])
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['all_cities_removed'])
        else:
            safe_send_message(call.message.chat.id, LANGUAGES[lang]['cancelled'])

        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Error in handle_clear_confirmation: {e}")

# -- Help Command --
@bot.message_handler(commands=['help'])
def cmd_help(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']

        help_text = LANGUAGES[lang].get('help_full', LANGUAGES[lang]['help'])
        safe_send_message(msg.chat.id, help_text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in cmd_help: {e}")

# -- Error Handler --
@bot.message_handler(func=lambda message: True, content_types=['audio', 'photo', 'voice', 'video', 'document',
                                                              'sticker', 'video_note', 'contact', 'venue'])
def handle_unsupported_content(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']

        safe_send_message(
            msg.chat.id,
            LANGUAGES[lang]['only_text_location']
        )

    except Exception as e:
        logger.error(f"Error in handle_unsupported_content: {e}")

# -- Main Execution --
from flask import Flask, request
import os

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например, https://your-app.onrender.com
WEBHOOK_PATH = ""  # всегда пусто, чтобы был '/'
WEBHOOK_URL = f"{WEBHOOK_HOST}/"

app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")  # Добавьте в переменные окружения
if not os.getenv("WEBHOOK_SECRET"):
    logger.error("❌ WEBHOOK_SECRET not set! Generate it first.")
    exit(1)

@app.route("/", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET and request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
        return "Forbidden", 403
        
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "error", 500

@app.route("/", methods=["GET"])
def healthcheck():
    return "ok", 200

def test_connections():
    # Проверка MongoDB
    try:
        data_manager.client.admin.command('ping')
        print("✅ MongoDB connection successful")
    except Exception as e:
        print(f"❌ MongoDB failed: {e}")

    # Проверка OpenWeather
    test_weather = weather_api.get_current_weather("London", "en")
    print(f"🌤️ Weather test: {'✅' if test_weather else '❌'}")

if __name__ == '__main__':
    logger.info("🚀 Starting WeatherBot 2.0...")

    def init_background_tasks():
        try:
            # Проверка API
            try:
                test_forecast = weather_api.get_forecast("London", "en")
                if not test_forecast:
                    logger.error("❌ OpenWeather API returned empty forecast. Check your API key or quota.")
            except Exception as test_e:
                logger.error(f"❌ OpenWeather API check failed: {test_e}")


            # Устанавливаем webhook для Telegram
            set_hook = bot.set_webhook(url=WEBHOOK_URL)
            if set_hook:
                logger.info(f"✅ Webhook set to {WEBHOOK_URL}")
            else:
                logger.error(f"❌ Failed to set webhook to {WEBHOOK_URL}")

            # Запуск планировщика уведомлений
            scheduler_thread = threading.Thread(target=notification_scheduler, daemon=True)
            scheduler_thread.start()
        except Exception as e:
            logger.error(f"💥 Background init error: {e}")

    threading.Thread(target=self_ping, daemon=True).start()

    # Запускаем фоновые задачи без блокировки Flask
    threading.Thread(target=init_background_tasks, daemon=True).start()

    try:
        # Flask стартует сразу
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
    finally:
        logger.info("🛑 WeatherBot 2.0 shutdown complete")
