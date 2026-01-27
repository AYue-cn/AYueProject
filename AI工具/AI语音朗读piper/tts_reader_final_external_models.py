# tts_reader_final_external_models.py
# 支持 piper 最新 API + SynthesisConfig 多参数调节
# 参数：length_scale, volume, noise_scale, noise_w_scale, normalize_audio 全部放到界面上可调

import os
import json
import threading
import queue
import time
import sys
import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter import ttk  # 显式导入tkinter的ttk，确保LabelFrame可用
import ttkbootstrap as ttkbs  # 重命名，避免和tkinter.ttk冲突
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText
from tkinter import filedialog, messagebox, StringVar, IntVar, DoubleVar, BooleanVar
from pathlib import Path
import wave
import tempfile
from piper import PiperVoice, SynthesisConfig


# ========== SoundDevice初始化 ==========
try:
    sd._initialize()
    sd.default.samplerate = 22050
    sd.default.channels = 1
except Exception as e:
    print(f"SoundDevice初始化提示: {e}")

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_piper_voices_dir():
    return os.path.join(get_base_dir(), "piper-voices")

class TTSApp(ttkbs.Window):  # 使用ttkbootstrap的Window，但控件用tkinter.ttk
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("阿岳TTS 阅读器 v1.2")
        self.geometry("615x650")  # 优化初始窗口尺寸
        self.minsize(615, 650)    # 设置最小尺寸
        self.resizable(True, True)

        self.sentences = []
        self.current_json_path = None
        self.current_index = 0
        self.task_queue = queue.Queue()
        self.is_running = False
        self.voice = None
        self.voice_models = []
        self.selected_model_path = None

        self.pause_var = IntVar(value=300)
        self.state_file = os.path.join(get_base_dir(), "playback_state.json")

        # SynthesisConfig 可调参数（全部放到界面）
        self.length_scale_var   = DoubleVar(value=0.90)
        self.volume_var         = DoubleVar(value=1.00)
        self.noise_scale_var    = DoubleVar(value=0.667)
        self.noise_w_scale_var  = DoubleVar(value=0.800)
        self.normalize_audio_var = BooleanVar(value=True)

        self.ui_queue = queue.Queue()
        self.process_ui_queue()

        self.load_voice_models()
        self.create_main_interface()  # 优化后的布局
        self.check_resume()

    def process_ui_queue(self):
        while not self.ui_queue.empty():
            task = self.ui_queue.get()
            if task[0] == "log":
                self._safe_log(task[1])
            elif task[0] == "update_progress":
                self.progress_label.configure(text=task[1])
            elif task[0] == "finish":
                self.stop_reading()
                messagebox.showinfo("完成", "所有内容朗读完毕")
        self.after(10, self.process_ui_queue)

    def _safe_log(self, msg):
        self.log_text.text.configure(state="normal")
        tag = "error" if "错误" in msg or "失败" in msg else None
        self.log_text.text.insert("end", msg + "\n", tag)
        self.log_text.text.see("end")
        self.log_text.text.configure(state="disabled")

    def log(self, msg):
        self.ui_queue.put(("log", msg))

    def update_progress(self, text):
        self.ui_queue.put(("update_progress", text))

    def load_voice_models(self):
        model_dir = get_piper_voices_dir()
        if not os.path.exists(model_dir):
            messagebox.showerror("错误", f"piper-voices 文件夹不存在！\n路径: {model_dir}")
            return
        self.voice_models = [f for f in os.listdir(model_dir) if f.endswith('.onnx')]
        if not self.voice_models:
            messagebox.showwarning("警告", f"piper-voices 文件夹中没有找到 .onnx 模型。")

    def create_main_interface(self):
        """创建优化后的主界面 - 紧凑布局"""
        main_frame = ttk.Frame(self, padding=10)  # 使用tkinter.ttk的Frame
        main_frame.pack(fill="both", expand=True)

        # ========== 第一部分：文件和模型选择（网格布局） ==========
        # 改用tkinter.ttk的LabelFrame，解决属性不存在问题
        top_frame = ttk.LabelFrame(main_frame, text="基础设置", padding=8)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        top_frame.grid_columnconfigure(1, weight=1)

        # JSON文件选择
        ttk.Label(top_frame, text="JSON文件：", width=10).grid(row=0, column=0, sticky="w", padx=(0, 5))
        # 修复：直接使用ttkbootstrap的Label，自带Secondary样式，无需手动查询
        self.file_label = ttkbs.Label(top_frame, text="未选择", bootstyle=SECONDARY)
        self.file_label.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        # 按钮使用ttkbootstrap的样式
        select_btn = ttkbs.Button(top_frame, text="选择", command=self.select_json_file, bootstyle=SUCCESS, width=8)
        select_btn.grid(row=0, column=2)

        # 声音模型选择
        ttk.Label(top_frame, text="语音模型：", width=10).grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.model_combo = ttkbs.Combobox(top_frame, values=self.voice_models, bootstyle=INFO)
        self.model_combo.grid(row=1, column=1, sticky="ew", padx=(0, 5), pady=(5, 0))
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_select)

        # ========== 第二部分：控制参数（两列布局） ==========
        param_frame = ttk.LabelFrame(main_frame, text="语音参数调节", padding=8)
        param_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        param_frame.grid_columnconfigure(1, weight=1)
        param_frame.grid_columnconfigure(4, weight=1)

        # 左列参数
        # 句子暂停
        ttk.Label(param_frame, text="句间暂停(ms)：").grid(row=0, column=0, sticky="w", padx=(0, 5))
        pause_scale = ttk.Scale(param_frame, from_=0, to=1500, orient="horizontal",
                               variable=self.pause_var, command=self._on_pause_change)
        pause_scale.grid(row=0, column=1, sticky="ew", padx=(0, 15))
        self.pause_label = ttk.Label(param_frame, text="300 ms", width=8)
        self.pause_label.grid(row=0, column=2, sticky="w")

        # 语速
        ttk.Label(param_frame, text="语速：").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        length_scale = ttk.Scale(param_frame, from_=0.5, to=2.0, orient="horizontal",
                                variable=self.length_scale_var)
        length_scale.grid(row=1, column=1, sticky="ew", padx=(0, 15), pady=(5, 0))
        self.length_label = ttk.Label(param_frame, text="0.90", width=8)
        self.length_label.grid(row=1, column=2, sticky="w", pady=(5, 0))
        self.length_scale_var.trace("w", lambda *args: self.length_label.configure(text=f"{self.length_scale_var.get():.2f}"))

        # 音量
        ttk.Label(param_frame, text="音量：").grid(row=2, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        volume_scale = ttk.Scale(param_frame, from_=0.1, to=2.0, orient="horizontal",
                                variable=self.volume_var)
        volume_scale.grid(row=2, column=1, sticky="ew", padx=(0, 15), pady=(5, 0))
        self.volume_label = ttk.Label(param_frame, text="1.00", width=8)
        self.volume_label.grid(row=2, column=2, sticky="w", pady=(5, 0))
        self.volume_var.trace("w", lambda *args: self.volume_label.configure(text=f"{self.volume_var.get():.2f}"))

        # 右列参数
        ttk.Label(param_frame, text="噪声尺度：").grid(row=0, column=3, sticky="w", padx=(10, 5))
        noise_scale = ttk.Scale(param_frame, from_=0.0, to=1.0, orient="horizontal",
                               variable=self.noise_scale_var)
        noise_scale.grid(row=0, column=4, sticky="ew", padx=(0, 15))
        self.noise_scale_label = ttk.Label(param_frame, text="0.667", width=8)
        self.noise_scale_label.grid(row=0, column=5, sticky="w")
        self.noise_scale_var.trace("w", lambda *args: self.noise_scale_label.configure(text=f"{self.noise_scale_var.get():.3f}"))

        ttk.Label(param_frame, text="说话变异：").grid(row=1, column=3, sticky="w", padx=(10, 5), pady=(5, 0))
        noise_w_scale = ttk.Scale(param_frame, from_=0.0, to=1.0, orient="horizontal",
                                 variable=self.noise_w_scale_var)
        noise_w_scale.grid(row=1, column=4, sticky="ew", padx=(0, 15), pady=(5, 0))
        self.noise_w_label = ttk.Label(param_frame, text="0.800", width=8)
        self.noise_w_label.grid(row=1, column=5, sticky="w", pady=(5, 0))
        self.noise_w_scale_var.trace("w", lambda *args: self.noise_w_label.configure(text=f"{self.noise_w_scale_var.get():.3f}"))

        # 音频归一化（使用ttkbootstrap的Checkbutton）
        norm_check = ttkbs.Checkbutton(param_frame, text="音频归一化（推荐开启）",
                       variable=self.normalize_audio_var, bootstyle="success-round-toggle")
        norm_check.grid(row=2, column=3, columnspan=3, sticky="w", padx=(10, 0), pady=(5, 0))

        # ========== 第三部分：控制功能 ==========
        control_frame = ttk.LabelFrame(main_frame, text="播放控制", padding=8)
        control_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        control_frame.grid_columnconfigure(1, weight=1)

        # 跳转功能
        ttk.Label(control_frame, text="起始句：", width=8).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.jump_entry = ttkbs.Entry(control_frame, width=8, bootstyle=INFO)
        self.jump_entry.grid(row=0, column=1, sticky="w", padx=(0, 10))
        ttk.Label(control_frame, text="（从1开始计数）", font=("Arial", 9)).grid(row=0, column=2, sticky="w")

        # 插入内容
        ttk.Label(control_frame, text="插入内容：", width=8).grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5, 0))
        self.input_entry = ttkbs.Entry(control_frame, bootstyle=PRIMARY)
        self.input_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 5), pady=(5, 0))
        self.input_entry.bind("<Return>", self.submit_insert)
        insert_btn = ttkbs.Button(control_frame, text="插入", command=self.submit_insert, bootstyle=PRIMARY, width=8)
        insert_btn.grid(row=1, column=3, pady=(5, 0))

        # 控制按钮
        btn_subframe = ttk.Frame(control_frame)
        btn_subframe.grid(row=2, column=0, columnspan=4, pady=(8, 0))
        self.start_btn = ttkbs.Button(btn_subframe, text="开始朗读", command=self.start_reading, bootstyle=SUCCESS, width=12)
        self.start_btn.pack(side="left", padx=(0, 10))
        self.stop_btn = ttkbs.Button(btn_subframe, text="停止朗读", command=self.stop_reading, bootstyle=DANGER, width=12, state="disabled")
        self.stop_btn.pack(side="left")

        # 进度显示
        self.progress_label = ttk.Label(control_frame, text="进度: 0 / 0    当前: -", font=("Segoe UI", 10))
        self.progress_label.grid(row=0, column=3, rowspan=2, sticky="e", padx=(10, 0))

        # ========== 第四部分：日志区域 ==========
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding=8)
        log_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 5))
        main_frame.grid_rowconfigure(3, weight=1)  # 日志区域自动扩展

        self.log_text = ScrolledText(log_frame, height=8, wrap="word", autohide=True)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.text.configure(state="disabled")
        self.log_text.insert("end", "日志区域...\n")

    def _on_pause_change(self, value):
        ms = int(float(value))
        self.pause_label.configure(text=f"{ms} ms")

    def check_resume(self):
        """检查断点续读"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                last_json = state.get("json_path")
                last_index = state.get("current_index", 0)

                if last_json and os.path.exists(last_json):
                    if messagebox.askyesno("断点续读", f"检测到上次进度：\n{os.path.basename(last_json)}\n已读到第 {last_index+1} 句\n是否继续？"):
                        self.current_json_path = last_json
                        self.current_index = last_index
                        with open(last_json, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        self.sentences = [item["text"] for item in data if isinstance(item.get("text"), str)]
                        self.file_label.configure(text=os.path.basename(last_json))
                        self.update_progress(f"进度: {self.current_index} / {len(self.sentences)}    当前: {self.current_index}")
                        self.jump_entry.delete(0, "end")
                        self.jump_entry.insert(0, str(last_index + 1))
                        self.log(f"恢复进度：{os.path.basename(last_json)} @ 第 {last_index+1} 句")
                        return
            except Exception as e:
                self.log(f"读取断点失败: {e}")

        self.log("无断点或选择从头开始")

    def save_state(self):
        """保存朗读进度"""
        if self.current_json_path:
            state = {
                "json_path": self.current_json_path,
                "current_index": self.current_index
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

    def select_json_file(self):
        """选择JSON文件"""
        file_path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.sentences = [item["text"] for item in data if isinstance(item.get("text"), str)]
            self.current_json_path = file_path
            self.current_index = 0
            self.file_label.configure(text=os.path.basename(file_path))
            self.update_progress(f"进度: 0 / {len(self.sentences)}    当前: -")
            self.jump_entry.delete(0, "end")
            self.jump_entry.insert(0, "1")

            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state.get("json_path") == file_path:
                    saved_index = state.get("current_index", 0)
                    if saved_index > 0 and saved_index < len(self.sentences):
                        if messagebox.askyesno("断点续读", f"检测到断点：已读到第 {saved_index+1} 句\n是否继续？"):
                            self.current_index = saved_index
                            self.update_progress(f"进度: {self.current_index} / {len(self.sentences)}    当前: {self.current_index}")
                            self.jump_entry.delete(0, "end")
                            self.jump_entry.insert(0, str(saved_index + 1))
                            self.log(f"自动恢复到第 {saved_index+1} 句")

            self.log(f"加载成功：{len(self.sentences)} 条句子")
            messagebox.showinfo("成功", f"已加载 {len(self.sentences)} 个句子")
            self.save_state()
        except Exception as e:
            messagebox.showerror("错误", f"加载失败：\n{e}")

    def on_model_select(self, event=None):
        """加载选中的Piper语音模型"""
        model_name = self.model_combo.get()
        if not model_name:
            return

        model_path = os.path.join(get_piper_voices_dir(), model_name)

        try:
            self.voice = PiperVoice.load(model_path)
            self.selected_model_path = model_path
            self.log(f"模型加载成功: {model_name}")
            self.log(f"采样率: {self.voice.config.sample_rate} Hz")
        except Exception as e:
            self.log(f"模型加载失败: {str(e)}")
            messagebox.showerror("错误", f"加载失败:\n{str(e)}\n路径: {model_path}")
            self.voice = None

    def submit_insert(self, event=None):
        """插入朗读内容"""
        content = self.input_entry.get().strip()
        self.input_entry.delete(0, "end")
        if not content or not self.is_running:
            return

        temp = []
        while not self.task_queue.empty():
            temp.append(self.task_queue.get())
        self.task_queue.put(content)
        for item in temp:
            self.task_queue.put(item)

        self.log(f"[插入] 已插入到当前句与下一句之间: {content}")

    def start_reading(self):
        """开始朗读"""
        if not self.sentences:
            messagebox.showwarning("提示", "请先选择 JSON 文件")
            return

        if not self.voice:
            current_model = self.model_combo.get()
            if current_model:
                self.on_model_select()
            else:
                messagebox.showwarning("提示", "请先选择声音模型")
                return

        if not self.voice:
            messagebox.showwarning("提示", "模型加载失败，请重新选择")
            return

        jump_str = self.jump_entry.get().strip()
        if jump_str:
            try:
                start_idx = int(jump_str) - 1
                if 0 <= start_idx < len(self.sentences):
                    self.current_index = start_idx
                    self.log(f"[跳转] 从第 {start_idx+1} 句开始")
                else:
                    self.log(f"跳转无效，使用当前进度 {self.current_index+1}")
            except ValueError:
                self.log("跳转输入无效，使用当前进度")

        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        while not self.task_queue.empty():
            self.task_queue.get()
        for s in self.sentences[self.current_index:]:
            self.task_queue.put(s)

        threading.Thread(target=self.speaker_thread, daemon=True).start()
        self.log("开始朗读...")

    def stop_reading(self):
        """停止朗读"""
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.update_progress(f"进度: {self.current_index} / {len(self.sentences)}    当前: -")
        try:
            sd.stop()
        except:
            pass
        self.log("已停止")
        self.save_state()

    def synthesize_and_play(self, text: str):
        """合成并播放语音"""
        if not text.strip() or not self.voice or not self.is_running:
            return

        self.log(f"[朗读] {text[:60]}{'...' if len(text)>60 else ''}")

        try:
            # 从界面读取所有参数
            syn_config = SynthesisConfig(
                length_scale=self.length_scale_var.get(),
                volume=self.volume_var.get(),
                noise_scale=self.noise_scale_var.get(),
                noise_w_scale=self.noise_w_scale_var.get(),
                normalize_audio=self.normalize_audio_var.get()
            )

            # 合成到临时 wav
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_wav_path = tmp.name

            with wave.open(tmp_wav_path, "wb") as wav_file:
                self.voice.synthesize_wav(text, wav_file, syn_config=syn_config)

            # 播放
            with wave.open(tmp_wav_path, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                audio_data = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype=np.int16)

            sd.play(audio_data, sample_rate, blocking=True)
            while sd.get_stream().active and self.is_running:
                time.sleep(0.01)

            pause_sec = self.pause_var.get() / 1000.0
            if pause_sec > 0 and self.is_running:
                time.sleep(pause_sec)

            try:
                os.unlink(tmp_wav_path)
            except:
                pass

        except Exception as e:
            self.log(f"播放错误: {type(e).__name__}: {str(e)}")
            try:
                sd.stop()
            except:
                pass

    def speaker_thread(self):
        """朗读线程"""
        try:
            while self.is_running and not self.task_queue.empty():
                sentence = self.task_queue.get()
                if not self.is_running:
                    break
                self.synthesize_and_play(sentence)
                self.current_index += 1
                self.save_state()
                self.update_progress(f"进度: {self.current_index} / {len(self.sentences)}    当前: {self.current_index}")
            if self.is_running and self.current_index >= len(self.sentences):
                self.ui_queue.put(("finish", ""))
        except Exception as e:
            self.log(f"朗读线程错误: {type(e).__name__}: {str(e)}")
            self.is_running = False
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            try:
                sd.stop()
            except:
                pass

if __name__ == "__main__":
    try:
        app = TTSApp()
        app.mainloop()
    except Exception as e:
        err_msg = f"程序启动错误: {type(e).__name__}: {str(e)}"
        messagebox.showerror("错误", err_msg)
        # 新增：将错误日志写入exe同目录的error_detail.log
        log_path = os.path.join(get_base_dir(), "error_detail.log")
        with open(log_path, "w", encoding="utf-8") as f:
            import traceback
            f.write(traceback.format_exc())  # 写入完整的堆栈信息