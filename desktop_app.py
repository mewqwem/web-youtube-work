import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import os
import threading
import asyncio
import uuid
import sys
import platform
import json
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
import edge_tts

# --- CONFIGURATION ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROK_API_KEY = os.getenv("GROK_API_KEY")
SETTINGS_FILE = "settings.json"

# Appearance settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window setup
        self.title("AI Audio Studio (English Version)")
        self.geometry("750x780") 
        self.resizable(True, True)

        self.setup_api()
        self.saved_settings = self.load_settings()

        # === INTERFACE ===
        
        # 1. Header
        self.title_label = ctk.CTkLabel(self, text="🎙️ AI Audio Generator", font=("Roboto", 24, "bold"))
        self.title_label.pack(pady=20)

        # 2. Settings Block
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.pack(pady=10, padx=20, fill="x")

        # AI Model
        self.lbl_model = ctk.CTkLabel(self.settings_frame, text="AI Model:", font=("Arial", 14))
        self.lbl_model.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.combo_model = ctk.CTkComboBox(self.settings_frame, values=["Gemini 2.0 Flash", "Grok 2 (xAI)"], width=200)
        self.combo_model.grid(row=0, column=1, padx=10, pady=10)
        self.combo_model.set(self.saved_settings.get("model", "Gemini 2.0 Flash"))

        # Voice
        self.lbl_voice = ctk.CTkLabel(self.settings_frame, text="Voice:", font=("Arial", 14))
        self.lbl_voice.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        # Windows Flag Fix (Windows doesn't support flag emojis well)
        if platform.system() == "Windows":
            flags = {"US": "[US]", "UA": "[UA]", "DE": "[DE]", "PL": "[PL]"}
        else:
            flags = {"US": "🇺🇸", "UA": "🇺🇦", "DE": "🇩🇪", "PL": "🇵🇱"}

        self.voices_map = {
            f"{flags['US']} Christopher (Male)": "en-US-ChristopherNeural",
            f"{flags['US']} Jenny (Female)": "en-US-JennyNeural",
            f"{flags['UA']} Ostap (Male)": "uk-UA-OstapNeural",
            f"{flags['UA']} Polina (Female)": "uk-UA-PolinaNeural",
            f"{flags['DE']} Christoph (Male)": "de-DE-ChristophNeural",
            f"{flags['PL']} Marek (Male)": "pl-PL-MarekNeural"
        }
        self.combo_voice = ctk.CTkComboBox(self.settings_frame, values=list(self.voices_map.keys()), width=200)
        self.combo_voice.grid(row=1, column=1, padx=10, pady=10)
        
        # Restore saved voice or default
        saved_voice = self.saved_settings.get("voice", "")
        if saved_voice in self.voices_map:
            self.combo_voice.set(saved_voice)
        else:
            self.combo_voice.set(list(self.voices_map.keys())[0])

        # Mode
        self.lbl_mode = ctk.CTkLabel(self.settings_frame, text="Mode:", font=("Arial", 14, "bold"))
        self.lbl_mode.grid(row=2, column=0, padx=10, pady=15, sticky="w")

        self.mode_switch = ctk.CTkSegmentedButton(self.settings_frame, values=["Text Rewrite", "Create from Scratch"],
                                                                    command=self.change_mode)
        self.mode_switch.grid(row=2, column=1, padx=10, pady=15, sticky="ew")
        self.mode_switch.set("Text Rewrite")

        # Instruction Frame
        self.instr_frame = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.instr_frame.grid(row=3, column=0, columnspan=3, sticky="ew")

        self.lbl_instr = ctk.CTkLabel(self.instr_frame, text="Instruction:", font=("Arial", 14))
        self.lbl_instr.grid(row=0, column=0, padx=10, pady=5, sticky="nw") 
        
        self.entry_instr = ctk.CTkTextbox(self.instr_frame, height=60, width=350, font=("Arial", 12))
        self.entry_instr.grid(row=0, column=1, padx=10, pady=5)
        self.entry_instr.insert("1.0", self.saved_settings.get("instruction", "Translate to English and improve style."))

        self.btn_paste_instr = ctk.CTkButton(self.instr_frame, text="Paste", width=60, height=25, 
                                                             command=lambda: self.paste_to_widget(self.entry_instr))
        self.btn_paste_instr.grid(row=0, column=2, padx=5, pady=5, sticky="n")

        # 3. Main Text Field
        self.text_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.text_header_frame.pack(pady=(10, 5), padx=20, fill="x")

        self.lbl_text = ctk.CTkLabel(self.text_header_frame, text="Your Text:", font=("Arial", 14, "bold"))
        self.lbl_text.pack(side="left")

        # Text Control Buttons
        self.btn_paste_text = ctk.CTkButton(self.text_header_frame, text="Paste", width=100, height=25, 
                                                            command=lambda: self.paste_to_widget(self.textbox))
        self.btn_paste_text.pack(side="right", padx=5)

        self.btn_clear_text = ctk.CTkButton(self.text_header_frame, text="Clear", width=100, height=25,
                                                            fg_color="#555555", hover_color="#333333",
                                                            command=self.clear_textbox)
        self.btn_clear_text.pack(side="right", padx=5)

        self.textbox = ctk.CTkTextbox(self, height=200, font=("Arial", 14))
        self.textbox.pack(pady=5, padx=20, fill="both", expand=True)

        # Context Menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Paste", command=self.paste_text_menu)
        self.context_menu.add_command(label="Copy", command=self.copy_text_menu)
        self.context_menu.add_command(label="Cut", command=self.cut_text_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Clear All", command=self.clear_text_menu)

        self.setup_text_bindings(self.textbox)
        self.setup_text_bindings(self.entry_instr)
        self.active_widget = None

        # 4. Action Buttons
        self.buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttons_frame.pack(pady=20, padx=20, fill="x")

        # Folder selection button
        self.btn_folder = ctk.CTkButton(self.buttons_frame, text="📂", width=50, height=50, 
                                        font=("Arial", 20), fg_color="#444444", hover_color="#555555",
                                        command=self.select_folder)
        self.btn_folder.pack(side="right", padx=(10, 0))

        # Generate Button
        self.btn_generate = ctk.CTkButton(self.buttons_frame, text="Generate Audio", font=("Arial", 16, "bold"), height=50, command=self.start_generation)
        self.btn_generate.pack(side="left", fill="x", expand=True)

        self.lbl_status = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.lbl_status.pack(pady=5)

        self.progressbar = ctk.CTkProgressBar(self, mode="indeterminate")

        # Show current folder
        current_path = self.saved_settings.get("download_path", "")
        if current_path:
            self.lbl_status.configure(text=f"📂 Folder: {current_path}", text_color="gray")

    # --- FOLDER SELECTION ---
    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.saved_settings["download_path"] = folder_selected
            self.save_settings()
            self.lbl_status.configure(text=f"📂 Folder changed: {folder_selected}", text_color="#00ff00")

    # --- INTERFACE LOGIC ---
    def change_mode(self, value):
        if value == "Text Rewrite":
            self.instr_frame.grid(row=3, column=0, columnspan=3, sticky="ew")
            self.lbl_text.configure(text="Your text (to process):")
            self.entry_instr.configure(state="normal")
        else:
            self.instr_frame.grid_forget()
            self.lbl_text.configure(text="Your prompt (topic, idea):")
            
    def clear_textbox(self):
        self.textbox.delete("1.0", "end")

    # --- SETTINGS LOGIC ---
    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except: pass
        return {} 

    def save_settings(self):
        settings = {
            "model": self.combo_model.get(),
            "voice": self.combo_voice.get(),
            "instruction": self.entry_instr.get("1.0", "end").strip(),
            "download_path": self.saved_settings.get("download_path", "")
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except: pass

    # --- SHORTCUTS LOGIC ---
    def setup_text_bindings(self, widget):
        widget.bind("<Button-3>", lambda event: self.show_context_menu(event, widget))
        widget.bind("<Button-2>", lambda event: self.show_context_menu(event, widget))
        
        if platform.system() == "Darwin": modifier = "Command"
        else: modifier = "Control"

        widget.bind(f"<{modifier}-v>", lambda event: self.handle_paste(event, widget))
        widget.bind(f"<{modifier}-c>", lambda event: self.handle_copy(event, widget))
        widget.bind(f"<{modifier}-x>", lambda event: self.handle_cut(event, widget))

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

    # --- AI LOGIC ---
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
            self.lbl_status.configure(text="❌ Error: Text field is empty!", text_color="red")
            return
        
        self.save_settings()
        self.btn_generate.configure(state="disabled", text="Generating...")
        self.progressbar.pack(pady=5, padx=50, fill="x")
        self.progressbar.start()
        self.lbl_status.configure(text="⏳ AI is working...", text_color="orange")

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
            
            final_audio_text = ""

            if mode == "Text Rewrite":
                instruction = self.entry_instr.get("1.0", "end").strip()
                final_user_prompt = f"User Instruction: {instruction}\n\nText to process: {input_text}"
                
                if "Gemini" in model_choice:
                    self.update_status("🤖 Gemini thinking...", "cyan")
                    final_audio_text = self.call_gemini_oneshot(final_user_prompt) or input_text
                elif "Grok" in model_choice:
                    self.update_status("🤖 Grok thinking...", "cyan")
                    final_audio_text = self.call_grok_oneshot(final_user_prompt) or input_text
            
            else: 
                if "Gemini" in model_choice:
                    final_audio_text = self.process_long_generation_gemini(input_text)
                elif "Grok" in model_choice:
                    final_audio_text = self.process_long_generation_grok(input_text)
                
                if not final_audio_text:
                    raise Exception("API returned no text (Possible SSL issue).")

            self.update_status(f"🎙️ Voicing ({len(final_audio_text)} chars)...", "cyan")

            # GENERATE FILE PATH
            filename = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
            
            download_path = self.saved_settings.get("download_path", "")
            if download_path and os.path.exists(download_path):
                full_path = os.path.join(download_path, filename)
            else:
                full_path = filename

            communicate = edge_tts.Communicate(final_audio_text, voice_code)
            await communicate.save(full_path)

            self.finish_success(full_path)
        except Exception as e:
            self.show_error(str(e))

    # --- API METHODS ---
    def call_gemini_oneshot(self, prompt):
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Gemini Error: {e}")
            return None

    def call_grok_oneshot(self, prompt):
        try:
            completion = self.grok_client.chat.completions.create(
                model="grok-2-latest",
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"Grok Error: {e}")
            return None

    def process_long_generation_gemini(self, initial_prompt):
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            chat = model.start_chat(history=[])
            full_audio_text = ""
            current_prompt = initial_prompt
            
            for i in range(15):
                self.update_status(f"🤖 Gemini writing part {i+1}...", "cyan")
                response = chat.send_message(current_prompt)
                raw_text = response.text
                
                if "Type ‘Continue’" not in raw_text and "END" not in raw_text:
                     full_audio_text += raw_text + " "

                if "END" in raw_text: break
                current_prompt = "Continue"
            return full_audio_text
        except Exception as e:
            raise Exception(f"Gemini Error: {e}")

    def process_long_generation_grok(self, initial_prompt):
        return self.call_grok_oneshot(initial_prompt)

    def update_status(self, message, color):
        self.after(0, lambda: self.lbl_status.configure(text=message, text_color=color))

    def finish_success(self, filename):
        def _update():
            self.progressbar.stop()
            self.progressbar.pack_forget()
            self.btn_generate.configure(state="normal", text="Generate Audio")
            self.lbl_status.configure(text=f"✅ Done! Saved: {filename}", text_color="#00ff00")
            self.open_file(filename)
        self.after(0, _update)

    def show_error(self, message):
        def _update():
            self.progressbar.stop()
            self.progressbar.pack_forget()
            self.btn_generate.configure(state="normal", text="Generate Audio")
            self.lbl_status.configure(text=f"❌ Error: {message}", text_color="red")
        self.after(0, _update)

    def open_file(self, filename):
        if platform.system() == "Windows": os.startfile(filename)
        elif platform.system() == "Darwin": os.system(f"open {filename}")
        else: os.system(f"xdg-open {filename}")

if __name__ == "__main__":
    app = AudioApp()
    app.mainloop()