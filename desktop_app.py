import customtkinter as ctk
import tkinter as tk
import os
import threading
import asyncio
import uuid
import sys
import platform
import json  # Бібліотека для роботи з JSON
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
import edge_tts

# --- НАЛАШТУВАННЯ ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
SETTINGS_FILE = "settings.json"  # Файл для збереження налаштувань

# Налаштування вигляду
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Налаштування вікна
        self.title("AI Audio Studio")
        self.geometry("750x750") # Трошки збільшив висоту
        self.resizable(False, False)

        self.setup_api()

        # Завантажуємо збережені налаштування або дефолтні
        self.saved_settings = self.load_settings()

        # === ІНТЕРФЕЙС ===
        
        # 1. Заголовок
        self.title_label = ctk.CTkLabel(self, text="🎙️ AI Audio Generator", font=("Roboto", 24, "bold"))
        self.title_label.pack(pady=20)

        # 2. Блок налаштувань (Модель, Голос, Режим)
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(pady=10, padx=20, fill="x")

        # -- Рядок 1: Модель та Голос --
        self.lbl_model = ctk.CTkLabel(self.settings_frame, text="Модель ШІ:", font=("Arial", 14))
        self.lbl_model.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.combo_model = ctk.CTkComboBox(self.settings_frame, values=["Gemini 2.0 Flash", "Grok 2 (xAI)"], width=200)
        self.combo_model.grid(row=0, column=1, padx=10, pady=10)
        self.combo_model.set(self.saved_settings.get("model", "Gemini 2.0 Flash"))

        self.lbl_voice = ctk.CTkLabel(self.settings_frame, text="Голос:", font=("Arial", 14))
        self.lbl_voice.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        self.voices_map = {
            "🇺🇸 Christopher (Male)": "en-US-ChristopherNeural",
            "🇺🇸 Jenny (Female)": "en-US-JennyNeural",
            "🇺🇦 Остап (Чол)": "uk-UA-OstapNeural",
            "🇺🇦 Поліна (Жін)": "uk-UA-PolinaNeural",
            "🇩🇪 Christoph (Male)": "de-DE-ChristophNeural",
            "🇵🇱 Marek (Male)": "pl-PL-MarekNeural"
        }
        self.combo_voice = ctk.CTkComboBox(self.settings_frame, values=list(self.voices_map.keys()), width=200)
        self.combo_voice.grid(row=1, column=1, padx=10, pady=10)
        saved_voice = self.saved_settings.get("voice", "🇺🇸 Christopher (Male)")
        self.combo_voice.set(saved_voice if saved_voice in self.voices_map else list(self.voices_map.keys())[0])

        # -- Рядок 2: Перемикач режимів --
        self.lbl_mode = ctk.CTkLabel(self.settings_frame, text="Режим:", font=("Arial", 14, "bold"))
        self.lbl_mode.grid(row=2, column=0, padx=10, pady=15, sticky="w")

        self.mode_switch = ctk.CTkSegmentedButton(self.settings_frame, values=["Реврайт тексту", "Створення з нуля"],
                                                  command=self.change_mode)
        self.mode_switch.grid(row=2, column=1, padx=10, pady=15, sticky="ew")
        self.mode_switch.set("Реврайт тексту") # Дефолт

        # -- Рядок 3: Інструкція (Тільки для Реврайту) --
        self.instr_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.instr_frame.grid(row=3, column=0, columnspan=3, sticky="ew")

        self.lbl_instr = ctk.CTkLabel(self.instr_frame, text="Інструкція:", font=("Arial", 14))
        self.lbl_instr.grid(row=0, column=0, padx=10, pady=5, sticky="nw") 
        
        self.entry_instr = ctk.CTkTextbox(self.instr_frame, height=60, width=350, font=("Arial", 12))
        self.entry_instr.grid(row=0, column=1, padx=10, pady=5)
        self.entry_instr.insert("1.0", self.saved_settings.get("instruction", "Translate to English and improve style."))

        self.btn_paste_instr = ctk.CTkButton(self.instr_frame, text="Вставити", width=60, height=25, 
                                             command=lambda: self.paste_to_widget(self.entry_instr))
        self.btn_paste_instr.grid(row=0, column=2, padx=5, pady=5, sticky="n")

        # 3. Головне поле для тексту
        self.text_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.text_header_frame.pack(pady=(10, 5), padx=20, fill="x")

        self.lbl_text = ctk.CTkLabel(self.text_header_frame, text="Ваш текст:", font=("Arial", 14, "bold"))
        self.lbl_text.pack(side="left")

        # Кнопки керування текстом
        self.btn_paste_text = ctk.CTkButton(self.text_header_frame, text="Вставити", width=100, height=25, 
                                            command=lambda: self.paste_to_widget(self.textbox))
        self.btn_paste_text.pack(side="right", padx=5)

        self.btn_clear_text = ctk.CTkButton(self.text_header_frame, text="Очистити", width=100, height=25,
                                            fg_color="#555555", hover_color="#333333",
                                            command=self.clear_textbox)
        self.btn_clear_text.pack(side="right", padx=5)

        self.textbox = ctk.CTkTextbox(self, height=200, font=("Arial", 14))
        self.textbox.pack(pady=5, padx=20, fill="x")

        # Контекстне меню
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Вставити (Paste)", command=self.paste_text_menu)
        self.context_menu.add_command(label="Копіювати (Copy)", command=self.copy_text_menu)
        self.context_menu.add_command(label="Вирізати (Cut)", command=self.cut_text_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Очистити все", command=self.clear_text_menu)

        self.setup_text_bindings(self.textbox)
        self.setup_text_bindings(self.entry_instr)
        self.active_widget = None

        # 4. Кнопка генерації
        self.btn_generate = ctk.CTkButton(self, text="Створити Аудіо", font=("Arial", 16, "bold"), height=50, command=self.start_generation)
        self.btn_generate.pack(pady=20, padx=20, fill="x")

        self.lbl_status = ctk.CTkLabel(self, text="Готовий до роботи", text_color="gray")
        self.lbl_status.pack(pady=5)

        self.progressbar = ctk.CTkProgressBar(self, mode="indeterminate")
        self.last_file = None

    # --- ЛОГІКА ІНТЕРФЕЙСУ ---
    def change_mode(self, value):
        """Змінює вигляд інтерфейсу залежно від обраного режиму"""
        if value == "Реврайт тексту":
            # Показуємо поле інструкції
            self.instr_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
            self.lbl_text.configure(text="Ваш текст (для обробки):")
            self.entry_instr.configure(state="normal")
        else:
            # Ховаємо поле інструкції, бо воно не потрібне
            self.instr_frame.grid_forget()
            self.lbl_text.configure(text="Ваш промпт (тема, ідея):")
            
    def clear_textbox(self):
        self.textbox.delete("1.0", "end")

    # --- ЛОГІКА ЗБЕРЕЖЕННЯ ---
    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Помилка завантаження налаштувань: {e}")
        return {} 

    def save_settings(self):
        settings = {
            "model": self.combo_model.get(),
            "voice": self.combo_voice.get(),
            "instruction": self.entry_instr.get("1.0", "end").strip()
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Помилка збереження налаштувань: {e}")

    # --- ЛОГІКА ШОРТКАТІВ ТА МЕНЮ ---
    def setup_text_bindings(self, widget):
        widget.bind("<Button-3>", lambda event: self.show_context_menu(event, widget))
        widget.bind("<Button-2>", lambda event: self.show_context_menu(event, widget))
        widget.bind("<Control-v>", lambda event: self.handle_paste(event, widget))
        widget.bind("<Control-c>", lambda event: self.handle_copy(event, widget))
        widget.bind("<Control-x>", lambda event: self.handle_cut(event, widget))

    def show_context_menu(self, event, target_widget):
        self.active_widget = target_widget
        try: self.context_menu.tk_popup(event.x_root, event.y_root)
        finally: self.context_menu.grab_release()

    def paste_to_widget(self, widget):
        try: widget.insert("insert", self.clipboard_get())
        except: pass

    def handle_paste(self, event, widget):
        try:
            widget.insert("insert", self.clipboard_get())
            return "break"
        except: pass

    def handle_copy(self, event, widget):
        try:
            self.clipboard_clear()
            self.clipboard_append(widget.get("sel.first", "sel.last"))
            return "break"
        except: pass

    def handle_cut(self, event, widget):
        try:
            self.handle_copy(event, widget)
            widget.delete("sel.first", "sel.last")
            return "break"
        except: pass

    def paste_text_menu(self):
        if self.active_widget: self.paste_to_widget(self.active_widget)
    def copy_text_menu(self):
        if self.active_widget: self.handle_copy(None, self.active_widget)
    def cut_text_menu(self):
        if self.active_widget: self.handle_cut(None, self.active_widget)
    def clear_text_menu(self):
        if self.active_widget: self.active_widget.delete("1.0", "end")

    # --- ЛОГІКА ШІ ---
    def setup_api(self):
        if GOOGLE_API_KEY:
            try: genai.configure(api_key=GOOGLE_API_KEY)
            except: pass
        self.grok_client = None
        if GROK_API_KEY:
            try: self.grok_client = OpenAI(api_key=GROK_API_KEY, base_url="https://api.x.ai/v1")
            except: pass

    def start_generation(self):
        main_input = self.textbox.get("1.0", "end").strip()
        if not main_input:
            self.lbl_status.configure(text="❌ Помилка: Поле тексту порожнє!", text_color="red")
            return
        
        self.save_settings()

        self.btn_generate.configure(state="disabled", text="Генерація...")
        self.progressbar.pack(pady=5, padx=50, fill="x")
        self.progressbar.start()
        self.lbl_status.configure(text="⏳ ШІ працює...", text_color="orange")

        threading.Thread(target=self.run_async_process, args=(main_input,), daemon=True).start()

    def run_async_process(self, input_text):
        try:
            if platform.system() == 'Windows':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            asyncio.run(self.process_and_generate(input_text))
        except Exception as e:
            self.show_error(str(e))

    async def process_and_generate(self, input_text):
        try:
            model_choice = self.combo_model.get()
            voice_code = self.voices_map[self.combo_voice.get()]
            mode = self.mode_switch.get()
            
            # Логіка формування запиту залежно від режиму
            if mode == "Реврайт тексту":
                instruction = self.entry_instr.get("1.0", "end").strip()
                final_user_prompt = f"User Instruction: {instruction}\n\nText to process: {input_text}"
            else: # Створення з нуля
                final_user_prompt = f"User Request/Topic: {input_text}"

            processed_text = input_text # Запасний варіант
            
            if "Gemini" in model_choice and GOOGLE_API_KEY:
                self.update_status("🤖 Gemini думає...", "cyan")
                processed_text = self.call_gemini(final_user_prompt) or input_text
            elif "Grok" in model_choice and self.grok_client:
                self.update_status("🤖 Grok думає...", "cyan")
                processed_text = self.call_grok(final_user_prompt) or input_text

            self.update_status(f"🎙️ Озвучую ({len(processed_text)} симв.)...", "cyan")

            filename = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            communicate = edge_tts.Communicate(processed_text, voice_code)
            await communicate.save(filename)

            self.finish_success(filename)
        except Exception as e:
            self.show_error(str(e))

    def call_gemini(self, prompt):
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            # СИСТЕМНИЙ ПРОМПТ (для обох режимів)
            hidden_system_prompt = (
                "STRICT SYSTEM INSTRUCTION: Output ONLY the final text content. "
                "Do NOT include any conversational filler, introductions (like 'Here is the story', 'Sure'), "
                "or concluding remarks. Just the raw text to be spoken."
            )
            full_prompt = f"{hidden_system_prompt}\n\n{prompt}"
            response = model.generate_content(full_prompt)
            return response.text.strip()
        except: return None

    def call_grok(self, prompt):
        try:
            hidden_system_prompt = (
                "STRICT SYSTEM INSTRUCTION: Output ONLY the final text content. "
                "Do NOT include any conversational filler, introductions, or concluding remarks. "
                "Just the raw text to be spoken."
            )
            completion = self.grok_client.chat.completions.create(
                model="grok-2-latest",
                messages=[
                    {"role": "system", "content": hidden_system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            return completion.choices[0].message.content.strip()
        except: return None

    def update_status(self, message, color):
        self.after(0, lambda: self.lbl_status.configure(text=message, text_color=color))

    def finish_success(self, filename):
        def _update():
            self.progressbar.stop()
            self.progressbar.pack_forget()
            self.btn_generate.configure(state="normal", text="Створити Аудіо")
            self.lbl_status.configure(text=f"✅ Готово! Збережено: {filename}", text_color="#00ff00")
            self.open_file(filename)
        self.after(0, _update)

    def show_error(self, message):
        def _update():
            self.progressbar.stop()
            self.progressbar.pack_forget()
            self.btn_generate.configure(state="normal", text="Створити Аудіо")
            self.lbl_status.configure(text=f"❌ Помилка: {message}", text_color="red")
        self.after(0, _update)

    def open_file(self, filename):
        if platform.system() == "Windows": os.startfile(filename)
        elif platform.system() == "Darwin": os.system(f"open {filename}")
        else: os.system(f"xdg-open {filename}")

if __name__ == "__main__":
    app = AudioApp()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\nПрограма зупинена користувачем.")
        try:
            app.destroy()
        except:
            pass