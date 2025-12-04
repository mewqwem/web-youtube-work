import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import os
import threading
import asyncio
import datetime
import json
import requests
import time
import platform
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from openai import OpenAI
import edge_tts

# --- КОНФІГУРАЦІЯ ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY") 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
GENAIPRO_API_KEY = os.getenv("GENAIPRO_API_KEY")

GENAIPRO_BASE_URL = "https://genaipro.vn/api/v1"
GENAIPRO_TASK_URL = f"{GENAIPRO_BASE_URL}/labs/task"
GENAIPRO_VOICES_URL = f"{GENAIPRO_BASE_URL}/labs/voices" 

SETTINGS_FILE = "settings.json"

# Налаштування безпеки
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class AudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Audio Studio (Story & Rewrite)")
        self.geometry("750x850") 
        self.resizable(True, True)

        self.setup_api()
        self.saved_settings = self.load_settings()

        # === ІНТЕРФЕЙС ===
        
        self.title_label = ctk.CTkLabel(self, text="🎙️ AI Generator Studio", font=("Roboto", 24, "bold"))
        self.title_label.pack(pady=20)

        # 1. Налаштування (Модель і Голос)
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(pady=10, padx=20, fill="x")

        self.lbl_model = ctk.CTkLabel(self.settings_frame, text="AI Model:", font=("Arial", 14))
        self.lbl_model.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # ОНОВЛЕНО СПИСОК МОДЕЛЕЙ
        self.combo_model = ctk.CTkComboBox(self.settings_frame, values=["Gemini 2.5 Pro", "Gemini 2.5 Flash"], width=200)
        self.combo_model.grid(row=0, column=1, padx=10, pady=10)
        self.combo_model.set(self.saved_settings.get("model", "Gemini 2.5 Pro"))

        self.lbl_voice = ctk.CTkLabel(self.settings_frame, text="Voice:", font=("Arial", 14))
        self.lbl_voice.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        if platform.system() == "Windows":
            self.flags = {"US": "[US]", "UA": "[UA]", "DE": "[DE]", "AI": "[AI]", "VN": "[VN]"}
        else:
            self.flags = {"US": "🇺🇸", "UA": "🇺🇦", "DE": "🇩🇪", "AI": "🤖", "VN": "🇻🇳"}

        self.voices_map = {
            f"{self.flags['US']} Christopher (Edge Free)": "edge|en-US-ChristopherNeural",
            f"{self.flags['US']} Jenny (Edge Free)": "edge|en-US-JennyNeural",
            f"{self.flags['UA']} Ostap (Edge Free)": "edge|uk-UA-OstapNeural",
            f"{self.flags['DE']} Conrad (Edge Free)": "edge|de-DE-ConradNeural",
            f"{self.flags['VN']} Konrad (Germany)": "genaipro|NlRO8ABjJNJNYaRaLiPJ",
            f"{self.flags['AI']} Alloy (OpenAI)": "openai|alloy",
            f"{self.flags['DE']} Killian (Edge Free)": "edge|de-DE-KillianNeural"
        }
        
        self.combo_voice = ctk.CTkComboBox(self.settings_frame, values=list(self.voices_map.keys()), width=200)
        self.combo_voice.grid(row=1, column=1, padx=10, pady=10)
        self.restore_voice_selection()

        # 2. Назва папки/файлу
        self.file_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.file_frame.pack(pady=5, padx=20, fill="x")
        self.lbl_filename = ctk.CTkLabel(self.file_frame, text="Назва (для папки):", font=("Arial", 14, "bold"))
        self.lbl_filename.pack(side="left", padx=(0, 10))
        self.entry_filename = ctk.CTkEntry(self.file_frame, placeholder_text="Project_Name", height=35)
        self.entry_filename.pack(side="left", fill="x", expand=True)
        self.entry_filename.insert(0, self.saved_settings.get("last_filename", ""))

        # 3. ВКЛАДКИ (Tabs) для режимів
        self.tabview = ctk.CTkTabview(self, width=700, height=400)
        self.tabview.pack(pady=10, padx=20, fill="both", expand=True)

        # Вкладка 1: Story Loop
        self.tab_story = self.tabview.add("Story (Loop)")
        self.setup_story_tab()

        # Вкладка 2: Rewrite
        self.tab_rewrite = self.tabview.add("Rewrite (One-shot)")
        self.setup_rewrite_tab()

        # 4. Головна кнопка
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(pady=20, padx=20, fill="x")

        self.btn_folder = ctk.CTkButton(self.bottom_frame, text="📂", width=50, height=50, 
                                        font=("Arial", 20), fg_color="#DDDDDD", text_color="black", hover_color="#BBBBBB",
                                        command=self.select_folder)
        self.btn_folder.pack(side="right", padx=(10, 0))

        self.btn_generate = ctk.CTkButton(self.bottom_frame, text="ГЕНЕРАЦІЯ ТА ОЗВУЧКА", font=("Arial", 16, "bold"), height=50, fg_color="#0066CC", command=self.start_process)
        self.btn_generate.pack(side="left", fill="x", expand=True)

        self.lbl_status = ctk.CTkLabel(self, text="Очікування...", text_color="gray")
        self.lbl_status.pack(pady=5)
        self.progressbar = ctk.CTkProgressBar(self, mode="indeterminate")

        if GENAIPRO_API_KEY:
            threading.Thread(target=self.fetch_genaipro_voices, daemon=True).start()

    def setup_story_tab(self):
        """Елементи для вкладки створення історії"""
        lbl = ctk.CTkLabel(self.tab_story, text="Промпт для історії (з правилами Continue/END):", font=("Arial", 12))
        lbl.pack(pady=(5, 5), anchor="w")
        
        self.textbox_story = ctk.CTkTextbox(self.tab_story, height=250, font=("Arial", 12))
        self.textbox_story.pack(fill="both", expand=True, padx=5, pady=5)
        
        btn_paste = ctk.CTkButton(self.tab_story, text="Вставити", width=80, height=25, command=lambda: self.paste_to_widget(self.textbox_story))
        btn_paste.pack(pady=5, anchor="e")

    def setup_rewrite_tab(self):
        """Елементи для вкладки рерайту"""
        # Інструкція
        lbl_instr = ctk.CTkLabel(self.tab_rewrite, text="Інструкція (як переписати):", font=("Arial", 12, "bold"))
        lbl_instr.pack(pady=(5, 0), anchor="w")
        
        self.entry_instruction = ctk.CTkEntry(self.tab_rewrite, placeholder_text="Наприклад: Перепиши це в стилі Карла Юнга, зроби текст більш емоційним...", height=40)
        self.entry_instruction.pack(fill="x", padx=5, pady=5)

        # Текст
        lbl_text = ctk.CTkLabel(self.tab_rewrite, text="Текст для перепису:", font=("Arial", 12))
        lbl_text.pack(pady=(5, 0), anchor="w")

        self.textbox_rewrite = ctk.CTkTextbox(self.tab_rewrite, height=200, font=("Arial", 12))
        self.textbox_rewrite.pack(fill="both", expand=True, padx=5, pady=5)
        
        btn_paste = ctk.CTkButton(self.tab_rewrite, text="Вставити", width=80, height=25, command=lambda: self.paste_to_widget(self.textbox_rewrite))
        btn_paste.pack(pady=5, anchor="e")

    # --- ЛОГІКА ---

    def start_process(self):
        filename = self.entry_filename.get().strip()
        if not filename:
            self.lbl_status.configure(text="❌ Помилка: Вкажи назву (filename)!", text_color="red")
            return

        # Визначаємо активну вкладку
        active_tab = self.tabview.get()
        process_data = {}

        if active_tab == "Story (Loop)":
            prompt = self.textbox_story.get("1.0", "end").strip()
            if not prompt:
                self.lbl_status.configure(text="❌ Помилка: Промпт історії порожній!", text_color="red")
                return
            process_data = {"mode": "story", "prompt": prompt}

        elif active_tab == "Rewrite (One-shot)":
            instruction = self.entry_instruction.get().strip()
            source_text = self.textbox_rewrite.get("1.0", "end").strip()
            if not source_text:
                self.lbl_status.configure(text="❌ Помилка: Немає тексту для рерайту!", text_color="red")
                return
            # Інструкція може бути порожньою (тоді просто рерайт), але краще мати
            process_data = {"mode": "rewrite", "instruction": instruction, "text": source_text}

        self.save_settings()
        self.btn_generate.configure(state="disabled", text="Працюю...")
        self.progressbar.pack(pady=5, padx=50, fill="x")
        self.progressbar.start()
        
        threading.Thread(target=self.run_pipeline, args=(process_data, filename), daemon=True).start()

    def run_pipeline(self, process_data, filename):
        try:
            if platform.system() == 'Windows':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(self.async_pipeline(process_data, filename))
        except Exception as e:
            self.show_error(str(e))

    async def async_pipeline(self, data, filename):
        try:
            model_choice = self.combo_model.get()
            voice_choice = self.combo_voice.get()
            
            # --- ОНОВЛЕНИЙ ВИБІР МОДЕЛІ ---
            if "Pro" in model_choice:
                api_model = 'gemini-2.5-pro'
            else:
                api_model = 'gemini-2.5-flash'

            model = genai.GenerativeModel(api_model)
            full_story_text = ""

            # === ЛОГІКА ГЕНЕРАЦІЇ ===
            
            if data["mode"] == "rewrite":
                # РЕЖИМ РЕРАЙТУ (Один запит)
                self.update_status(f"🤖 Переписую текст...", "blue")
                
                instruction = data.get("instruction", "Rewrite this text.")
                source_text = data.get("text", "")
                
                # Формуємо єдиний промпт
                final_prompt = f"INSTRUCTION:\n{instruction}\n\nSOURCE TEXT TO REWRITE:\n{source_text}"
                
                response = model.generate_content(final_prompt, safety_settings=SAFETY_SETTINGS)
                full_story_text = response.text.strip()
                
            else:
                # РЕЖИМ ІСТОРІЇ (Loop/Цикл)
                self.update_status(f"🤖 Пишу історію (Loop)...", "blue")
                chat = model.start_chat(history=[])
                current_msg = data["prompt"]
                part_count = 0
                
                while True:
                    part_count += 1
                    self.update_status(f"🤖 Генерація частини {part_count}...", "blue")
                    
                    response = chat.send_message(current_msg, safety_settings=SAFETY_SETTINGS)
                    raw_text = response.text.strip()
                    
                    clean_text = raw_text
                    is_end = False
                    if "END" in clean_text:
                        clean_text = clean_text.replace("END", "")
                        is_end = True
                    
                    # Чистка сміття
                    clean_text = clean_text.replace("Type 'Continue' to receive the next part.", "")
                    clean_text = clean_text.replace("Type “Continue” to receive the next part.", "")
                    clean_text = clean_text.replace("Type Continue to receive the next part.", "")
                    clean_text = clean_text.replace("Type ‘Continue’ to receive the next part.", "")
                    
                    full_story_text += clean_text + "\n"
                    
                    if is_end or part_count > 40:
                        break
                    
                    current_msg = "Continue"
                    time.sleep(1)

            if not full_story_text.strip():
                raise Exception("AI повернув порожній текст.")

            # === ЗБЕРЕЖЕННЯ ТА ОЗВУЧКА (Спільне для обох режимів) ===
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            base_path = self.saved_settings.get("download_path", os.getcwd())
            folder_name = f"{filename}_{timestamp}"
            target_folder = os.path.join(base_path, folder_name)
            os.makedirs(target_folder, exist_ok=True)

            text_path = os.path.join(target_folder, "story.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(full_story_text)

            self.update_status("🎙️ Генерую аудіо...", "blue")
            audio_path = os.path.join(target_folder, "audio.mp3")
            
            voice_raw = self.voices_map[voice_choice]
            provider, voice_id = voice_raw.split("|")

            if provider == "openai":
                if not self.openai_tts_client: raise Exception("Немає OPENAI_API_KEY")
                await asyncio.to_thread(self.generate_openai, full_story_text, voice_id, audio_path)
            elif provider == "genaipro":
                if not GENAIPRO_API_KEY: raise Exception("Немає GENAIPRO_API_KEY")
                await asyncio.to_thread(self.generate_genaipro, full_story_text, voice_id, audio_path, self.update_status)
            else: # Edge
                communicate = edge_tts.Communicate(full_story_text, voice_id)
                await communicate.save(audio_path)

            self.finish_success(target_folder)

        except Exception as e:
            self.show_error(str(e))

    # --- ДОПОМІЖНІ ФУНКЦІЇ ---

    def paste_to_widget(self, widget):
        try: widget.insert("insert", self.clipboard_get())
        except: pass

    def generate_openai(self, text, voice, path):
        resp = self.openai_tts_client.audio.speech.create(model="tts-1", voice=voice, input=text)
        resp.stream_to_file(path)

    def generate_genaipro(self, text, voice, path, status_callback):
        headers = {"Authorization": f"Bearer {GENAIPRO_API_KEY}", "Content-Type": "application/json"}
        # ТУТ ДОДАНО ПАРАМЕТРИ speed І style
        data = {
            "input": text[:10000], 
            "voice_id": voice, 
            "model_id": "eleven_multilingual_v2",
            "speed": 1,
            "style": 0.5
        }
        
        r = requests.post(GENAIPRO_TASK_URL, json=data, headers=headers)
        if r.status_code != 200: raise Exception(f"GenAI Error: {r.text}")
        
        task_id = r.json().get("task_id")
        check_url = f"{GENAIPRO_TASK_URL}/{task_id}"
        
        for i in range(600): 
            time.sleep(2)
            r_check = requests.get(check_url, headers=headers)
            if r_check.status_code == 200:
                url = r_check.json().get("result")
                if url:
                    with open(path, 'wb') as f: f.write(requests.get(url).content)
                    return
        raise Exception("GenAI Timeout")

    def setup_api(self):
        if GOOGLE_API_KEY: genai.configure(api_key=GOOGLE_API_KEY)
        self.openai_tts_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    def load_settings(self):
        try: return json.load(open(SETTINGS_FILE, "r", encoding="utf-8")) if os.path.exists(SETTINGS_FILE) else {}
        except: return {}

    def save_settings(self):
        s = {"model": self.combo_model.get(), "voice": self.combo_voice.get(), 
             "download_path": self.saved_settings.get("download_path", ""), 
             "last_filename": self.entry_filename.get()}
        try: json.dump(s, open(SETTINGS_FILE, "w", encoding="utf-8"), indent=4)
        except: pass

    def restore_voice_selection(self):
        v = self.saved_settings.get("voice", "")
        if v in self.voices_map: self.combo_voice.set(v)

    def fetch_genaipro_voices(self):
        try:
            h = {"Authorization": f"Bearer {GENAIPRO_API_KEY}"}
            r = requests.get(f"{GENAIPRO_VOICES_URL}?page_size=100", headers=h)
            if r.status_code == 200:
                voices = r.json().get("voices", [])
                for v in voices:
                    label = f"{self.flags['VN']} {v.get('name')} (GenAI)"
                    self.voices_map[label] = f"genaipro|{v.get('voice_id')}"
                self.after(0, lambda: self.combo_voice.configure(values=list(self.voices_map.keys())))
        except: pass

    def select_folder(self):
        f = filedialog.askdirectory()
        if f: self.saved_settings["download_path"] = f; self.save_settings()

    def update_status(self, m, c): 
        self.after(0, lambda: self.lbl_status.configure(text=m, text_color=c))

    def finish_success(self, folder):
        def _u():
            self.progressbar.stop()
            self.progressbar.pack_forget()
            self.btn_generate.configure(state="normal", text="ГЕНЕРАЦІЯ ТА ОЗВУЧКА")
            self.lbl_status.configure(text="✅ Готово! Файли збережено.", text_color="green")
            self.open_folder(folder)
        self.after(0, _u)

    def show_error(self, m):
        def _u():
            self.progressbar.stop()
            self.progressbar.pack_forget()
            self.btn_generate.configure(state="normal", text="ГЕНЕРАЦІЯ ТА ОЗВУЧКА")
            self.lbl_status.configure(text=f"❌ Помилка: {m}", text_color="red")
        self.after(0, _u)

    def open_folder(self, p):
        if platform.system() == "Windows": os.startfile(p)
        elif platform.system() == "Darwin": os.system(f"open {p}")
        else: os.system(f"xdg-open {p}")

if __name__ == "__main__":
    app = AudioApp()
    app.mainloop()