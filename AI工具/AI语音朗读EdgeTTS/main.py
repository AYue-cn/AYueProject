import os
import json
import threading
import queue
import time
import re
import numpy as np
import sounddevice as sd
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, StringVar, IntVar, DoubleVar
import asyncio
import io
import soundfile as sf
from datetime import datetime
import edge_tts
from edge_tts import VoicesManager, SubMaker

# 修复：设置全局异步策略，解决线程中异步调用冲突
asyncio.set_event_loop_policy(
    asyncio.WindowsSelectorEventLoopPolicy() if os.name == 'nt' else asyncio.DefaultEventLoopPolicy())


class TTSApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("JSON TTS 阅读器 - Edge TTS (无缝+合句+JSON容错版)")
        self.geometry("980x1050")
        self.resizable(True, True)

        # 核心数据存储
        self.sentences = []  # 最终播放的句子（合并后）
        self.original_sentences = []  # 原始加载的句子（用于回滚）
        self.current_index = 0
        self.task_queue = queue.Queue()
        self.audio_buffer_queue = queue.Queue(maxsize=10)
        self.max_prefetch = 4  # 默认预合成数量提升至4（适配长文本）
        self.model_lock = threading.Lock()
        self.interrupt_event = threading.Event()
        self.interrupt_content = None
        self.is_running = False
        self.synthesis_running = False
        self.synthesis_thread = None
        self.available_voices = []
        self.filtered_voices = []
        self.submaker = None

        # 音频播放相关
        self.audio_streams = []
        self.audio_playback_finished = threading.Event()
        self.current_audio_duration = 0
        self.sample_rate = 24000

        # 音频前后段单独裁剪（默认前段0ms、后段100ms）
        self.crop_front_ms = IntVar(value=0)
        self.crop_back_ms = IntVar(value=100)
        self.crop_front_points = 0
        self.crop_back_points = 0
        self.crop_debounce = False  # 裁剪参数防抖变量，避免重复触发
        self.init_crop_points()

        # 自动合并短句配置项（可自定义）
        self.auto_merge_var = IntVar(value=1)  # 是否启用自动合并，1=启用（默认），0=关闭
        self.min_zh_len = IntVar(value=15)  # 中文短句阈值：≤15汉字为短句（可自定义）
        self.min_en_len = IntVar(value=30)  # 英文短句阈值：≤30字符为短句（可自定义）
        self.max_merge_num = IntVar(value=5)  # 最大合并句数：最多合并5句（避免合成长文本）

        # Edge TTS 配置参数
        self.voice_var = StringVar(value="en-US-AnaNeural (Female/en-US)")
        self.rate_var = DoubleVar(value=5.0)  # 适配你的语速+5%设置
        self.volume_var = DoubleVar(value=0.0)
        self.pitch_var = DoubleVar(value=0.0)
        self.save_subtitle_var = IntVar(value=0)
        self.subtitle_path = "tts_subtitles.srt"

        # 播放控制参数
        self.mode_var = StringVar(value="interrupt")
        self.pause_var = IntVar(value=-50)  # 默认重叠-50ms（无缝核心）
        self.prefetch_var = IntVar(value=self.max_prefetch)  # 预合成默认4

        # 音色筛选参数
        self.voice_filter_var = StringVar(value="")

        self.create_widgets()
        self.load_edge_tts_voices()

    def init_crop_points(self):
        """初始化音频裁剪采样点数"""
        self.crop_front_points = int(self.sample_rate * (self.crop_front_ms.get() / 1000))
        self.crop_back_points = int(self.sample_rate * (self.crop_back_ms.get() / 1000))

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        # 1. JSON文件选择区
        ttk.Label(main_frame, text="JSON 文件：", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 5))
        self.file_label = ttk.Label(main_frame, text="未选择", wraplength=880, bootstyle=SECONDARY)
        self.file_label.pack(anchor="w", fill="x")
        select_btn = ttk.Button(main_frame, text="选择 JSON 文件", command=self.select_json_file, bootstyle=SUCCESS)
        select_btn.pack(pady=(5, 8))

        # 自动合并短句配置区（核心）
        merge_frame = ttk.Labelframe(main_frame, text="自动合并短句配置（可选启用）", padding=10, bootstyle=PRIMARY)
        merge_frame.pack(fill="x", pady=(0, 15))
        # 启用/关闭复选框
        ttk.Checkbutton(merge_frame, text="启用自动合并短句", variable=self.auto_merge_var,
                        bootstyle=PRIMARY).pack(side="left", padx=(0, 20))
        # 中文阈值
        ttk.Label(merge_frame, text="中文最短阈值：", bootstyle=SECONDARY).pack(side="left", padx=(10, 2))
        zh_entry = ttk.Entry(merge_frame, textvariable=self.min_zh_len, width=6, justify="center")
        zh_entry.pack(side="left")
        ttk.Label(merge_frame, text="汉字（≤为短句）", bootstyle=SECONDARY).pack(side="left", padx=(2, 15))
        # 英文阈值
        ttk.Label(merge_frame, text="英文最短阈值：", bootstyle=SECONDARY).pack(side="left", padx=(10, 2))
        en_entry = ttk.Entry(merge_frame, textvariable=self.min_en_len, width=6, justify="center")
        en_entry.pack(side="left")
        ttk.Label(merge_frame, text="字符（≤为短句）", bootstyle=SECONDARY).pack(side="left", padx=(2, 15))
        # 最大合并数
        ttk.Label(merge_frame, text="最大合并句数：", bootstyle=SECONDARY).pack(side="left", padx=(10, 2))
        num_entry = ttk.Entry(merge_frame, textvariable=self.max_merge_num, width=6, justify="center")
        num_entry.pack(side="left")
        ttk.Label(merge_frame, text="句（避免合成长文本）", bootstyle=SECONDARY).pack(side="left", padx=(2, 0))
        # 提示
        ttk.Label(merge_frame, text="💡 合并后仍为短文本，适配Edge TTS，默认配置：中15/英30/最大5句",
                  bootstyle=INFO).pack(side="left", padx=(20, 0))

        # 2. Edge TTS 核心配置区
        tts_frame = ttk.Labelframe(main_frame, text="Edge TTS 核心配置", padding=10, bootstyle=INFO)
        tts_frame.pack(fill="x", pady=10)

        # 2.1 音色选择 + 实时筛选
        voice_frame = ttk.Frame(tts_frame)
        voice_frame.pack(fill="x", pady=8)
        ttk.Label(voice_frame, text="语音选择：", width=12, anchor="w").pack(side="left")
        self.voice_combobox = ttk.Combobox(voice_frame, textvariable=self.voice_var, width=55, state="readonly")
        self.voice_combobox.pack(side="left", padx=5)
        refresh_voice_btn = ttk.Button(voice_frame, text="刷新", command=self.load_edge_tts_voices,
                                       bootstyle=OUTLINE, width=6)
        refresh_voice_btn.pack(side="left", padx=3)
        ttk.Label(voice_frame, text="筛选：", bootstyle=INFO).pack(side="left", padx=(10, 3))
        voice_filter_entry = ttk.Entry(voice_frame, textvariable=self.voice_filter_var, width=15)
        voice_filter_entry.pack(side="left")
        self.voice_filter_var.trace_add("write", self.filter_voices)

        # 2.2 语速调整
        rate_frame = ttk.Frame(tts_frame)
        rate_frame.pack(fill="x", pady=5)
        ttk.Label(rate_frame, text="语速：", width=12, anchor="w").pack(side="left")
        ttk.Scale(rate_frame, from_=-50, to=50, orient="horizontal", variable=self.rate_var,
                  length=500, command=self.update_rate_label).pack(side="left", padx=5)
        self.rate_label = ttk.Label(rate_frame, text="+0%", width=8, anchor="w")
        self.rate_label.pack(side="left")

        # 2.3 音量调整
        volume_frame = ttk.Frame(tts_frame)
        volume_frame.pack(fill="x", pady=5)
        ttk.Label(volume_frame, text="音量：", width=12, anchor="w").pack(side="left")
        ttk.Scale(volume_frame, from_=-50, to=50, orient="horizontal", variable=self.volume_var,
                  length=500, command=self.update_volume_label).pack(side="left", padx=5)
        self.volume_label = ttk.Label(volume_frame, text="+0%", width=8, anchor="w")
        self.volume_label.pack(side="left")

        # 2.4 音调调整
        pitch_frame = ttk.Frame(tts_frame)
        pitch_frame.pack(fill="x", pady=5)
        ttk.Label(pitch_frame, text="音调：", width=12, anchor="w").pack(side="left")
        ttk.Scale(pitch_frame, from_=-50, to=50, orient="horizontal", variable=self.pitch_var,
                  length=500, command=self.update_pitch_label).pack(side="left", padx=5)
        self.pitch_label = ttk.Label(pitch_frame, text="+0Hz", width=8, anchor="w")
        self.pitch_label.pack(side="left")

        # 2.5 音频前后段单独裁剪
        crop_frame = ttk.Frame(tts_frame)
        crop_frame.pack(fill="x", pady=8)
        ttk.Label(crop_frame, text="音频裁剪：", width=12, anchor="w").pack(side="left")
        ttk.Label(crop_frame, text="前段(ms)：", bootstyle=SECONDARY).pack(side="left", padx=(5, 2))
        crop_front_entry = ttk.Entry(crop_frame, textvariable=self.crop_front_ms, width=8, justify="center")
        crop_front_entry.pack(side="left")
        ttk.Label(crop_frame, text="后段(ms)：", bootstyle=SECONDARY).pack(side="left", padx=(15, 2))
        crop_back_entry = ttk.Entry(crop_frame, textvariable=self.crop_back_ms, width=8, justify="center")
        crop_back_entry.pack(side="left")
        ttk.Label(crop_frame, text="💡 0=不裁剪，仅支持非负整数", bootstyle=INFO).pack(side="left", padx=(10, 0))
        self.crop_front_ms.trace_add("write", self.on_crop_value_change)
        self.crop_back_ms.trace_add("write", self.on_crop_value_change)

        # 2.6 字幕保存选项
        subtitle_frame = ttk.Frame(tts_frame)
        subtitle_frame.pack(fill="x", pady=5)
        ttk.Checkbutton(subtitle_frame, text="生成SRT字幕文件", variable=self.save_subtitle_var,
                        bootstyle=PRIMARY).pack(side="left")
        ttk.Label(subtitle_frame, text="保存路径：").pack(side="left", padx=10)
        self.subtitle_path_entry = ttk.Entry(subtitle_frame, width=45, textvariable=StringVar(value=self.subtitle_path))
        self.subtitle_path_entry.pack(side="left")
        ttk.Button(subtitle_frame, text="选择", command=self.select_subtitle_path, bootstyle=OUTLINE, width=6).pack(
            side="left", padx=5)

        # 3. 播放控制区
        play_frame = ttk.Labelframe(main_frame, text="播放控制（调小/负数=更紧凑）", padding=10, bootstyle=WARNING)
        play_frame.pack(fill="x", pady=10)

        # 3.1 播放模式
        mode_frame = ttk.Frame(play_frame)
        mode_frame.pack(fill="x", pady=5)
        ttk.Radiobutton(mode_frame, text="打断模式（立即插入并中断当前）", variable=self.mode_var,
                        value="interrupt", command=self.update_input_label, bootstyle=PRIMARY).pack(anchor="w", pady=3)
        ttk.Radiobutton(mode_frame, text="插入模式（插入到下一个句子前）", variable=self.mode_var,
                        value="insert", command=self.update_input_label, bootstyle=PRIMARY).pack(anchor="w", pady=3)

        # 3.2 句子间间隔（默认-50ms重叠）
        pause_frame = ttk.Frame(play_frame)
        pause_frame.pack(fill="x", pady=5)
        ttk.Label(pause_frame, text="句子间间隔(ms)：", width=15, anchor="w").pack(side="left")
        ttk.Scale(pause_frame, from_=-200, to=500, orient="horizontal", variable=self.pause_var,
                  length=450, command=self.update_pause_label).pack(side="left", padx=5)
        self.pause_label = ttk.Label(pause_frame, text="当前间隔：-50 ms（重叠50ms）", width=25, anchor="w")
        self.pause_label.pack(side="left")
        ttk.Label(pause_frame, text="💡 负数=重叠，0=无缝，推荐-50ms", bootstyle=INFO).pack(side="left", padx=5)

        # 3.3 预合成数量（默认4，推荐5）
        prefetch_frame = ttk.Frame(play_frame)
        prefetch_frame.pack(fill="x", pady=5)
        ttk.Label(prefetch_frame, text="预合成数量：", width=15, anchor="w").pack(side="left")
        ttk.Spinbox(prefetch_frame, from_=1, to=8, textvariable=self.prefetch_var, width=5, bootstyle=PRIMARY).pack(
            side="left", padx=10)
        ttk.Label(prefetch_frame, text="长文本推荐4~5（减少播放等待）").pack(side="left")

        # 4. 插入/打断内容区
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill="x", pady=10)
        self.input_label = ttk.Label(input_frame, text="打断内容（立即插入并中断当前，按 Enter 提交）：", anchor="w")
        self.input_label.pack(anchor="w")
        self.input_entry = ttk.Entry(input_frame, width=90, bootstyle=PRIMARY)
        self.input_entry.pack(pady=5, fill="x")
        self.input_entry.bind("<Return>", self.submit_insert)

        # 5. 功能按钮区
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        self.start_btn = ttk.Button(btn_frame, text="开始朗读", command=self.start_reading, bootstyle=SUCCESS, width=15)
        self.start_btn.pack(side="left", padx=10)
        self.stop_btn = ttk.Button(btn_frame, text="停止朗读", command=self.stop_reading, bootstyle=DANGER, width=15,
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        # 6. 进度展示区
        self.progress_label = ttk.Label(main_frame, text="进度: 0 / 0    当前: -", font=("Segoe UI", 12, "bold"))
        self.progress_label.pack(pady=10)

        # 7. 日志展示区
        log_frame = ttk.Labelframe(main_frame, text="运行日志（含时间戳 & 缓冲状态）", padding=10, bootstyle=SECONDARY)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log_text = ttk.Text(log_frame, height=12, wrap="word", state="normal",
                                 bg="#2d2d2d", fg="#e0e0e0", insertbackground="white", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, side="left")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(fill="y", side="right")
        self.log_text.config(yscrollcommand=log_scroll.set)
        # 初始日志提示
        self.log_text.insert("end",
                             "欢迎使用 Edge TTS 无缝播放+自动合句+JSON容错版\n- 音色支持实时筛选（关键词：zh-CN/zh-TW/en-US/Female/Male等）\n"
                             "- 音频裁剪支持前后段单独设置，默认前段0ms（不裁）、后段100ms\n"
                             "- 句子间间隔默认-50ms（重叠播放），彻底消除停顿\n"
                             "- 自动合并短句：默认启用（中≤15汉字/英≤30字符为短句，最大合并5句）\n"
                             "- JSON容错：自动修复不完整的\u转义符，精准定位解析错误\n"
                             "- 预合成数量默认4，长文本推荐5，缓冲永远充足\n"
                             "- 字幕生成默认关闭，需手动勾选启用\n")
        self.log_text.configure(state="disabled")

        # 初始化参数标签
        self.update_rate_label(5)  # 适配默认语速+5%
        self.update_volume_label(0)
        self.update_pitch_label(0)
        self.update_pause_label(-50)  # 适配默认重叠-50ms
        self.update_input_label()

    # 核心工具函数1 - 判断文本类型（中文/英文）
    def judge_text_type(self, text):
        """判断文本是中文还是英文，返回zh/en"""
        # 匹配中文字符（含繁体）
        zh_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u{20000}-\u{2a6df}]', re.UNICODE)
        zh_chars = zh_pattern.findall(text)
        # 中文占比超50%则判定为中文，否则为英文
        if len(zh_chars) / len(text) > 0.5 if text else False:
            return "zh"
        return "en"

    # 核心函数 - 自动合并短句
    def merge_short_sentences(self, original_sentences):
        """
        自动合并短句，规则：
        1. 中文≤min_zh_len汉字/英文≤min_en_len字符 → 判定为短句
        2. 短句加入缓冲区，缓冲区达到max_merge_num句/遇到长句 → 合并缓冲区
        3. 合并后的文本用空格连接，保留原顺序和语义
        4. 最终所有句子均为短文本，不超过Edge TTS适配范围
        """
        if not original_sentences:
            return []
        # 获取配置参数（做非负整数验证）
        min_zh = max(1, self.min_zh_len.get())
        min_en = max(1, self.min_en_len.get())
        max_merge = max(2, self.max_merge_num.get())  # 至少合并2句
        self.min_zh_len.set(min_zh)
        self.min_en_len.set(min_en)
        self.max_merge_num.set(max_merge)

        merged_sentences = []
        current_buffer = []  # 合并缓冲区
        zh_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u{20000}-\u{2a6df}]', re.UNICODE)

        for sent in original_sentences:
            if not sent.strip():
                continue
            text_type = self.judge_text_type(sent)
            # 计算有效长度（中文按汉字数，英文按字符数，排除空格）
            if text_type == "zh":
                sent_len = len(zh_pattern.findall(sent))  # 纯汉字数
                threshold = min_zh
            else:
                sent_len = len(sent.replace(" ", ""))  # 英文排除空格后的字符数
                threshold = min_en

            # 规则1：长句 → 先合并缓冲区（若有），再将长句加入结果
            if sent_len >= threshold:
                if current_buffer:
                    merged = " ".join(current_buffer)
                    merged_sentences.append(merged)
                    self.log(f"[合句] 合并{len(current_buffer)}个短句：{merged[:50]}...")
                    current_buffer = []
                merged_sentences.append(sent)
            # 规则2：短句 → 加入缓冲区，若缓冲区达最大数则合并
            else:
                current_buffer.append(sent)
                if len(current_buffer) >= max_merge:
                    merged = " ".join(current_buffer)
                    merged_sentences.append(merged)
                    self.log(f"[合句] 达到最大合并数{max_merge}，合并：{merged[:50]}...")
                    current_buffer = []

        # 规则3：遍历结束后，合并缓冲区剩余的短句
        if current_buffer:
            merged = " ".join(current_buffer)
            merged_sentences.append(merged)
            self.log(f"[合句] 合并剩余{len(current_buffer)}个短句：{merged[:50]}...")

        return merged_sentences

    # 音色筛选函数
    def filter_voices(self, *args):
        """实时过滤音色列表，支持关键词：语言、性别、名称"""
        keyword = self.voice_filter_var.get().strip().lower()
        if not keyword:
            self.filtered_voices = self.available_voices
        else:
            self.filtered_voices = [
                voice for voice in self.available_voices
                if keyword in voice.lower()
            ]
        self.voice_combobox["values"] = self.filtered_voices
        self.log(f"音色筛选：关键词「{keyword}」，匹配 {len(self.filtered_voices)} 个音色")

    # 裁剪参数防抖+数值验证
    def on_crop_value_change(self, *args):
        """裁剪时长变化时更新采样点数（加防抖，避免重复触发）"""
        if self.crop_debounce:
            return
        self.crop_debounce = True

        # 确保输入为非负整数
        try:
            front = max(0, self.crop_front_ms.get())
            back = max(0, self.crop_back_ms.get())
            self.crop_front_ms.set(front)
            self.crop_back_ms.set(back)
        except:
            self.crop_front_ms.set(0)
            self.crop_back_ms.set(50)

        # 更新采样点数
        self.crop_front_points = int(self.sample_rate * (self.crop_front_ms.get() / 1000))
        self.crop_back_points = int(self.sample_rate * (self.crop_back_ms.get() / 1000))
        self.log(f"音频裁剪参数更新：前段 {self.crop_front_ms.get()}ms，后段 {self.crop_back_ms.get()}ms")

        # 0.1s后释放防抖，避免输入时重复触发
        self.after(100, lambda: setattr(self, 'crop_debounce', False))

    def crop_audio(self, audio_np):
        """音频前后段单独裁剪"""
        audio_len = len(audio_np)
        front_ms = self.crop_front_ms.get()
        back_ms = self.crop_back_ms.get()
        front_points = self.crop_front_points
        back_points = self.crop_back_points

        if front_ms == 0 and back_ms == 0:
            self.log(f"音频裁剪：未启用（时长 {audio_len / self.sample_rate * 1000:.0f}ms）")
            return audio_np

        if front_points + back_points >= audio_len:
            self.log(f"音频裁剪警告：裁剪总时长超过音频长度，跳过裁剪（音频{audio_len / self.sample_rate * 1000:.0f}ms）")
            return audio_np

        cropped_audio = audio_np[front_points: audio_len - back_points]
        cropped_len = len(cropped_audio)
        self.log(
            f"音频裁剪完成：原{audio_len / self.sample_rate * 1000:.0f}ms → 裁剪后{cropped_len / self.sample_rate * 1000:.0f}ms "
            f"（前段{front_ms}ms，后段{back_ms}ms）"
        )
        return cropped_audio

    # 基础参数标签更新
    def update_rate_label(self, value):
        self.rate_label.configure(text=f"{float(value):+.0f}%")

    def update_volume_label(self, value):
        self.volume_label.configure(text=f"{float(value):+.0f}%")

    def update_pitch_label(self, value):
        self.pitch_label.configure(text=f"{float(value):+.0f}Hz")

    def update_pause_label(self, value):
        ms = int(float(value))
        if ms < 0:
            self.pause_label.configure(text=f"当前间隔：{ms} ms（重叠{abs(ms)}ms）")
        elif ms == 0:
            self.pause_label.configure(text=f"当前间隔：{ms} ms（无缝衔接）")
        else:
            self.pause_label.configure(text=f"当前间隔：{ms} ms（停顿）")

    def update_input_label(self, *args):
        if self.mode_var.get() == "insert":
            self.input_label.configure(text="插入内容（下一个句子前，按 Enter 提交）：")
        else:
            self.input_label.configure(text="打断内容（立即插入并中断当前，按 Enter 提交）：")

    # 日志输出
    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full_msg = f"[{timestamp}] {msg}\n"
        self.log_text.configure(state="normal")
        if any(k in msg for k in ["错误", "失败", "警告", "异常"]):
            self.log_text.tag_configure("error", foreground="#ff6666")
            self.log_text.insert("end", full_msg, "error")
        else:
            self.log_text.insert("end", full_msg)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ========== 核心修改：JSON文件加载 - 增加\u转义符容错 + 精准错误定位 ==========
    def select_json_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            # 第一步：读取原始文本，强制UTF-8编码
            with open(path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            # 第二步：预处理修复不完整的Unicode转义符（解决incomplete escape \u错误）
            def fix_incomplete_u_escape(match):
                u_part = match.group(0)
                # 完整的\uXXXX是6个字符（\u + 4位十六进制），不足则补0
                if len(u_part) < 6:
                    fixed = u_part.ljust(6, '0')  # 补0到6位（如\u123 → \u1230）
                    # 若想直接删除不完整的\u，注释上一行，启用下一行：
                    # fixed = ""
                    self.log(f"[JSON修复] 不完整\u转义符：{u_part} → {fixed}")
                    return fixed
                else:
                    # 检查后4位是否为有效十六进制，无效则删除
                    hex_part = u_part[2:]
                    if re.match(r'^[0-9a-fA-F]{4}$', hex_part):
                        return u_part
                    else:
                        self.log(f"[JSON修复] 无效\u转义符：{u_part} → 已删除")
                        return ""

            # 正则匹配所有\u开头的不完整序列并修复
            processed_text = re.sub(r'\\u[0-9a-fA-F]{0,3}', fix_incomplete_u_escape, raw_text)
            # 修复单独的反斜杠（未转义）→ 改为双反斜杠
            processed_text = re.sub(r'(?<!\\)\\(?!u)', r'\\\\', processed_text)

            # 第三步：解析修复后的JSON
            data = json.loads(processed_text)

            # 第四步：清洗句子 + 自动合句
            self.original_sentences = [re.sub(r'\s+', ' ', item["text"]).strip()
                                       for item in data if isinstance(item.get("text"), str) and item["text"].strip()]
            original_count = len(self.original_sentences)
            self.file_label.configure(text=os.path.basename(path))
            self.log(f"JSON加载成功：共 {original_count} 条原始句子（已清洗特殊字符）")

            # 自动合并短句（若启用）
            if self.auto_merge_var.get() == 1:
                self.sentences = self.merge_short_sentences(self.original_sentences)
                merged_count = len(self.sentences)
                self.log(
                    f"自动合句完成：原{original_count}句 → 合并后{merged_count}句（减少{original_count - merged_count}句）")
            else:
                self.sentences = self.original_sentences
                self.log("未启用自动合句，使用原始句子列表")

            # 更新进度标签
            self.progress_label.configure(text=f"进度: 0 / {len(self.sentences)}    当前: -")

        except json.JSONDecodeError as e:
            # 精准定位错误位置（行/列 + 上下文）
            error_pos = e.pos
            error_line = raw_text[:error_pos].count('\n') + 1
            error_col = error_pos - (
                raw_text[:error_pos].rfind('\n') if raw_text[:error_pos].rfind('\n') != -1 else 0) - 1
            self.log(f"[JSON解析错误] {str(e)} → 错误位置：第{error_line}行，第{error_col}列（字符位置{error_pos}）")
            # 打印错误上下文（前后20字符）
            context_start = max(0, error_pos - 20)
            context_end = min(len(raw_text), error_pos + 20)
            self.log(f"错误上下文：{raw_text[context_start:context_end]}")
        except Exception as e:
            self.log(f"JSON 加载失败：{str(e)}")

    def select_subtitle_path(self):
        path = filedialog.asksaveasfilename(defaultextension=".srt", filetypes=[("SRT字幕文件", "*.srt")])
        if path:
            self.subtitle_path = path
            self.subtitle_path_entry.delete(0, "end")
            self.subtitle_path_entry.insert(0, path)

    # 音色列表加载
    def load_edge_tts_voices(self):
        def async_load():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                voices_manager = loop.run_until_complete(VoicesManager.create())
                raw_voices = voices_manager.find()
                self.available_voices = [
                    f"{v['ShortName']} ({v['Gender']}/{v['Locale']})"
                    for v in raw_voices
                ]
                loop.close()
                self.filter_voices()
                self.log(f"音色列表加载成功：共 {len(self.available_voices)} 个可用音色（支持实时筛选）")
            except Exception as e:
                self.log(f"音色列表加载失败：{str(e)}")

        threading.Thread(target=async_load, daemon=True).start()

    # Edge TTS 合成逻辑
    async def edge_tts_synthesize(self, text):
        if not text.strip():
            return None, None
        clean_text = re.sub(r'[^\x20-\x7E\u4e00-\u9fa5]', ' ', text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        voice_short_name = self.voice_var.get().split(" ")[0]
        rate = f"{self.rate_var.get():+.0f}%"
        volume = f"{self.volume_var.get():+.0f}%"
        pitch = f"{self.pitch_var.get():+.0f}Hz"

        audio_bytes = io.BytesIO()
        submaker = SubMaker()
        try:
            communicate = edge_tts.Communicate(
                text=clean_text, voice=voice_short_name, rate=rate, volume=volume, pitch=pitch,
                boundary="SentenceBoundary"
            )
            async with asyncio.timeout(10):
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes.write(chunk["data"])
                    elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                        submaker.feed(chunk)
            if audio_bytes.tell() == 0:
                self.log(f"合成警告：无音频数据返回（文本：{clean_text[:30]}...）")
                return None, None
            audio_bytes.seek(0)
            audio_np, sr = sf.read(audio_bytes)
            if sr != self.sample_rate:
                self.sample_rate = sr
                self.on_crop_value_change()
                self.log(f"采样率自动更新为：{sr} Hz，裁剪点数已同步")
            audio_np = self.crop_audio(audio_np)
            srt_content = submaker.get_srt() if self.save_subtitle_var.get() else None
            return audio_np, srt_content
        except asyncio.TimeoutError:
            self.log(f"合成失败：请求超时（文本：{clean_text[:30]}...）")
            return None, None
        except Exception as e:
            self.log(f"合成失败：{str(e)}（文本：{clean_text[:30]}...）")
            return None, None

    def synthesize_text(self, text, retry=1):
        """同步合成，带重试机制"""
        if not text.strip():
            return None, None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        audio_np = None
        srt_content = None
        for i in range(retry + 1):
            try:
                audio_np, srt_content = loop.run_until_complete(self.edge_tts_synthesize(text))
                if audio_np is not None:
                    break
                self.log(f"合成重试 {i + 1}/{retry + 1}...")
            except Exception as e:
                self.log(f"重试失败 {i + 1}：{str(e)}")
                continue

        if audio_np is None:
            return None, None

        # 音频后处理
        max_abs = np.max(np.abs(audio_np))
        if max_abs > 0:
            audio_np = audio_np / max_abs * 0.92
        audio_np = np.clip(audio_np, -1.0, 1.0)
        dither = np.random.triangular(-1, 0, 1, size=audio_np.shape) * (1 / 32768)
        audio_np += dither
        audio_int16 = (audio_np * 32767).astype(np.int16)
        return audio_int16, srt_content

    # 插入/打断逻辑
    def submit_insert(self, event=None):
        content = self.input_entry.get().strip()
        self.input_entry.delete(0, "end")
        if not content or not self.is_running:
            return
        if self.mode_var.get() == "interrupt":
            self.interrupt_event.set()
            self.interrupt_content = content
            self.log(f"[打断] 插入内容：{content[:50]}...")
        else:
            temp = []
            while not self.task_queue.empty():
                temp.append(self.task_queue.get())
            self.task_queue.put(content)
            for item in temp:
                self.task_queue.put(item)
            self.log(f"[插入] 已加入队列头部：{content[:50]}...")

    # 开始朗读
    def start_reading(self):
        if not self.sentences:
            messagebox.showwarning("提示", "请先选择 JSON 文件")
            return
        if self.save_subtitle_var.get():
            self.submaker = SubMaker()
        self.is_running = True
        self.synthesis_running = True
        self.current_index = 0
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        # 清空队列
        while not self.task_queue.empty():
            self.task_queue.get()
        while not self.audio_buffer_queue.empty():
            self.audio_buffer_queue.get()
        # 填充任务队列
        for s in self.sentences:
            self.task_queue.put(s)
        # 预合成最小值设为4（避免设太小）
        self.max_prefetch = self.prefetch_var.get() or 4
        # 启动线程
        self.synthesis_thread = threading.Thread(target=self.synthesis_worker, daemon=True)
        self.synthesis_thread.start()
        threading.Thread(target=self.speaker_thread, daemon=True).start()
        # 日志输出配置
        voice_short_name = self.voice_var.get().split(" ")[0]
        pause_ms = self.pause_var.get()
        pause_desc = f"重叠{abs(pause_ms)}ms" if pause_ms < 0 else f"停顿{pause_ms}ms" if pause_ms > 0 else "无缝衔接"
        self.log(f"开始朗读（预合成{self.max_prefetch}句，间隔{pause_ms}ms({pause_desc})）")
        self.log(
            f"当前配置：音色={voice_short_name} | 语速{self.rate_var.get():+.0f}% | 音量{self.volume_var.get():+.0f}% | 音调{self.pitch_var.get():+.0f}Hz")
        self.log(
            f"音频裁剪：前段{self.crop_front_ms.get()}ms，后段{self.crop_back_ms.get()}ms（采样率{self.sample_rate}Hz）")
        if self.save_subtitle_var.get():
            self.log(f"字幕生成：启用，将保存至 {self.subtitle_path}")
        else:
            self.log(f"字幕生成：已关闭（可在配置区勾选启用）")

    # 停止朗读
    def stop_reading(self):
        self.is_running = False
        self.synthesis_running = False
        self.interrupt_event.set()
        # 停止所有音频流
        for stream in self.audio_streams:
            try:
                stream.abort()
                stream.stop()
                stream.close()
            except:
                pass
        self.audio_streams.clear()
        # 重置按钮和进度
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress_label.configure(text=f"进度: 0 / {len(self.sentences)}    当前: -")
        # 保存字幕
        if self.save_subtitle_var.get() and self.submaker:
            try:
                with open(self.subtitle_path, "w", encoding="utf-8") as f:
                    f.write(self.submaker.get_srt())
                self.log(f"字幕已保存至：{self.subtitle_path}")
            except Exception as e:
                self.log(f"字幕保存失败：{str(e)}")
        self.log("已停止朗读")

    # 预合成线程：加快合成速度（0.1s→0.05s）
    def synthesis_worker(self):
        while self.synthesis_running and self.is_running:
            if not self.task_queue.empty() and self.audio_buffer_queue.qsize() < self.max_prefetch:
                sentence = self.task_queue.get()
                self.log(f"[预合成 {self.audio_buffer_queue.qsize() + 1}/{self.max_prefetch}] {sentence[:50]}...")
                with self.model_lock:
                    audio_data, srt_content = self.synthesize_text(sentence)
                if audio_data is not None:
                    self.audio_buffer_queue.put((sentence, audio_data, srt_content))
                    self.log(f"[缓冲更新] 剩余预合成：{self.audio_buffer_queue.qsize()} 句")
                    if self.save_subtitle_var.get() and srt_content:
                        self.submaker.feed_raw(srt_content)
                else:
                    self.log(f"[预合成失败] 跳过句子：{sentence[:30]}...")
                time.sleep(0.05)  # 加快合成速度，减少等待
            else:
                time.sleep(0.05)

    # 播放音频：延迟打印日志，优先启动播放流
    def play_audio_data(self, audio_data: np.ndarray, is_interrupt=False):
        if len(audio_data) == 0:
            return None
        audio_duration_ms = len(audio_data) / self.sample_rate * 1000
        self.current_audio_duration = len(audio_data)
        start_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # 延迟0.01s打印日志，让播放流先启动，避免日志阻塞
        self.after(10, lambda: self.log(
            f"[播放开始 @ {start_time}] 裁剪后时长：{audio_duration_ms:.0f}ms | 缓冲剩余：{self.audio_buffer_queue.qsize()} 句"
        ))

        audio_data_ref = audio_data.copy()
        self.audio_playback_finished.clear()

        def callback(outdata, frames, time_info, status):
            nonlocal audio_data_ref
            if self.interrupt_event.is_set() and not is_interrupt:
                self.audio_playback_finished.set()
                raise sd.CallbackAbort
            chunk_size = min(len(audio_data_ref), frames)
            outdata[:chunk_size, 0] = audio_data_ref[:chunk_size]
            outdata[chunk_size:, 0] = 0
            audio_data_ref = audio_data_ref[chunk_size:]
            if len(audio_data_ref) == 0:
                self.audio_playback_finished.set()
                raise sd.CallbackStop

        stream = sd.OutputStream(
            samplerate=self.sample_rate, channels=1, dtype='int16',
            callback=callback, blocksize=16384
        )
        try:
            stream.start()
            self.audio_streams.append(stream)
            return stream
        except Exception as e:
            self.log(f"播放异常：{str(e)}")
            return None

    # 播放等待逻辑：简化冗余，精准重叠
    def wait_for_playback(self, stream, overlap_ms=0):
        """等待播放完成（优化后：无冗余等待，精准重叠）"""
        if stream is None:
            return
        audio_duration_ms = self.current_audio_duration / self.sample_rate * 1000
        wait_ms = max(0, audio_duration_ms + overlap_ms)
        # 精准等待，去掉冗余循环检查
        time.sleep(wait_ms / 1000)
        # 非阻塞清理流，下一句可直接启动
        try:
            if stream in self.audio_streams:
                self.audio_streams.remove(stream)
            stream.stop()
            stream.close()
        except:
            pass

    # 即时合成播放
    def synthesize_and_play(self, text: str, is_interrupt=False):
        if not text.strip():
            return
        self.log(f"[{'打断' if is_interrupt else '即时'}朗读] {text[:70]}{'...' if len(text) > 70 else ''}")
        with self.model_lock:
            audio_data, srt_content = self.synthesize_text(text)
        if audio_data is not None:
            stream = self.play_audio_data(audio_data, is_interrupt=is_interrupt)
            self.wait_for_playback(stream)
            if self.save_subtitle_var.get() and srt_content:
                self.submaker.feed_raw(srt_content)
        else:
            self.log(f"[合成失败] 无法播放：{text[:30]}...")

    # 播放线程
    def speaker_thread(self):
        while self.is_running:
            # 处理打断请求
            if self.interrupt_content is not None and self.mode_var.get() == "interrupt":
                while not self.audio_buffer_queue.empty():
                    self.audio_buffer_queue.get()
                for stream in self.audio_streams:
                    try:
                        stream.abort()
                    except:
                        pass
                self.audio_streams.clear()
                self.synthesize_and_play(self.interrupt_content, is_interrupt=True)
                self.interrupt_content = None
                remaining = self.sentences[self.current_index:]
                while not self.task_queue.empty():
                    self.task_queue.get()
                for s in remaining:
                    self.task_queue.put(s)
            # 正常播放
            elif not self.audio_buffer_queue.empty():
                sentence, audio_data, srt_content = self.audio_buffer_queue.get()
                if audio_data is not None:
                    try:
                        pause_ms = self.pause_var.get()
                        stream = self.play_audio_data(audio_data, is_interrupt=False)
                        self.wait_for_playback(stream, overlap_ms=pause_ms)
                        self.current_index += 1
                        show_text = sentence[:25] + "..." if len(sentence) > 25 else sentence
                        self.progress_label.configure(
                            text=f"进度: {self.current_index} / {len(self.sentences)}    当前: {show_text}"
                        )
                    except Exception as e:
                        self.log(f"播放线程异常：{str(e)}")
                else:
                    self.log("[跳过] 合成失败的句子")
            else:
                time.sleep(0.05)
        # 朗读完成
        if self.current_index >= len(self.sentences) and self.is_running:
            while self.audio_streams:
                time.sleep(0.1)
            self.log("所有内容朗读完成！")
            if self.save_subtitle_var.get() and self.submaker:
                try:
                    with open(self.subtitle_path, "w", encoding="utf-8") as f:
                        f.write(self.submaker.get_srt())
                    self.log(f"最终字幕已保存至：{self.subtitle_path}")
                except Exception as e:
                    self.log(f"最终字幕保存失败：{str(e)}")
            messagebox.showinfo("完成", "朗读完毕！")
            self.stop_reading()


if __name__ == "__main__":
    # 安装依赖（执行以下命令）：
    # pip install edge-tts sounddevice ttkbootstrap soundfile numpy
    app = TTSApp()
    app.mainloop()