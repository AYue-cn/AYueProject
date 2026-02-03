import os
import json
import threading
import queue
import time
import sys
import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, IntVar, DoubleVar
from pathlib import Path
import torch
import scipy.io.wavfile
from pocket_tts import TTSModel
import ttkbootstrap as ttkbs
from ttkbootstrap.constants import *
from ttkbootstrap.widgets.scrolled import ScrolledText

# ==================== SoundDevice 初始化 ====================
try:
    sd._initialize()
    sd.default.channels = 1
except Exception as e:
    print(f"SoundDevice 初始化提示: {e}")

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

class TTSApp(ttkbs.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("阿岳TTS 阅读器 - Pocket-TTS v1.3")
        self.geometry("625x820")
        self.minsize(625, 820)

        self.sentences = []
        self.current_json_path = None
        self.current_index = 0
        self.task_queue = queue.Queue()               # 待合成文本队列
        self.audio_queue = queue.Queue(maxsize=20)    # 已合成音频队列
        self.is_running = False
        self.synthesis_running = False

        self.model: TTSModel = None
        self.voice_state = None
        self.clone_audio_path = None

        self.state_file = os.path.join(get_base_dir(), "playback_state.json")

        # 参数 - 与界面默认显示值保持一致
        self.pause_var = IntVar(value=0)              # 对应标签 "0 ms"
        self.preload_count_var = IntVar(value=4)
        self.temp_var = DoubleVar(value=0.70)
        self.frames_after_eos_var = IntVar(value=15)
        self.lsd_steps_var = IntVar(value=4)          # 注意这里是 4，与你代码一致
        self.noise_clamp_var = DoubleVar(value=0.0)

        self.model_dirty = True

        self.ui_queue = queue.Queue()
        self.process_ui_queue()

        self.load_model()
        self.create_interface()
        self._sync_labels()  # ← 新增：初始化时同步所有标签显示
        self.check_resume()

        # 参数变化标记 + 实时更新标签
        for var, lbl, fmt in [
            (self.temp_var, self.temp_lbl, "{:.2f}"),
            (self.frames_after_eos_var, self.frames_lbl, "{}"),
            (self.lsd_steps_var, self.lsd_lbl, "{}"),
            (self.noise_clamp_var, self.clamp_lbl, "{:.2f}"),
            (self.pause_var, self.pause_lbl, "{} ms"),
            (self.preload_count_var, self.preload_lbl, "{} 句")
        ]:
            var.trace_add("write", lambda *a, v=var, l=lbl, f=fmt: l.configure(text=f.format(v.get())))
            var.trace_add("write", self._mark_dirty if var in [self.temp_var, self.frames_after_eos_var, self.lsd_steps_var, self.noise_clamp_var] else lambda *a: None)

    def _sync_labels(self):
        """初始化时强制同步所有参数标签显示"""
        self.temp_lbl.configure(text=f"{self.temp_var.get():.2f}")
        self.frames_lbl.configure(text=str(self.frames_after_eos_var.get()))
        self.lsd_lbl.configure(text=str(self.lsd_steps_var.get()))
        self.clamp_lbl.configure(text=f"{self.noise_clamp_var.get():.2f}")
        self.pause_lbl.configure(text=f"{self.pause_var.get()} ms")
        self.preload_lbl.configure(text=f"{int(self.preload_count_var.get())} 句")

    def _mark_dirty(self, *args):
        self.model_dirty = True
        self.log("生成参数已变更，下次合成将重新加载模型")

    # ==================== UI 队列处理 ====================
    def process_ui_queue(self):
        while not self.ui_queue.empty():
            task = self.ui_queue.get()
            if task[0] == "log":
                self._safe_log(task[1])
            elif task[0] == "update_progress":
                self.progress_label.configure(text=task[1])
            elif task[0] == "finish":
                self.stop_reading()
                messagebox.showinfo("完成", "所有内容已朗读完毕！")
        self.after(10, self.process_ui_queue)

    def _safe_log(self, msg):
        self.log_text.text.configure(state="normal")
        tag = "error" if any(w in msg.lower() for w in ["错误", "失败", "异常"]) else None
        self.log_text.text.insert("end", msg + "\n", tag)
        self.log_text.text.see("end")
        self.log_text.text.configure(state="disabled")

    def log(self, msg):
        self.ui_queue.put(("log", msg))

    def update_progress(self, text):
        self.ui_queue.put(("update_progress", text))

    # ==================== 模型加载 ====================
    def load_model(self):
        if not self.model_dirty and self.model is not None:
            return
        try:
            noise_clamp = self.noise_clamp_var.get() if self.noise_clamp_var.get() > 0 else None
            self.model = TTSModel.load_model(
                temp=self.temp_var.get(),
                lsd_decode_steps=self.lsd_steps_var.get(),
                noise_clamp=noise_clamp,
                eos_threshold=-4.0
            )
            self.model_dirty = False
            self.log(f"模型加载成功 | temp={self.temp_var.get():.2f} | lsd={self.lsd_steps_var.get()} | 采样率={self.model.sample_rate}")
        except Exception as e:
            self.log(f"模型加载失败: {e}")
            messagebox.showerror("错误", f"模型加载失败:\n{e}")
            self.model = None

    # ==================== 语音克隆 ====================
    def select_clone_audio(self):
        path = filedialog.askopenfilename(
            title="选择克隆音频（推荐5s+清晰人声）",
            filetypes=[("WAV 文件", "*.wav"), ("所有文件", "*.*")]
        )
        if not path:
            return
        if not self.model:
            messagebox.showwarning("警告", "模型未加载，无法克隆")
            return
        try:
            self.voice_state = self.model.get_state_for_audio_prompt(path)
            self.clone_audio_path = path
            self.clone_label.configure(text=f"已克隆: {os.path.basename(path)}")
            self.log(f"语音克隆成功 → {os.path.basename(path)}")
        except Exception as e:
            self.log(f"克隆失败: {e}")
            messagebox.showerror("克隆失败", str(e))

    # ==================== 界面 ====================
    def create_interface(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        top = ttk.LabelFrame(main, text="基础设置", padding=10)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,10))
        top.grid_columnconfigure(1, weight=1)

        ttk.Label(top, text="JSON文件：").grid(row=0, column=0, sticky="w", padx=(0,5))
        self.file_label = ttkbs.Label(top, text="未选择", bootstyle=SECONDARY)
        self.file_label.grid(row=0, column=1, sticky="ew")
        ttkbs.Button(top, text="选择", command=self.select_json_file, bootstyle=SUCCESS).grid(row=0, column=2, padx=5)

        ttk.Label(top, text="克隆语音：").grid(row=1, column=0, sticky="w", padx=(0,5), pady=(8,0))
        self.clone_label = ttkbs.Label(top, text="未克隆（默认声线）", bootstyle=INFO)
        self.clone_label.grid(row=1, column=1, sticky="ew", pady=(8,0))
        ttkbs.Button(top, text="上传音频克隆", command=self.select_clone_audio, bootstyle=PRIMARY).grid(row=1, column=2, padx=5, pady=(8,0))

        param = ttk.LabelFrame(main, text="生成 & 播放参数", padding=10)
        param.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,10))
        param.grid_columnconfigure(1, weight=1)
        param.grid_columnconfigure(4, weight=1)

        ttk.Label(param, text="温度:").grid(row=0, column=0, sticky="w")
        ttk.Scale(param, from_=0.5, to=1.2, variable=self.temp_var).grid(row=0, column=1, sticky="ew", padx=(0,15))
        self.temp_lbl = ttk.Label(param, text="0.70")  # 初始值与 temp_var 一致
        self.temp_lbl.grid(row=0, column=2)

        ttk.Label(param, text="EOS后帧:").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Scale(param, from_=0, to=60, variable=self.frames_after_eos_var).grid(row=1, column=1, sticky="ew", padx=(0,15), pady=6)
        self.frames_lbl = ttk.Label(param, text="15")
        self.frames_lbl.grid(row=1, column=2, pady=6)

        ttk.Label(param, text="解码步数:").grid(row=0, column=3, sticky="w", padx=(20,0))
        ttk.Scale(param, from_=1, to=6, variable=self.lsd_steps_var).grid(row=0, column=4, sticky="ew", padx=(0,15))
        self.lsd_lbl = ttk.Label(param, text="4")  # 与 lsd_steps_var 初始值一致
        self.lsd_lbl.grid(row=0, column=5)

        ttk.Label(param, text="噪声钳位:").grid(row=1, column=3, sticky="w", padx=(20,0), pady=6)
        ttk.Scale(param, from_=0.0, to=1.0, variable=self.noise_clamp_var).grid(row=1, column=4, sticky="ew", padx=(0,15), pady=6)
        self.clamp_lbl = ttk.Label(param, text="0.00")
        self.clamp_lbl.grid(row=1, column=5, pady=6)

        ttk.Label(param, text="句间暂停(ms):").grid(row=2, column=0, sticky="w", pady=(10,0))
        ttk.Scale(param, from_=0, to=2000, variable=self.pause_var).grid(row=2, column=1, sticky="ew", padx=(0,15), pady=(10,0))
        self.pause_lbl = ttk.Label(param, text="0 ms")  # 与 pause_var 初始值一致
        self.pause_lbl.grid(row=2, column=2, pady=(10,0))

        ttk.Label(param, text="预缓存句子:").grid(row=2, column=3, sticky="w", padx=(20,0), pady=(10,0))
        ttk.Scale(param, from_=1, to=10, variable=self.preload_count_var).grid(row=2, column=4, sticky="ew", padx=(0,15), pady=(10,0))
        self.preload_lbl = ttk.Label(param, text="4 句")
        self.preload_lbl.grid(row=2, column=5, pady=(10,0))

        ctrl = ttk.LabelFrame(main, text="播放控制", padding=10)
        ctrl.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0,10))

        ttk.Label(ctrl, text="起始句：").grid(row=0, column=0, sticky="w")
        self.jump_entry = ttkbs.Entry(ctrl, width=8)
        self.jump_entry.grid(row=0, column=1, sticky="w", padx=5)
        self.jump_entry.insert(0, "1")

        ttk.Label(ctrl, text="插入内容：").grid(row=1, column=0, sticky="w", pady=(8,0))
        self.input_entry = ttkbs.Entry(ctrl)
        self.input_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=(8,0))
        self.input_entry.bind("<Return>", lambda e: self.submit_insert())

        ttkbs.Button(ctrl, text="插入", command=self.submit_insert, bootstyle=PRIMARY).grid(row=1, column=2, padx=5, pady=(8,0))

        btns = ttk.Frame(ctrl)
        btns.grid(row=2, column=0, columnspan=3, pady=12)
        self.start_btn = ttkbs.Button(btns, text="开始朗读", command=self.start_reading, bootstyle=SUCCESS, width=15)
        self.start_btn.pack(side="left", padx=8)
        self.stop_btn = ttkbs.Button(btns, text="停止朗读", command=self.stop_reading, bootstyle=DANGER, width=15, state="disabled")
        self.stop_btn.pack(side="left")

        self.progress_label = ttk.Label(ctrl, text="进度: 0 / 0", font=("Segoe UI", 11, "bold"))
        self.progress_label.grid(row=0, column=3, rowspan=2, sticky="e", padx=20)

        logf = ttk.LabelFrame(main, text="日志", padding=8)
        logf.grid(row=3, column=0, columnspan=2, sticky="nsew")
        main.grid_rowconfigure(3, weight=1)

        self.log_text = ScrolledText(logf, height=12, wrap="word")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.text.configure(state="disabled")
        self.log_text.insert("end", "阿岳TTS - Pocket-TTS 预缓存版 已就绪\n插入文本已修复：会插入到当前朗读句之后\n")

    # ==================== 合成函数 ====================
    def _synthesize_to_numpy(self, text: str):
        try:
            self.load_model()
            state = self.voice_state or self.model.get_state_for_audio_prompt(
                "hf://kyutai/tts-voices/alba-mackenna/casual.wav")
            audio_tensor = self.model.generate_audio(
                state,
                text,
                frames_after_eos=self.frames_after_eos_var.get(),
                copy_state=True
            )
            return audio_tensor.cpu().numpy().astype(np.float32)
        except Exception as e:
            self.log(f"合成失败 '{text[:30]}...': {e}")
            return None

    # ==================== 预合成线程 ====================
    def synthesis_worker(self):
        self.synthesis_running = True
        self.log("预合成线程启动...")
        while self.synthesis_running and self.is_running:
            try:
                target = self.preload_count_var.get()
                if self.audio_queue.qsize() < target and not self.task_queue.empty():
                    text = self.task_queue.get()
                    audio_np = self._synthesize_to_numpy(text)
                    if audio_np is not None:
                        self.audio_queue.put((audio_np, text))
                        self.log(f"[预合成] 已缓存: {text}")
                else:
                    time.sleep(0.2 if self.audio_queue.qsize() < target else 0.5)
            except Exception as e:
                self.log(f"预合成异常: {e}")
                time.sleep(1)
        self.log("预合成线程停止")

    # ==================== 播放线程 ====================
    def playback_worker(self):
        self.log("播放线程启动...")
        try:
            while self.is_running:
                try:
                    audio_np, text = self.audio_queue.get(timeout=3.0)
                    self.log(f"播放: {text}")
                    sd.play(audio_np, samplerate=self.model.sample_rate, blocking=True)
                    if self.is_running and self.pause_var.get() > 0:
                        time.sleep(self.pause_var.get() / 1000.0)
                    self.current_index += 1
                    self.update_progress(f"进度: {self.current_index} / {len(self.sentences)}")
                    self.save_state()
                except queue.Empty:
                    if self.task_queue.empty() and self.audio_queue.empty():
                        self.ui_queue.put(("finish", None))
                        break
                    continue
                except Exception as e:
                    self.log(f"播放异常: {e}")
                    break
        finally:
            self.is_running = False
            self.synthesis_running = False
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")

    # ==================== 控制函数 ====================
    def check_resume(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    s = json.load(f)
                last_json = s.get("json_path")
                last_idx = s.get("current_index", 0)
                if last_json and os.path.exists(last_json):
                    if messagebox.askyesno("断点续读", f"上次进度：第 {last_idx+1} 句\n是否继续？"):
                        self.current_json_path = last_json
                        self.current_index = last_idx
                        self.select_json_file(last_json, resume=True)
            except: pass

    def save_state(self):
        if self.current_json_path:
            state = {"json_path": self.current_json_path, "current_index": self.current_index}
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)

    def select_json_file(self, path=None, resume=False):
        if path is None:
            path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.sentences = [item["text"] for item in data if isinstance(item.get("text"), str)]
            self.current_json_path = path
            if not resume:
                self.current_index = 0
            self.file_label.configure(text=os.path.basename(path))
            self.update_progress(f"进度: {self.current_index} / {len(self.sentences)}")
            self.log(f"加载完成：{len(self.sentences)} 句")
            self.save_state()
        except Exception as e:
            messagebox.showerror("加载错误", f"JSON 加载失败：{e}")

    def submit_insert(self):
        text = self.input_entry.get().strip()
        if not text or not self.is_running:
            return

        temp = []
        while not self.task_queue.empty():
            temp.append(self.task_queue.get())

        self.task_queue.put(text)
        for item in temp:
            self.task_queue.put(item)

        self.log(f"[插入成功] 已添加到下一句前: {text}")
        self.input_entry.delete(0, "end")

    def start_reading(self):
        if not self.sentences:
            messagebox.showwarning("提示", "请先加载 JSON 文件")
            return
        if not self.model:
            messagebox.showerror("错误", "模型未加载")
            return

        try:
            jump = int(self.jump_entry.get().strip()) - 1
            if 0 <= jump < len(self.sentences):
                self.current_index = jump
                self.log(f"跳转到第 {jump+1} 句")
        except: pass

        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        while not self.task_queue.empty():
            self.task_queue.get()
        while not self.audio_queue.empty():
            self.audio_queue.get()

        for s in self.sentences[self.current_index:]:
            self.task_queue.put(s)

        threading.Thread(target=self.synthesis_worker, daemon=True).start()
        threading.Thread(target=self.playback_worker, daemon=True).start()

        self.log("开始朗读... 预合成 & 播放线程已启动")

    def stop_reading(self):
        self.is_running = False
        self.synthesis_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        sd.stop()
        self.save_state()
        self.log("朗读已停止")

if __name__ == "__main__":
    try:
        app = TTSApp()
        app.mainloop()
    except Exception as e:
        print(f"程序启动异常: {e}")
        import traceback
        with open("startup_error.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)