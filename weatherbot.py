import os
import logging
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import telebot
import requests
import json
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

# Отключаем предупреждения SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -- Logging Configuration --
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weatherbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -- Configuration (используй переменные окружения!) --
TOKEN = '8256727883:AAHk2paecc7KzkyGqwvuv3BEWd8R1Mq_PTQ'
OWM_API_KEY = 'a9570d9508d57dc1c705ef6bbad533e4'
DATA_FILE = 'user_data.json'

# Проверка конфигурации
if TOKEN == 'YOUR_BOT_TOKEN_HERE' or OWM_API_KEY == 'YOUR_API_KEY_HERE':
    logger.error("❌ Установи переменные окружения TELEGRAM_BOT_TOKEN и OPENWEATHER_API_KEY!")
    exit(1)

# -- Initialization --
bot = telebot.TeleBot(TOKEN)
tf = TimezoneFinder()

# Исправленная инициализация геолокатора
try:
    import ssl
    # Создаем SSL контекст, который не проверяет сертификаты
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    geolocator = Nominatim(user_agent="enhanced_weatherbot/1.0", timeout=15)
except Exception as e:
    logger.warning(f"SSL context creation failed: {e}")
    geolocator = Nominatim(user_agent="enhanced_weatherbot/1.0", timeout=15)

# -- Weather Icons & Emojis --
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

# -- Enhanced Language Resources --
LANGUAGES = {
    'uk': {
        'welcome':       "🌤️ *Ласкаво просимо до WeatherBot 2.0!*\n\n"
                         "✨ Новинки:\n🏙️ Декілька міст\n📊 Графіки температури\n🚨 Погодні попередження\n\n"
                         "Оберіть мову:",
        'ask_location':  "📍 Надішліть геолокацію або введіть назву міста:",
        'forecast_button':       "🌦️ Прогноз",
        'cities_button':         "🏙️ Мої міста",
        'settings_button':       "⚙️ Налаштування",
        'chart_button':          "📊 Графік",
        'send_location':         "📍 Геолокація",
        'back':                  "🔙 Назад",
        'main_menu':             "🏠 Головне меню",
        'forecast_title':        "{icon} *Прогноз погоди в {city}*\n📅 {date}",
        'select_date':           "📅 Оберіть дату прогнозу",
        'current_weather':       "🌡️ *Зараз:* {temp}°C (відчувається {feels}°C)\n{icon} {desc}\n"
                                 "💧 Вологість: {humidity}%\n💨 Вітер: {wind} м/с\n👁️ Видимість: {visibility} км",
        'hourly':                "🕐 {hour}:00 — {icon} {desc}, {temp}°C",
        'daily_summary':         "\n📊 *За день:* {min}°C → {max}°C",
        'alerts':                "🚨 *Попередження:*\n{alerts}",
        'no_alerts':             "✅ Без попереджень",
        'not_found':             "⚠️ Місто не знайдено. Спробуйте ще раз.",
        'error':                 "❌ Помилка: {error}",
        'confirm_clear_all':     "⚠️ Ви впевнені, що хочете видалити всі збережені міста?",
        'confirm_clear_all_yes': "✅ Так, очистити",
        'cancel':                "❌ Скасування",
        'cancelled':             "❌ Скасовано",
        'invalid_time_format':   "❌ Неправильний формат часу. Використовуйте ГГ:ХХ",
        'enter_city':            "📍 Введіть назву міста:",
        'enter_notification_time': "🕐 Введіть час для сповіщень у форматі ГГ:ХХ (наприклад, 08:30):",
        'all_cities_removed':    "🗑️ Усі міста видалені",
        'clear_cities_button':   "🗑️ Очистити міста",
        'city_added':            "✅ Місто {city} додано",
        'city_removed':          "🗑️ Місто {city} видалено",
        'max_cities':            "⚠️ Максимум 5 міст",
        'saved_cities':          "🏙️ *Збережені міста:*",
        'no_saved_cities':       "📍 Немає збережених міст"
    },
    'ru': {
        'welcome':       "🌤️ *Добро пожаловать в WeatherBot 2.0!*\n\n"
                         "✨ Новинки:\n🏙️ Несколько городов\n📊 Графики температуры\n🚨 Погодные предупреждения\n\n"
                         "Выберите язык:",
        'ask_location':  "📍 Отправьте геолокацию или введите название города:",
        'forecast_button':       "🌦️ Прогноз",
        'cities_button':         "🏙️ Мои города",
        'settings_button':       "⚙️ Настройки",
        'chart_button':          "📊 График",
        'send_location':         "📍 Геолокация",
        'back':                  "🔙 Назад",
        'main_menu':             "🏠 Главное меню",
        'forecast_title':        "{icon} *Прогноз погоды в {city}*\n📅 {date}",
        'select_date':           "📅 Выберите дату прогноза",
        'current_weather':       "🌡️ *Сейчас:* {temp}°C (ощущается {feels}°C)\n{icon} {desc}\n"
                                 "💧 Влажность: {humidity}%\n💨 Ветер: {wind} м/с\n👁️ Видимость: {visibility} км",
        'hourly':                "🕐 {hour}:00 — {icon} {desc}, {temp}°C",
        'daily_summary':         "\n📊 *За день:* {min}°C → {max}°C",
        'alerts':                "🚨 *Предупреждения:*\n{alerts}",
        'no_alerts':             "✅ Без предупреждений",
        'not_found':             "⚠️ Город не найден. Попробуйте снова.",
        'error':                 "❌ Ошибка: {error}",
        'confirm_clear_all':     "⚠️ Вы уверены, что хотите удалить все сохраненные города?",
        'confirm_clear_all_yes': "✅ Да, удалить",
        'cancel':                "❌ Отмена",
        'cancelled':             "❌ Отменено",
        'invalid_time_format':   "❌ Неверный формат времени. Используйте ЧЧ:ММ",
        'enter_city':            "📍 Введите название города:",
        'enter_notification_time': "🕐 Введите время для уведомлений (ЧЧ:ММ):",
        'all_cities_removed':    "🗑️ Все города удалены",
        'clear_cities_button':   "🗑️ Очистить города",
        'city_added':            "✅ Город {city} добавлен",
        'city_removed':          "🗑️ Город {city} удален",
        'max_cities':            "⚠️ Максимум 5 городов",
        'saved_cities':          "🏙️ *Сохраненные города:*",
        'no_saved_cities':       "📍 Нет сохраненных городов"
    },
    'en': {
        'welcome':       "🌤️ *Welcome to WeatherBot 2.0!*\n\n"
                         "✨ What's new:\n🏙️ Multiple cities\n📊 Temperature charts\n🚨 Weather alerts\n\n"
                         "Choose your language:",
        'ask_location':  "📍 Send your location or enter a city name:",
        'forecast_button':       "🌦️ Forecast",
        'cities_button':         "🏙️ My Cities",
        'settings_button':       "⚙️ Settings",
        'chart_button':          "📊 Chart",
        'send_location':         "📍 Location",
        'back':                  "🔙 Back",
        'main_menu':             "🏠 Main menu",
        'forecast_title':        "{icon} *Weather forecast in {city}*\n📅 {date}",
        'select_date':           "📅 Select forecast date",
        'current_weather':       "🌡️ *Now:* {temp}°C (feels like {feels}°C)\n{icon} {desc}\n"
                                 "💧 Humidity: {humidity}%\n💨 Wind: {wind} m/s\n👁️ Visibility: {visibility} km",
        'hourly':                "🕐 {hour}:00 — {icon} {desc}, {temp}°C",
        'daily_summary':         "\n📊 *Today:* {min}°C → {max}°C",
        'alerts':                "🚨 *Weather Alerts:*\n{alerts}",
        'no_alerts':             "✅ No alerts",
        'not_found':             "⚠️ City not found. Try again.",
        'error':                 "❌ Error: {error}",
        'confirm_clear_all':     "⚠️ Are you sure you want to delete all saved cities?",
        'confirm_clear_all_yes': "✅ Yes, clear",
        'cancel':                "❌ Cancel",
        'cancelled':             "❌ Cancelled",
        'invalid_time_format':   "❌ Invalid time format. Use HH:MM",
        'enter_city':            "📍 Enter city name:",
        'enter_notification_time': "🕐 Enter notification time (HH:MM):",
        'all_cities_removed':    "🗑️ All cities removed",
        'clear_cities_button':   "🗑️ Clear cities",
        'city_added':            "✅ City {city} added",
        'city_removed':          "🗑️ City {city} removed",
        'max_cities':            "⚠️ Maximum 5 cities",
        'saved_cities':          "🏙️ *Saved Cities:*",
        'no_saved_cities':       "📍 No saved cities"
    }
}
# -- Data Management --
class DataManager:
    def __init__(self, filename: str):
        self.filename = filename
        self.data = self.load_data()
    
    def load_data(self) -> Dict:
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info(f"Creating new data file: {self.filename}")
            return {}
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return {}
    
    def save_data(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def get_user_settings(self, chat_id: int) -> Dict:
        sid = str(chat_id)
        if sid not in self.data:
            self.data[sid] = {
                'language': 'en',
                'notifications': True,
                'notification_time': '08:00',
                'saved_cities': [],
                'timezone': 'UTC',
                'last_activity': datetime.now().isoformat()
            }
            self.save_data()
        return self.data[sid]
    
    def update_user_setting(self, chat_id: int, key: str, value):
        settings = self.get_user_settings(chat_id)
        settings[key] = value
        settings['last_activity'] = datetime.now().isoformat()
        self.save_data()

# -- Weather API Manager --
class WeatherAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    def normalize_city_name(self, city: str) -> str:
        """Нормализация названия города для избежания дубликатов"""
        return city.strip().title()
    
    def get_current_weather(self, city: str, lang: str = 'en') -> Optional[Dict]:
        try:
            params = {
                'q': city,
                'appid': self.api_key,
                'units': 'metric',
                'lang': lang
            }
            response = requests.get(f"{self.base_url}/weather", params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching current weather: {e}")
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
    
    def get_weather_alerts(self, lat: float, lon: float) -> List[Dict]:
        """Генерирует погодные предупреждения на основе текущих условий"""
        try:
            current = self.get_current_weather_by_coords(lat, lon)
            if not current:
                return []
            
            alerts = []
            temp = current['main']['temp']
            wind_speed = current['wind']['speed']
            visibility = current.get('visibility', 10000) / 1000  # км
            
            # Температурные предупреждения
            if temp > 35:
                alerts.append(f"{ALERT_ICONS['hot']} Экстремальная жара: {temp}°C")
            elif temp < -20:
                alerts.append(f"{ALERT_ICONS['cold']} Экстремальный холод: {temp}°C")
            
            # Ветер
            if wind_speed > 15:
                alerts.append(f"{ALERT_ICONS['wind']} Сильный ветер: {wind_speed} м/с")
            
            # Видимость
            if visibility < 1:
                alerts.append(f"🌫️ Плохая видимость: {visibility} км")
            
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
    def create_temperature_chart(forecast_data: Dict, city: str, lang: str) -> io.BytesIO:
        matplotlib.use('Agg')
        plt.ioff()
        try:
            # Устанавливаем шрифт, который поддерживает эмодзи
            plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'Noto Color Emoji']
            
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

# -- Initialize managers --
data_manager = DataManager(DATA_FILE)
weather_api = WeatherAPI(OWM_API_KEY)

# -- Helper Functions --
def get_weather_icon(description: str) -> str:
    return WEATHER_ICONS.get(description.lower(), '🌤️')

def create_main_keyboard(lang: str) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton(LANGUAGES[lang]['send_location'], request_location=True)
    )
    kb.add(
        types.KeyboardButton(LANGUAGES[lang]['forecast_button']),
        types.KeyboardButton(LANGUAGES[lang]['cities_button'])
    )
    kb.add(
        types.KeyboardButton(LANGUAGES[lang]['chart_button']),
        types.KeyboardButton(LANGUAGES[lang]['settings_button'])
    )
    return kb

def safe_send_message(chat_id: int, text: str, **kwargs):
    try:
        bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Error sending message to {chat_id}: {e}")

# -- Bot Handlers --
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    try:
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

@bot.message_handler(content_types=['location'])
def handle_location(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        
        loc = msg.location
        
        # Сначала попробуем получить погоду по координатам
        weather_data = weather_api.get_current_weather_by_coords(loc.latitude, loc.longitude, lang)
        if not weather_data:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['error'].format(error="Не удалось получить данные о погоде"))
            return
        
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

@bot.message_handler(func=lambda m: m.text and any(m.text == LANGUAGES[lang]['chart_button'] for lang in LANGUAGES.keys()))
def show_chart_options(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        
        saved_cities = settings.get('saved_cities', [])
        if not saved_cities:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['no_saved_cities'])
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for city in saved_cities:
            markup.add(types.InlineKeyboardButton(
                f"📊 {city}", callback_data=f"chart_{city}"
            ))
        
        safe_send_message(
            msg.chat.id,
            LANGUAGES[lang]['weather_chart'],
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_chart_options: {e}")

@bot.message_handler(func=lambda m: m.text and any(m.text == LANGUAGES[lang]['forecast_button'] for lang in LANGUAGES.keys()))
def show_forecast_options(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        
        saved_cities = settings.get('saved_cities', [])
        if not saved_cities:
            safe_send_message(msg.chat.id, LANGUAGES[lang]['no_saved_cities'])
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for city in saved_cities:
            markup.add(types.InlineKeyboardButton(
                f"🌦️ {city}", callback_data=f"forecast_{city}"
            ))
        
        safe_send_message(
            msg.chat.id,
            f"🌦️ {LANGUAGES[lang]['forecast_button']}",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Error in show_forecast_options: {e}")

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
            safe_send_message(msg.chat.id, LANGUAGES[lang]['city_added'].format(city=normalized_city))
            send_current_weather(msg.chat.id, normalized_city, lang)
        else:
            safe_send_message(msg.chat.id, f"⚠️ Город {normalized_city} уже добавлен")
            
    except Exception as e:
        logger.error(f"Error in process_new_city: {e}")

@bot.message_handler(func=lambda m: m.text and any(m.text == LANGUAGES[lang]['settings_button'] for lang in LANGUAGES.keys()))
def show_settings(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Переключатель уведомлений
        notif_text = "🔔 Выкл. уведомления" if settings['notifications'] else "🔔 Вкл. уведомления"
        markup.add(types.InlineKeyboardButton(notif_text, callback_data="toggle_notifications"))
        
        # Время уведомлений
        markup.add(types.InlineKeyboardButton(
            f"🕐 Время: {settings['notification_time']}", 
            callback_data="set_notification_time"
        ))
        
        # Выбор языка
        markup.add(types.InlineKeyboardButton("🌍 Язык", callback_data="change_language"))
        
        # Очистить все города
        if settings.get('saved_cities', []):
            markup.add(types.InlineKeyboardButton("🗑️ Очистить города", callback_data="clear_cities"))
        
        settings_text = f"""⚙️ *Настройки*

🔔 Уведомления: {"включены" if settings['notifications'] else "отключены"}
🕐 Время: {settings['notification_time']}
🌍 Язык: {lang.upper()}
🏙️ Городов сохранено: {len(settings.get('saved_cities', []))}
🕒 Часовой пояс: {settings.get('timezone', 'UTC')}"""
        
        safe_send_message(
            msg.chat.id,
            settings_text,
            parse_mode="Markdown",
            reply_markup=markup
        )
        
    except Exception as e:
        logger.error(f"Error in show_settings: {e}")

@bot.message_handler(func=lambda m: True)
def handle_text_message(msg):
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
            safe_send_message(msg.chat.id, "🤖 Введите название города или нажмите кнопку 📍 Геолокация")
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

def send_current_weather(chat_id: int, city: str, lang: str, lat: float = None, lon: float = None):
    try:
        current_data = weather_api.get_current_weather(city, lang)
        if not current_data:
            safe_send_message(chat_id, LANGUAGES[lang]['not_found'])
            return
        
        # Основная информация о погоде
        temp = round(current_data['main']['temp'])
        feels_like = round(current_data['main']['feels_like'])
        description = current_data['weather'][0]['description'].title()
        icon = get_weather_icon(current_data['weather'][0]['description'])
        humidity = current_data['main']['humidity']
        wind_speed = current_data['wind']['speed']
        visibility = current_data.get('visibility', 10000) / 1000
        
        # Сформировать сообщение
        date_str = datetime.now().strftime("%d.%m.%Y")
        
        message = LANGUAGES[lang]['forecast_title'].format(
            icon=icon, 
            city=current_data['name'], 
            date=date_str
        )
        message += "\n\n" + LANGUAGES[lang]['current_weather'].format(
            temp=temp,
            feels=feels_like,
            icon=icon,
            desc=description,
            humidity=humidity,
            wind=wind_speed,
            visibility=visibility
        )
        
        # Добавить предупреждения если есть координаты
        if lat and lon:
            alerts = weather_api.get_weather_alerts(lat, lon)
            if alerts:
                message += "\n\n" + LANGUAGES[lang]['alerts'].format(alerts="\n".join(alerts))
            else:
                message += "\n\n" + LANGUAGES[lang]['no_alerts']
        
        safe_send_message(chat_id, message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in send_current_weather: {e}")
        safe_send_message(chat_id, LANGUAGES[lang]['error'].format(error=str(e)))

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
        message = f"\n\n🕐 **Почасовой прогноз:**\n"
        
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
    try:
        current_time = datetime.now()
        
        for chat_id_str, settings in data_manager.data.items():
            try:
                if not settings.get('notifications', False):
                    continue
                
                chat_id = int(chat_id_str)
                notification_time = settings.get('notification_time', '08:00')
                timezone_str = settings.get('timezone', 'UTC')
                saved_cities = settings.get('saved_cities', [])
                lang = settings.get('language', 'en')
                
                if not saved_cities:
                    continue
                
                # Проверить время в часовом поясе пользователя
                try:
                    user_tz = pytz.timezone(timezone_str)
                    user_time = current_time.astimezone(user_tz)
                    
                    if user_time.strftime('%H:%M') == notification_time:
                        # Отправить прогноз для первого сохраненного города
                        main_city = saved_cities[0]
                        send_current_weather(chat_id, main_city, lang)
                        
                        # Небольшая задержка чтобы избежать спама
                        time.sleep(1)
                except Exception as tz_e:
                    logger.error(f"Timezone error for {chat_id_str}: {tz_e}")
                    
            except Exception as e:
                logger.error(f"Error sending notification to {chat_id_str}: {e}")
                
    except Exception as e:
        logger.error(f"Error in notification system: {e}")

def notification_scheduler():
    """Планировщик уведомлений"""
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
        settings = data_manager.get_user_settings(call.message.chat.id)
        settings['notifications'] = not settings['notifications']
        data_manager.update_user_setting(call.message.chat.id, 'notifications', settings['notifications'])
        
        lang = settings['language']
        status = "включены" if settings['notifications'] else "отключены"
        
        safe_send_message(call.message.chat.id, f"🔔 Уведомления {status}")
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in toggle_notifications: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "set_notification_time")
def request_notification_time(call):
    try:
        settings = data_manager.get_user_settings(call.message.chat.id)
        lang = settings['language']
        
        msg = bot.send_message(
            call.message.chat.id,
            "🕐 Введите время для уведомлений в формате ЧЧ:ММ (например, 08:30):"
        )
        bot.register_next_step_handler(msg, process_notification_time)
        bot.answer_callback_query(call.id)
        
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
        except ValueError:
            safe_send_message(msg.chat.id, "❌ Неверный формат времени. Используйте ЧЧ:ММ")
            
    except Exception as e:
        logger.error(f"Error in process_notification_time: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "change_language")
def change_language_menu(call):
    try:
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = []
        for code in LANGUAGES.keys():
            buttons.append(types.InlineKeyboardButton(
                code.upper(), callback_data=f"setlang_{code}"
            ))
        markup.add(*buttons)
        
        safe_send_message(
            call.message.chat.id,
            "🌍 Выберите язык:",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in change_language_menu: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
def change_language(call):
    try:
        new_lang = call.data.split('_')[1]
        data_manager.update_user_setting(call.message.chat.id, 'language', new_lang)
        
        safe_send_message(
            call.message.chat.id,
            f"✅ Язык изменен на {new_lang.upper()}",
            reply_markup=create_main_keyboard(new_lang)
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in change_language: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "clear_cities")
def clear_all_cities(call):
    try:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear")
        )
        
        safe_send_message(
            call.message.chat.id,
            "⚠️ Вы уверены, что хотите удалить все сохраненные города?",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in clear_all_cities: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_clear", "cancel_clear"])
def handle_clear_confirmation(call):
    try:
        if call.data == "confirm_clear":
            data_manager.update_user_setting(call.message.chat.id, 'saved_cities', [])
            safe_send_message(call.message.chat.id, "🗑️ Все города удалены")
        else:
            safe_send_message(call.message.chat.id, "❌ Отменено")
            
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in handle_clear_confirmation: {e}")

# -- Help Command --
@bot.message_handler(commands=['help'])
def cmd_help(msg):
    try:
        settings = data_manager.get_user_settings(msg.chat.id)
        lang = settings['language']
        
        help_text = f"""🤖 *WeatherBot 2.0 - Помощь*

🌤️ *Основные функции:*
• Текущая погода с подробной информацией
• Прогноз погоды на несколько дней
• Графики температуры
• Погодные предупреждения
• До 5 сохраненных городов
• Автоматические уведомления

📱 *Как пользоваться:*
• Отправьте геолокацию или название города
• Используйте кнопки для быстрого доступа
• Настройте уведомления в настройках
• Добавляйте города в избранное

🔧 *Команды:*
/start - Запуск бота
/help - Эта справка

💡 *Совет:* Добавьте несколько городов для быстрого доступа к прогнозу!"""
        
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
            "🤖 Я понимаю только текст и геолокацию. Отправьте название города или нажмите кнопку 📍 Геолокация"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_unsupported_content: {e}")

# -- Main Execution --
from flask import Flask, request
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # потом укажешь в Render
WEBHOOK_PATH = ""
WEBHOOK_URL = f"{WEBHOOK_HOST}/{WEBHOOK_PATH}"

app = Flask(__name__)

@app.route(f"/{WEBHOOK_PATH}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

if __name__ == '__main__':
    try:
        logger.info("🚀 Starting WeatherBot 2.0...")
        
        # Проверка API
        test_weather = weather_api.get_current_weather("London", "en")
        if not test_weather:
            logger.error("❌ Cannot connect to OpenWeather API. Check your API key!")
            exit(1)
        logger.info("✅ OpenWeather API connection successful")
        
        # Планировщик уведомлений
        notification_thread = threading.Thread(target=notification_scheduler, daemon=True)
        notification_thread.start()
        logger.info("✅ Notification scheduler started")
        
        logger.info("✅ Bot handlers registered")
        
        # Устанавливаем webhook
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ Webhook set to {WEBHOOK_URL}")
        
        # Запуск Flask-сервера
        port = int(os.environ.get("PORT", 10000))
        app.run(host="0.0.0.0", port=port)

    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
    finally:
        logger.info("🛑 WeatherBot 2.0 shutdown complete")
