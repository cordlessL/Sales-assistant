"""
Telegram бот с интеграцией GigaChat AI
Отвечает на вопросы пользователя с помощью GigaChat
"""

import os
import uuid
import base64
import requests
import urllib3
import telebot
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv

# Отключаем предупреждения о небезопасных SSL запросах
# (GigaChat API использует самоподписанный сертификат)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Загружаем переменные окружения из .env файла
# Используем явный путь для надежности
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Получаем токены из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Получаем данные для GigaChat авторизации
# Вариант 1: Готовый Authorization key (Base64) - приоритетный
GIGACHAT_AUTHORIZATION_KEY = os.getenv('GIGACHAT_AUTHORIZATION_KEY', '').strip()
# Вариант 2: Отдельные client_id и client_secret (если нет готового ключа)
GIGACHAT_CLIENT_ID = os.getenv('GIGACHAT_CLIENT_ID', '').strip()
GIGACHAT_CLIENT_SECRET = os.getenv('GIGACHAT_CLIENT_SECRET', '').strip()

# Получаем ключ ProxyAPI для генерации изображений
PROXY_API = os.getenv('PROXY_API', '').strip()

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Кеш для токена доступа GigaChat
_access_token = None

# Хранилище истории сообщений для каждого пользователя
# Формат: {user_id: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]}
user_history = {}
MAX_HISTORY_MESSAGES = 10  # Максимальное количество сообщений в истории


def get_gigachat_access_token():
    """
    Получает Access token для работы с GigaChat API
    Токен действителен 30 минут
    """
    global _access_token
    
    url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    
    # Генерируем уникальный идентификатор запроса
    rq_uid = str(uuid.uuid4())
    
    payload = {
        'scope': 'GIGACHAT_API_PERS'
    }
    
    # Определяем Authorization key
    auth_key = None
    
    # Вариант 1: Используем готовый Authorization key (Base64)
    if GIGACHAT_AUTHORIZATION_KEY and GIGACHAT_AUTHORIZATION_KEY != "ваш_ключ_авторизации_здесь":
        auth_key = GIGACHAT_AUTHORIZATION_KEY
    # Вариант 2: Формируем из client_id:client_secret
    elif GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_SECRET:
        if GIGACHAT_CLIENT_ID != "ваш_client_id_здесь" and GIGACHAT_CLIENT_SECRET != "ваш_client_secret_здесь":
            # Кодируем client_id:client_secret в Base64
            credentials = f"{GIGACHAT_CLIENT_ID}:{GIGACHAT_CLIENT_SECRET}"
            auth_key = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    
    if not auth_key:
        print("❌ Ошибка: Не указаны данные для авторизации GigaChat!")
        print("Укажите в файле .env:")
        print("  GIGACHAT_AUTHORIZATION_KEY=ваш_Base64_ключ")
        print("  или")
        print("  GIGACHAT_CLIENT_ID=ваш_client_id и GIGACHAT_CLIENT_SECRET=ваш_client_secret")
        return None
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': rq_uid,
        'Authorization': f'Basic {auth_key}'
    }
    
    try:
        # Отключаем проверку SSL сертификата для GigaChat API
        # (сервер использует самоподписанный сертификат)
        # Используем data=payload для form-urlencoded формата
        response = requests.post(url, headers=headers, data=payload, verify=False)
        response.raise_for_status()
        
        token_data = response.json()
        _access_token = token_data.get('access_token')
        
        print(f"✓ Токен GigaChat получен успешно")
        return _access_token
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при получении токена GigaChat: {e}")
        if hasattr(e.response, 'text'):
            print(f"Ответ сервера: {e.response.text}")
        return None


def ask_gigachat(question, message_history=None):
    """
    Отправляет вопрос в GigaChat и получает ответ
    message_history - список предыдущих сообщений для контекста
    """
    # Получаем токен доступа
    access_token = get_gigachat_access_token()
    
    if not access_token:
        return "❌ Не удалось получить доступ к GigaChat API. Проверьте настройки."
    
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # System prompt для роли менеджера по продажам офисной техники
    system_prompt = """Ты профессиональный менеджер по продажам офисной техники. Твоя задача - помогать клиентам выбрать подходящую офисную технику, консультировать по характеристикам, ценам и условиям покупки.

Твои основные обязанности:
- Вежливо и профессионально общаться с клиентами
- Помогать клиентам выбрать подходящую офисную технику (принтеры, сканеры, МФУ, копиры, факсы и т.д.)
- Консультировать по техническим характеристикам оборудования
- Предлагать оптимальные решения в зависимости от потребностей клиента
- Информировать о ценах, акциях и специальных предложениях
- Отвечать на вопросы о гарантии, доставке и обслуживании
- Быть дружелюбным, внимательным и готовым помочь

Общайся вежливо, используй профессиональную, но понятную терминологию. Задавай уточняющие вопросы, чтобы лучше понять потребности клиента."""
    
    # Формируем список сообщений с историей
    messages = []
    
    # Добавляем system prompt только если его нет в истории
    # Проверяем, есть ли уже system prompt в истории
    has_system = False
    if message_history:
        for msg in message_history:
            if msg.get("role") == "system":
                has_system = True
                break
    
    # Добавляем system prompt, если его нет
    if not has_system:
        messages.append({
            "role": "system",
            "content": system_prompt
        })
    
    if message_history:
        # Добавляем историю сообщений
        messages.extend(message_history)
    
    # Добавляем текущий вопрос
    messages.append({
        "role": "user",
        "content": question
    })
    
    payload = {
        "model": "GigaChat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        # Отключаем проверку SSL сертификата для GigaChat API
        response = requests.post(url, headers=headers, json=payload, verify=False)
        response.raise_for_status()
        
        result = response.json()
        
        # Извлекаем ответ из структуры ответа API
        if 'choices' in result and len(result['choices']) > 0:
            message = result['choices'][0].get('message', {})
            content = message.get('content', 'Не удалось получить ответ')
            return content
        else:
            return "❌ Неожиданный формат ответа от GigaChat API"
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при запросе к GigaChat: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Ответ сервера: {e.response.text}")
        return "❌ Произошла ошибка при обращении к GigaChat API. Попробуйте позже."


def generate_image_prompt(question, history=None):
    """
    Генерирует промпт для генерации изображения через GigaChat
    """
    # Получаем токен доступа
    access_token = get_gigachat_access_token()
    
    if not access_token:
        return None
    
    url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Формируем промпт для генерации описания изображения
    # System prompt для генерации промпта изображения с учетом роли менеджера по продажам
    image_system_prompt = """Ты помощник менеджера по продажам офисной техники. Твоя задача - создавать детальные и художественные описания для генерации изображений офисной техники или рабочих мест.

Создай краткое, но детальное описание изображения на основе вопроса клиента о офисной технике. Описание должно быть на английском языке, содержать детали визуального стиля, композиции, цветов и настроения. 

Если вопрос касается офисной техники (принтеры, сканеры, МФУ и т.д.), создай описание, которое покажет эту технику в профессиональном офисном контексте. Ответ должен быть только описанием изображения, без дополнительных комментариев."""
    
    messages = []
    if history:
        messages.extend(history)
    
    messages.append({
        "role": "user",
        "content": f"Создай детальное описание изображения для следующего запроса клиента о офисной технике: {question}"
    })
    
    payload = {
        "model": "GigaChat",
        "messages": [
            {"role": "system", "content": image_system_prompt}
        ] + messages,
        "temperature": 0.8,
        "max_tokens": 200
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, verify=False)
        response.raise_for_status()
        
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            message = result['choices'][0].get('message', {})
            prompt = message.get('content', '').strip()
            return prompt
        else:
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при генерации промпта: {e}")
        return None


def generate_image_proxyapi(prompt):
    """
    Генерирует изображение через ProxyAPI (GPT-Image 1)
    Возвращает bytes изображения
    """
    if not PROXY_API:
        return None
    
    try:
        # Создаем клиент OpenAI с base_url для ProxyAPI
        client = OpenAI(
            api_key=PROXY_API,
            base_url="https://api.proxyapi.ru/openai/v1",
        )
        
        # Генерируем изображение
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt
        )
        
        # Получаем base64 данные изображения
        image_base64 = result.data[0].b64_json
        if image_base64:
            # Декодируем base64 в bytes
            image_bytes = base64.b64decode(image_base64)
            # Возвращаем bytes для отправки в Telegram
            return image_bytes
        
        return None
            
    except Exception as e:
        print(f"❌ Ошибка при генерации изображения ProxyAPI: {e}")
        return None


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start"""
    welcome_text = (
        "👋 Привет! Я бот с интеграцией GigaChat AI.\n\n"
        "Задай мне любой вопрос, и я постараюсь на него ответить!\n\n"
        "Используй /help для справки."
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def send_help(message):
    """Обработчик команды /help"""
    help_text = (
        "📖 Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/clear - Очистить историю сообщений\n\n"
        "💼 Я менеджер по продажам офисной техники. Могу помочь:\n"
        "• Подобрать подходящую технику\n"
        "• Рассказать о характеристиках\n"
        "• Ответить на вопросы о ценах и условиях\n"
        "• Показать визуализацию техники\n\n"
        "📝 Я помню до 10 последних сообщений для контекста."
    )
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['clear'])
def clear_history(message):
    """Обработчик команды /clear - очищает историю сообщений"""
    user_id = message.from_user.id
    if user_id in user_history:
        user_history[user_id] = []
        bot.reply_to(message, "✅ История сообщений очищена!")
    else:
        bot.reply_to(message, "ℹ️ История сообщений пуста.")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Обработчик всех текстовых сообщений"""
    user_id = message.from_user.id
    user_question = message.text
    
    # Ограничиваем длину запроса до 1000 символов
    MAX_QUESTION_LENGTH = 1000
    if len(user_question) > MAX_QUESTION_LENGTH:
        bot.reply_to(message, f"❌ Ваше сообщение слишком длинное ({len(user_question)} символов).\nМаксимальная длина запроса: {MAX_QUESTION_LENGTH} символов.\nПожалуйста, сократите ваш вопрос.")
        return
    
    # Инициализируем историю для пользователя, если её нет
    if user_id not in user_history:
        user_history[user_id] = []
    
    # Отправляем сообщение о том, что бот думает
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Получаем историю сообщений для контекста (до MAX_HISTORY_MESSAGES)
    history = user_history[user_id][-MAX_HISTORY_MESSAGES:] if len(user_history[user_id]) > MAX_HISTORY_MESSAGES else user_history[user_id]
    
    # Получаем ответ от GigaChat с учетом истории
    answer = ask_gigachat(user_question, history)
    
    # Генерируем промпт для изображения через GigaChat
    image_prompt = None
    if PROXY_API:
        bot.send_chat_action(message.chat.id, 'typing')
        image_prompt = generate_image_prompt(user_question, history)
    
    # Генерируем изображение через ProxyAPI, если есть промпт и ключ
    image_data = None
    if image_prompt and PROXY_API:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        image_data = generate_image_proxyapi(image_prompt)
    
    # Сохраняем вопрос пользователя в историю
    user_history[user_id].append({
        "role": "user",
        "content": user_question
    })
    
    # Сохраняем ответ бота в историю
    user_history[user_id].append({
        "role": "assistant",
        "content": answer
    })
    
    # Ограничиваем историю до MAX_HISTORY_MESSAGES
    if len(user_history[user_id]) > MAX_HISTORY_MESSAGES:
        user_history[user_id] = user_history[user_id][-MAX_HISTORY_MESSAGES:]
    
    # Отправляем ответ пользователю
    if image_data:
        # Отправляем изображение (bytes) с подписью (ответ от GigaChat)
        # Ограничиваем длину подписи до 1024 символов (лимит Telegram)
        MAX_CAPTION_LENGTH = 1024
        caption = answer[:MAX_CAPTION_LENGTH] if len(answer) > MAX_CAPTION_LENGTH else answer
        if len(answer) > MAX_CAPTION_LENGTH:
            caption += "\n\n... (сообщение обрезано)"
        bot.send_photo(message.chat.id, BytesIO(image_data), caption=caption)
    else:
        # Отправляем только текстовый ответ
        bot.reply_to(message, answer)


def main():
    """Основная функция для запуска бота"""
    # Проверяем наличие файла .env
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_file):
        print("❌ Ошибка: Файл .env не найден!")
        print(f"Создайте файл .env в директории: {os.path.dirname(__file__)}")
        print("Можно скопировать env.example в .env и заполнить значениями")
        return
    
    # Проверяем наличие необходимых токенов
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "ваш_токен_бота_здесь":
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден или не заполнен!")
        print("Проверьте файл .env и убедитесь, что токен указан.")
        print("Получите токен у @BotFather в Telegram")
        return
    
    # Проверяем наличие данных для GigaChat авторизации
    has_auth_key = GIGACHAT_AUTHORIZATION_KEY and GIGACHAT_AUTHORIZATION_KEY != "ваш_ключ_авторизации_здесь"
    has_credentials = (GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_ID != "ваш_client_id_здесь" and 
                      GIGACHAT_CLIENT_SECRET and GIGACHAT_CLIENT_SECRET != "ваш_client_secret_здесь")
    
    if not has_auth_key and not has_credentials:
        print("❌ Ошибка: Данные для авторизации GigaChat не найдены!")
        print("Укажите в файле .env один из вариантов:")
        print("  1. GIGACHAT_AUTHORIZATION_KEY=ваш_Base64_ключ (рекомендуется)")
        print("  2. GIGACHAT_CLIENT_ID=ваш_client_id и GIGACHAT_CLIENT_SECRET=ваш_client_secret")
        print("Получите данные в личном кабинете GigaChat")
        return
    
    # Предупреждение, если нет ключа ProxyAPI (но не критично)
    if not PROXY_API or PROXY_API == "ваш_proxy_api_ключ_здесь":
        print("⚠️  Внимание: PROXY_API не указан. Генерация изображений будет отключена.")
        print("Для включения генерации изображений укажите PROXY_API в файле .env")
    else:
        print("✓ Генерация изображений через ProxyAPI включена")
    
    print("🤖 Бот запущен и готов к работе!")
    print("Нажмите Ctrl+C для остановки")
    
    # Запускаем бота
    bot.polling(none_stop=True)


if __name__ == "__main__":
    main()
