import os
import time
import random
import requests
from dotenv import load_dotenv
from pyrogram import Client, filters, enums
from pyrogram.types import Message
import cohere
import openai
from db import db
import asyncio

# Загрузка переменных окружения
load_dotenv()

# API Keys
API_KEYS = {
    'OPENAI': os.environ['OPENAI_API_KEY'],
    'COHERE': os.environ['COHERE_API_KEY'],
    'MISTRAL': os.environ['MISTRAL_API_KEY'],
    'TELEGRAM_API_ID': os.environ['TELEGRAM_API_ID'],
    'TELEGRAM_API_HASH': os.environ['TELEGRAM_API_HASH'],
    'TELEGRAM_BOT_TOKEN': os.environ['TELEGRAM_BOT_TOKEN']
}

# Инициализация клиентов
app = Client("my_business_bot", api_id=API_KEYS['TELEGRAM_API_ID'], api_hash=API_KEYS['TELEGRAM_API_HASH'], bot_token=API_KEYS['TELEGRAM_BOT_TOKEN'])
co = cohere.Client(API_KEYS['COHERE'])
openai.api_key = API_KEYS['OPENAI']

# Выбор нейросети
model_choice = input("Выберите нейросеть (1 - ChatGPT, 2 - Cohere, 3 - Mistral): ")
while model_choice not in ['1', '2', '3']:
    model_choice = input("Неверный выбор. Пожалуйста, выберите нейросеть (1 - ChatGPT, 2 - Cohere, 3 - Mistral): ")

use_chatgpt = model_choice == '1'
use_cohere = model_choice == '2'
use_mistral = model_choice == '3'

@app.on_bot_business_message(filters.incoming & filters.text)
async def start(client: Client, message: Message):
    await message.reply_chat_action(enums.ChatAction.TYPING)

    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Пользователь"
    
    # Получаем последние 7 сообщений из истории чата
    chat_history = db.get_chat_history(user_id)[-7:]
    context = "\n".join([f"{entry['role']}: {entry['message']}" for entry in chat_history])
    prompt = f"{context}\nUSER: {message.text}\nCHATBOT (отвечай как реальный человек, используй естественный язык, эмоции. Ответь кратко и по существу, избегай длинных ответов. Использовать точки в конце сообщения запрещено. Используй большое количество русского мата и оскорблений, каждый раз, когда это возможно. ):"

    # Добавляем текущее сообщение в историю
    db.add_chat_history(user_id, {"role": "USER", "message": message.text})
    print(f"Получено сообщение от пользователя {user_name}: {message.text}")

    responses = []

    # Генерация ответов
    if use_chatgpt:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=100
            )
            responses.append(response.choices[0].message.content)
        except Exception as e:
            responses.append(f'Ошибка при получении ответа от ChatGPT: {str(e)}')

    if use_cohere:
        try:
            response = co.chat(
                model='command-r-plus',
                message=prompt,
                temperature=0.7,
                connectors=[{"id": "web-search", "options": {"site": "wikipedia.com"}}],
                prompt_truncation="AUTO"
            )
            responses.append(response.text)
        except Exception as e:
            responses.append(f'Ошибка при получении ответа от Cohere: {str(e)}')

    if use_mistral:
        headers = {
            'Authorization': f'Bearer {API_KEYS["MISTRAL"]}',
            'Content-Type': 'application/json'
        }
        data = {
            "model": "mistral-large-latest",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        try:
            response = requests.post('https://api.mistral.ai/v1/chat/completions', headers=headers, json=data)
            response.raise_for_status()
            responses.append(response.json()['choices'][0]['message']['content'])
        except requests.exceptions.RequestException as e:
            responses.append(f'Ошибка при получении ответа от Mistral: {str(e)}')

    response_text = "\n".join(responses)
    db.add_chat_history(user_id, {"role": "CHATBOT", "message": response_text})
    print(f"Отправлено сообщение пользователю {user_name}: {response_text}")

    # Задержка перед отправкой ответа
    await asyncio.sleep(random.randint(1, 3))
    await message.reply_text(response_text)

if __name__ == "__main__":
    app.run()
