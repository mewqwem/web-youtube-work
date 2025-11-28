from flask import Flask, render_template, request, jsonify, send_file
import os
import asyncio
import datetime
import uuid
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
import edge_tts
import platform

app = Flask(__name__)

# --- НАЛАШТУВАННЯ ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Налаштування Gemini (якщо є ключ)
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        print("✅ Gemini налаштовано.")
    except Exception as e:
        print(f"⚠️ Помилка налаштування Gemini: {e}")

# Виправлення для Windows (щоб не зависало локально)
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- ФУНКЦІЇ ---

async def save_audio(text, filename, voice):
    """Зберігає аудіо через потік (Stream) — це найнадійніший метод для Render."""
    if not text or not text.strip():
        print("❌ ПОМИЛКА: Текст для озвучки пустий!")
        raise ValueError("Text cannot be empty for TTS generation.")
    
    print(f"🎙️ Починаю генерацію аудіо (перші 50 симв.): {text[:50]}...")
    
    # 🔄 МЕХАНІЗМ ПОВТОРНИХ СПРОБ (3 рази)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice)
            
            # ВІДКРИВАЄМО ФАЙЛ І ЗАПИСУЄМО ПОТОКОМ (Chunk-by-chunk)
            # Це надійніше, ніж communicate.save(), бо ми контролюємо процес
            received_data = False
            with open(filename, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                        received_data = True
            
            if not received_data:
                raise Exception("Microsoft не надіслав жодних даних (пустий потік).")
                
            print(f"✅ Аудіо успішно збережено: {filename}")
            return # Успіх
            
        except Exception as e:
            print(f"⚠️ Помилка генерації (Спроба {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1.5) # Чекаємо трохи довше
            else:
                print("❌ Всі спроби вичерпано.")
                raise e

def call_gemini(text, instruction):
    """Викликає Gemini API."""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        full_prompt = f"{instruction}\n\nText: {text}"
        response = model.generate_content(full_prompt)
        
        if not response.parts:
            print("⚠️ Gemini повернув порожню відповідь (можливо, фільтри безпеки).")
            return None
            
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ Помилка виклику Gemini: {e}")
        return None

# --- МАРШРУТИ ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    print("\n--- НОВИЙ ЗАПИТ ---")
    data = request.json
    text = data.get('text')
    voice = data.get('voice', 'en-US-ChristopherNeural')
    model_name = data.get('model', 'gemini-2.0-flash')
    instruction = data.get('instruction', '')

    if not text:
        return jsonify({"error": "Введіть текст!"}), 400

    print(f"📥 Отримано текст: {text[:30]}...")
    print(f"🤖 Модель: {model_name}, Голос: {voice}")

    # 1. Логіка обробки тексту
    processed_text = text  # За замовчуванням беремо оригінал
    
    # Спробуємо використати ШІ тільки якщо вибрано Gemini і є ключ
    if "gemini" in model_name:
        if GOOGLE_API_KEY:
            ai_result = call_gemini(text, instruction)
            if ai_result:
                processed_text = ai_result
                print("✨ Текст успішно оброблено через ШІ.")
            else:
                print("⚠️ ШІ не спрацював, використовуємо оригінальний текст.")
        else:
            print("⚠️ Немає ключа GOOGLE_API_KEY, пропускаємо ШІ.")

    # 2. ФІНАЛЬНА СТРАХОВКА
    # Якщо processed_text раптом став None або пустим — вертаємо оригінал
    if not processed_text or not processed_text.strip():
        print("⚠️ Увага! Оброблений текст пустий. Відкат до оригіналу.")
        processed_text = text

    # Якщо і оригінал був пустим (хоча перевірка вище це ловить), ставимо заглушку
    if not processed_text or not processed_text.strip():
        processed_text = "System error. No text provided."

    try:
        # 3. Генерація файлу
        filename = f"audio_{uuid.uuid4()}.mp3"
        
        # Виклик асинхронної функції
        asyncio.run(save_audio(processed_text, filename, voice))

        return jsonify({"filename": filename})

    except Exception as e:
        print(f"🔥 КРИТИЧНА ПОМИЛКА: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return str(e), 404

if __name__ == '__main__':
    app.run(debug=True)