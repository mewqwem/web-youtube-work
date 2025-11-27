from flask import Flask, render_template, request, jsonify, send_file
import os
import asyncio
import datetime
import platform
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from openai import OpenAI
import edge_tts

app = Flask(__name__)

# --- НАЛАШТУВАННЯ ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Налаштування Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Налаштування Grok
grok_client = OpenAI(
    api_key=GROK_API_KEY,
    base_url="https://api.x.ai/v1",
)

# --- ВИПРАВЛЕННЯ ДЛЯ WINDOWS (Критично для edge_tts) ---
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- ФУНКЦІЇ ---

async def save_audio(text, filename, voice):
    """Асинхронне збереження аудіо через edge-tts"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

def call_gemini(text, instruction):
    """Виклик Gemini з налаштуваннями безпеки як у термінальному коді"""
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    
    model = genai.GenerativeModel('gemini-2.0-flash', safety_settings=safety_settings)
    
    # Формуємо повний промпт
    full_prompt = f"{instruction}\n\nText to process: {text}"
    
    response = model.generate_content(full_prompt)
    return response.text.strip()

def call_grok(text, instruction):
    """Виклик Grok"""
    full_prompt = f"{instruction}\n\nText to process: {text}"
    completion = grok_client.chat.completions.create(
        model="grok-2-latest",
        messages=[
            {"role": "system", "content": "You are a creative assistant."},
            {"role": "user", "content": full_prompt}
        ]
    )
    return completion.choices[0].message.content.strip()

# --- МАРШРУТИ САЙТУ ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    text = data.get('text')
    voice = data.get('voice', 'en-US-ChristopherNeural')
    model_name = data.get('model', 'gemini-2.0-flash')
    instruction = data.get('instruction', '')

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # 1. Обробка тексту через AI
        processed_text = text # За замовчуванням
        
        if "grok" in model_name:
            if GROK_API_KEY:
                print("🤖 Використовую GROK...")
                processed_text = call_grok(text, instruction)
            else:
                return jsonify({"error": "Grok API Key missing"}), 500
        else:
            if GOOGLE_API_KEY:
                print("🤖 Використовую GEMINI...")
                processed_text = call_gemini(text, instruction)
            else:
                # Якщо ключа немає, використовуємо оригінальний текст (як у термінальному коді)
                print("⚠️ API ключ відсутній. Озвучую оригінальний текст.")
                processed_text = text

        # 2. Генерація імені файлу (Timestamp)
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}.mp3"
        
        # 3. Створення аудіо файлу
        # Використовуємо asyncio.run для виклику асинхронної функції в синхронному Flask
        asyncio.run(save_audio(processed_text, filename, voice))

        # 4. ВАЖЛИВО: Повертаємо JSON з назвою файлу (як хоче твій JS), а не сам файл
        return jsonify({"filename": filename})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Окремий маршрут для скачування файлу"""
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return str(e), 404

if __name__ == '__main__':
    app.run(debug=True)