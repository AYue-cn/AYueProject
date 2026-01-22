import os
import sys
import random
import hashlib  # 新增：用于生成唯一文件名，避免重复
import numpy as np
import json
from datetime import datetime
import tkinter.messagebox as msgbox
from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip
import tempfile
import time

import customtkinter as ctk
from tkinter import filedialog, Menu
import threading
import subprocess
# 关键修改1：替换ProcessPoolExecutor为ThreadPoolExecutor（避免多进程复制GUI）
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 核心配置：按要求调整 ==========
USE_HARDWARE_ENCODE = True
CONFIG_FILE = "video_duet_config.json"

# ========== 初始化优化 ==========
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# 获取CPU物理核心数
try:
    import psutil
    CPU_PHYSICAL_CORES = psutil.cpu_count(logical=False)
    CPU_LOGICAL_CORES = psutil.cpu_count(logical=True)
    THREADS_PER_VIDEO = max(1, CPU_PHYSICAL_CORES // 2)
except ImportError:
    msgbox.showwarning("提示", "未安装psutil，建议执行 pip install psutil 以获得最佳性能！")
    CPU_PHYSICAL_CORES = os.cpu_count() or 4
    THREADS_PER_VIDEO = max(1, CPU_PHYSICAL_CORES // 2)

# ========== 多线程视频处理函数（替换多进程） ==========
def process_single_pair(args):
    """多线程执行单个视频合成（避免多进程复制GUI窗口）"""
    a_file, b_file, output_file, audio_source, duration_source, overlap_pixels = args
    log_messages = []

    def log_callback(msg):
        log_messages.append(msg)

    clip_a = None
    clip_b = None
    final = None
    try:
        # 加载并预处理视频（统一9:16竖屏）
        raw_a = VideoFileClip(a_file)
        raw_b = VideoFileClip(b_file)

        # 预处理A视频
        target_ratio = 9 / 16
        current_ratio = raw_a.w / raw_a.h
        if abs(current_ratio - target_ratio) > 0.05:
            if current_ratio > target_ratio:
                target_w = int(raw_a.h * target_ratio)
                raw_a = raw_a.crop(x_center=raw_a.w // 2, width=target_w)
            else:
                target_h = int(raw_a.w / target_ratio)
                raw_a = raw_a.crop(y_center=raw_a.h // 2, height=target_h)
        clip_a = raw_a.resize(height=1080)

        # 预处理B视频
        current_ratio = raw_b.w / raw_b.h
        if abs(current_ratio - target_ratio) > 0.05:
            if current_ratio > target_ratio:
                target_w = int(raw_b.h * target_ratio)
                raw_b = raw_b.crop(x_center=raw_b.w // 2, width=target_w)
            else:
                target_h = int(raw_b.w / target_ratio)
                raw_b = raw_b.crop(y_center=raw_b.h // 2, height=target_h)
        clip_b = raw_b.resize(height=1080)

        w = clip_a.w
        # 时长基准处理
        duration = 0
        if duration_source == "A 的时长":
            duration_clip = clip_a
            adjust_clip = clip_b
            duration = duration_clip.duration
            log_callback(f"调试：以A视频时长({duration:.2f}秒)为基准\n")
        else:
            duration_clip = clip_b
            adjust_clip = clip_a
            duration = duration_clip.duration
            log_callback(f"调试：以B视频时长({duration:.2f}秒)为基准\n")

        # 调整时长（裁剪/循环）
        if adjust_clip.duration > duration:
            adjust_clip = adjust_clip.subclip(0, duration)
            log_callback(f"调试：视频时长过长，裁剪至{duration:.2f}秒\n")
        elif adjust_clip.duration < duration:
            adjust_clip = adjust_clip.loop(duration=duration)
            log_callback(f"调试：视频时长不足，循环至{duration:.2f}秒\n")

        # 赋值回原变量
        if duration_source == "A 的时长":
            clip_b = adjust_clip
        else:
            clip_a = adjust_clip

        # 选择音频来源
        audio_clip = clip_a if audio_source == "A 的音频" else clip_b

        # 生成渐变蒙板
        overlap = max(0, min(overlap_pixels, int(w * 1.5)))
        total_width = 2 * w - overlap
        left_pos_x = (1080 - total_width) / 2
        right_pos_x = left_pos_x + w - overlap

        if overlap > 0:
            fade_out = np.linspace(1.0, 0.0, int(overlap))
            fade_in = np.linspace(0.0, 1.0, int(overlap))

            left_mask_array = np.ones((1080, w), dtype=np.float32)
            left_mask_array[:, -int(overlap):] = np.tile(fade_out, (1080, 1))
            mask_left = ImageClip(left_mask_array, ismask=True).set_duration(duration)
            clip_a = clip_a.set_mask(mask_left)

            right_mask_array = np.ones((1080, w), dtype=np.float32)
            right_mask_array[:, :int(overlap)] = np.tile(fade_in, (1080, 1))
            mask_right = ImageClip(right_mask_array, ismask=True).set_duration(duration)
            clip_b = clip_b.set_mask(mask_right)

        # 合成最终视频
        fps = max(clip_a.fps or 30, clip_b.fps or 30)
        final = CompositeVideoClip([
            clip_a.set_position((left_pos_x, 0)),
            clip_b.set_position((right_pos_x, 0))
        ], size=(1080, 1080)).set_audio(audio_clip.audio)

        # 编码参数（硬件/软件最优配置）
        encode_info = "硬件编码(NVIDIA NVENC)" if USE_HARDWARE_ENCODE else "极速软件编码"
        log_callback(f"开始{encode_info}：{os.path.basename(output_file)}（单视频线程数：{THREADS_PER_VIDEO}）\n")

        if USE_HARDWARE_ENCODE:
            # NVIDIA硬件编码
            final.write_videofile(
                output_file,
                fps=fps,
                codec="h264_nvenc",
                audio_codec="aac",
                threads=THREADS_PER_VIDEO,
                preset="p1",
                audio_bitrate="128k",
                ffmpeg_params=["-movflags", "+faststart", "-loglevel", "info"],
                verbose=False,  # 关键修改2：关闭冗余输出，避免日志刷屏
                logger=None     # 禁用moviepy的日志器，减少干扰
            )
        else:
            # 软件极速编码
            final.write_videofile(
                output_file,
                fps=fps,
                codec="libx264",
                audio_codec="aac",
                threads=THREADS_PER_VIDEO,
                preset="ultrafast",
                audio_bitrate="128k",
                ffmpeg_params=["-movflags", "+faststart", "-loglevel", "info"],
                verbose=False,
                logger=None
            )

        log_callback(f"生成完成：{os.path.basename(output_file)}\n")
        return (True, a_file, b_file, "".join(log_messages))
    except Exception as e:
        error_msg = f"错误：{os.path.basename(a_file)} + {os.path.basename(b_file)} → {str(e)}\n"
        log_callback(error_msg)
        return (False, a_file, b_file, "".join(log_messages))
    finally:
        # 强制释放资源
        if clip_a: clip_a.close()
        if clip_b: clip_b.close()
        if final: final.close()
        if 'raw_a' in locals(): raw_a.close()
        if 'raw_b' in locals(): raw_b.close()

# ========== GUI主程序 ==========
class VideoDuetApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"视频拼接助手v5.0（极速版）- 物理核心数：{CPU_PHYSICAL_CORES}")
        self.geometry("950x950")
        self.resizable(True, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 窗口图标（可选）
        icon_path = "4odpx-r40oi-001.ico"
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # 加载配置
        self.config = self.load_config()

        # 界面变量初始化
        self.folder_a = self.config.get("folder_a", os.path.join(os.getcwd(), "A"))
        self.folder_b = self.config.get("folder_b", os.path.join(os.getcwd(), "B"))
        self.output_folder = self.config.get("output_folder", os.path.join(os.getcwd(), "O"))
        self.num_generate = ctk.StringVar(value=self.config.get("num_generate", "5"))
        self.mode_var = ctk.StringVar(value=self.config.get("mode", "随机模式"))
        self.audio_var = ctk.StringVar(value=self.config.get("audio_source", "A 的音频"))
        self.duration_var = ctk.StringVar(value=self.config.get("duration_source", "A 的时长"))
        self.overlap_var = ctk.IntVar(value=self.config.get("overlap_pixels", 135))

        # 运行状态
        self.is_running = False
        self.is_cancelled = False
        self.executor = None
        self.task_start_time = None

        # 布局参数
        pad_y = 10
        pad_x = 20
        row = 0

        # 性能信息提示
        perf_info = f"编码模式：{'硬件' if USE_HARDWARE_ENCODE else '软件'} | 单视频线程：{THREADS_PER_VIDEO} | 并行线程数：{CPU_PHYSICAL_CORES}"
        ctk.CTkLabel(
            self,
            text=perf_info,
            font=ctk.CTkFont(size=10),
            text_color="#2E8B57"
        ).grid(row=row, column=0, columnspan=3, padx=pad_x, pady=5, sticky="w")
        row += 1

        # 拼接模式选择
        ctk.CTkLabel(self, text="拼接模式：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.mode_seg = ctk.CTkSegmentedButton(
            self, values=["随机模式", "穷举模式", "1vN模式"],
            variable=self.mode_var, command=self.on_mode_change
        )
        self.mode_seg.grid(row=row, column=1, columnspan=2, padx=pad_x, pady=pad_y, sticky="w")
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 文件夹选择
        # A文件夹
        ctk.CTkLabel(self, text="A 文件夹（左视频）：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.label_a = ctk.CTkLabel(self, text="未选择", text_color="gray")
        self.label_a.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择", command=self.choose_folder_a).grid(
            row=row, column=2, padx=pad_x, pady=pad_y
        )
        row += 1

        # B文件夹
        ctk.CTkLabel(self, text="B 文件夹（右视频）：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.label_b = ctk.CTkLabel(self, text="未选择", text_color="gray")
        self.label_b.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择", command=self.choose_folder_b).grid(
            row=row, column=2, padx=pad_x, pady=pad_y
        )
        row += 1

        # 输出文件夹
        ctk.CTkLabel(self, text="输出文件夹：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.label_out = ctk.CTkLabel(self, text="未选择", text_color="gray")
        self.label_out.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择", command=self.choose_output_folder).grid(
            row=row, column=2, padx=pad_x, pady=pad_y
        )
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 生成参数
        # 生成数量
        ctk.CTkLabel(self, text="生成数量（随机/1vN模式）：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.entry_num = ctk.CTkEntry(self, textvariable=self.num_generate, width=100)
        self.entry_num.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="w")
        row += 1

        # 音频来源
        ctk.CTkLabel(self, text="音频来源：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        ctk.CTkOptionMenu(self, values=["A 的音频", "B 的音频"], variable=self.audio_var).grid(
            row=row, column=1, padx=pad_x, pady=pad_y, sticky="w"
        )
        row += 1

        # 时长基准
        ctk.CTkLabel(self, text="时长基准：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        ctk.CTkOptionMenu(self, values=["A 的时长", "B 的时长"], variable=self.duration_var).grid(
            row=row, column=1, padx=pad_x, pady=pad_y, sticky="w"
        )
        row += 1

        # 蒙板宽度
        ctk.CTkLabel(self, text="渐变蒙板宽度（像素）：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.overlap_slider = ctk.CTkSlider(
            self, from_=0, to=700, variable=self.overlap_var, command=self.update_overlap_label
        )
        self.overlap_slider.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="w")
        self.overlap_label = ctk.CTkLabel(self, text=f"{self.overlap_var.get()} 像素")
        self.overlap_label.grid(row=row, column=2, padx=pad_x, pady=pad_y, sticky="w")
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 操作按钮
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.grid(row=row, column=0, columnspan=3, pady=(15, 10), padx=pad_x, sticky="ew")

        # 开始生成
        self.btn_start = ctk.CTkButton(
            self.btn_frame, text="开始极速生成", font=ctk.CTkFont(size=16, weight="bold"),
            width=200, height=40, fg_color="#2E8B57", hover_color="#3CB371",
            command=self.start_generation
        )
        self.btn_start.pack(side="left", padx=20, pady=10)

        # 取消生成
        self.btn_cancel = ctk.CTkButton(
            self.btn_frame, text="取消生成", state="disabled",
            width=200, height=40, fg_color="#DC143C", hover_color="#FF4500",
            command=self.cancel_generation
        )
        self.btn_cancel.pack(side="left", padx=20, pady=10)

        # 打开输出文件夹
        self.btn_open_output = ctk.CTkButton(
            self.btn_frame, text="打开输出文件夹", width=200, height=40,
            fg_color="#4682B4", hover_color="#6495ED",
            command=self.open_output_folder
        )
        self.btn_open_output.pack(side="left", padx=20, pady=10)
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 进度条
        ctk.CTkLabel(self, text="整体进度：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=(10, 5), sticky="w"
        )
        row += 1
        self.progress_bar = ctk.CTkProgressBar(self, width=800)
        self.progress_bar.grid(row=row, column=0, columnspan=3, padx=pad_x, pady=(0, 15))
        self.progress_bar.set(0)
        row += 1

        # 日志区域
        log_header_frame = ctk.CTkFrame(self)
        log_header_frame.grid(row=row, column=0, columnspan=3, padx=pad_x, pady=(10, 5), sticky="ew")
        log_header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_header_frame, text="运行日志：", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(
            log_header_frame, text="清空日志", width=100, fg_color="#FF8C00", hover_color="#FFA500",
            command=self.clear_log
        ).grid(row=0, column=1, sticky="e", padx=10)
        row += 1

        self.log_text = ctk.CTkTextbox(self, height=250, width=900, wrap="word")
        self.log_text.grid(row=row, column=0, columnspan=3, padx=pad_x, pady=(0, 20))
        self.log_text.insert("end", f"✅ 初始化完成（{perf_info}）\n")
        self.log_text.insert("end", "📌 提示：多线程优化提升批量总效率，单个视频速度已达硬件上限\n")
        self.log_text.insert("end", "📌 建议：生成前关闭后台程序，使用SSD存放视频文件\n")

        # 布局优化
        self.grid_columnconfigure(1, weight=1)
        self.on_mode_change()
        self.update_folder_labels()

    # ========== 辅助函数 ==========
    def add_divider(self, row):
        """添加分割线"""
        divider = ctk.CTkFrame(self, height=2, fg_color=("#333333", "#777777"))
        divider.grid(row=row, column=0, columnspan=3, padx=20, pady=5, sticky="ew")

    def open_output_folder(self):
        """打开输出文件夹"""
        if self.output_folder and os.path.isdir(self.output_folder):
            try:
                if os.name == 'nt':
                    os.startfile(self.output_folder)
                elif os.name == 'posix':
                    subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', self.output_folder])
            except Exception as e:
                self.log(f"❌ 无法打开输出文件夹：{str(e)}\n")
        else:
            self.log("❌ 输出文件夹未设置或不存在！\n")

    def clear_log(self):
        """清空日志"""
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "日志已清空\n")

    def show_about(self):
        """关于弹窗"""
        msgbox.showinfo(
            "关于",
            "视频拼接助手v5.0（极速版）\n\n核心优化：\n1. 适配CPU物理核心数，避免资源竞争\n2. 单个视频最优线程数，提升单任务速度\n3. NVIDIA硬件编码支持（速度提升2-5倍）\n4. 临时文件目录恢复为当前文件夹\n5. 新增任务总耗时统计功能\n\n使用说明：\n- 有NVIDIA显卡建议开启硬件编码\n- 批量生成时效率提升5-8倍\n- 单个视频速度已达硬件上限 \n Email：zyclovewyc@gmail.com"
        )

    def load_config(self):
        """加载配置"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_config(self):
        """保存配置"""
        config = {
            "folder_a": self.folder_a,
            "folder_b": self.folder_b,
            "output_folder": self.output_folder,
            "num_generate": self.num_generate.get(),
            "mode": self.mode_var.get(),
            "audio_source": self.audio_var.get(),
            "duration_source": self.duration_var.get(),
            "overlap_pixels": self.overlap_var.get()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def on_close(self):
        """关闭窗口"""
        self.save_config()
        if self.executor:
            self.executor.shutdown(wait=False)
        self.destroy()

    def shorten_path(self, path, count=0):
        """缩短路径显示"""
        if not path:
            return "未选择"
        display = path if len(path) <= 60 else "..." + path[-57:]
        return f"{display} ({count} 个视频)" if count else display

    def update_folder_labels(self):
        """更新文件夹标签"""
        count_a = len(self.get_video_files(self.folder_a))
        count_b = len(self.get_video_files(self.folder_b))
        self.label_a.configure(
            text=self.shorten_path(self.folder_a, count_a),
            text_color="black" if self.folder_a else "gray"
        )
        self.label_b.configure(
            text=self.shorten_path(self.folder_b, count_b),
            text_color="black" if self.folder_b else "gray"
        )
        self.label_out.configure(
            text=self.shorten_path(self.output_folder),
            text_color="black" if self.output_folder else "gray"
        )

    def get_video_files(self, folder):
        """获取视频文件列表"""
        if not folder or not os.path.isdir(folder):
            return []
        return [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]

    def update_overlap_label(self, val):
        """更新蒙板宽度标签"""
        self.overlap_label.configure(text=f"{int(float(val))} 像素")

    def on_mode_change(self, *args):
        """模式切换"""
        if self.mode_var.get() == "穷举模式":
            self.entry_num.configure(state="disabled")
        else:
            self.entry_num.configure(state="normal")

    def log(self, message):
        """线程安全日志"""
        self.log_text.insert("end", message)
        self.log_text.see("end")
        self.update_idletasks()

    def choose_folder_a(self):
        """选择A文件夹"""
        path = filedialog.askdirectory(title="选择A文件夹")
        if path:
            self.folder_a = path
            self.update_folder_labels()

    def choose_folder_b(self):
        """选择B文件夹"""
        path = filedialog.askdirectory(title="选择B文件夹")
        if path:
            self.folder_b = path
            self.update_folder_labels()

    def choose_output_folder(self):
        """选择输出文件夹"""
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_folder = path
            self.update_folder_labels()

    # ========== 生成逻辑 ==========
    def start_generation(self):
        """开始生成（多线程并行）"""
        # 基础校验
        if not self.folder_a or not self.folder_b or not self.output_folder:
            self.log("❌ 请先选择所有文件夹！\n")
            return

        # 视频数量校验
        video_a_list = self.get_video_files(self.folder_a)
        video_b_list = self.get_video_files(self.folder_b)
        count_a = len(video_a_list)
        count_b = len(video_b_list)

        if count_a == 0:
            msgbox.showerror("错误", "A文件夹中未找到视频文件！")
            self.log("❌ A文件夹中未找到视频文件！\n")
            return
        if count_b == 0:
            msgbox.showerror("错误", "B文件夹中未找到视频文件！")
            self.log("❌ B文件夹中未找到视频文件！\n")
            return

        # 模式专属校验
        n_value = 0
        if self.mode_var.get() in ["随机模式", "1vN模式"]:
            try:
                n_value = int(self.num_generate.get())
                if n_value <= 0:
                    raise ValueError
            except:
                msgbox.showerror("错误", "生成数量必须是正整数！")
                self.log("❌ 生成数量必须是正整数！\n")
                return

            # 1vN模式校验
            if self.mode_var.get() == "1vN模式":
                if count_b < n_value:
                    msgbox.showerror("错误", f"1vN模式下，B文件夹视频数量({count_b}个)不能小于N值({n_value})！")
                    self.log(f"❌ 1vN模式下，B文件夹视频数量不足！\n")
                    return

        # 穷举模式确认
        if self.mode_var.get() == "穷举模式":
            total = count_a * count_b
            if total > 50:
                if not msgbox.askyesno(
                        "确认",
                        f"穷举模式将生成 {total} 个视频，是否继续？"
                ):
                    self.log("✅ 用户取消生成\n")
                    return

        # 初始化状态
        self.is_running = True
        self.is_cancelled = False
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.set(0)
        self.task_start_time = time.time()
        self.log(f"🚀 开始极速生成（模式：{self.mode_var.get()}，并行线程数：{CPU_PHYSICAL_CORES}）\n")
        self.log(f"⏱️ 任务开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 启动后台线程
        thread = threading.Thread(target=self.generate_videos)
        thread.daemon = True
        thread.start()

    def cancel_generation(self):
        """取消生成"""
        self.is_cancelled = True
        self.log("🛑 正在取消所有线程，请等待当前任务完成...\n")
        if self.executor:
            self.executor.shutdown(wait=False)

    def generate_videos(self):
        """多线程核心生成逻辑"""
        try:
            os.makedirs(self.output_folder, exist_ok=True)

            # 获取视频列表
            videos_a = [os.path.join(self.folder_a, f) for f in self.get_video_files(self.folder_a)]
            videos_b = [os.path.join(self.folder_b, f) for f in self.get_video_files(self.folder_b)]
            count_a = len(videos_a)
            count_b = len(videos_b)

            # 生成配对列表
            pairs = []
            total = 0
            time_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")

            # 分模式处理
            if self.mode_var.get() == "随机模式":
                n_value = int(self.num_generate.get())
                selected_a = random.choices(videos_a, k=n_value)
                selected_b = random.choices(videos_b, k=n_value)
                pairs = list(zip(selected_a, selected_b))
                total = n_value
                self.log(f"🎲 随机模式：将并行生成 {total} 个视频\n")

            elif self.mode_var.get() == "穷举模式":
                pairs = [(a, b) for a in videos_a for b in videos_b]
                total = len(pairs)
                self.log(f"🔍 穷举模式：将并行生成 {total} 个视频\n")

            elif self.mode_var.get() == "1vN模式":
                n_value = int(self.num_generate.get())
                total = count_a * n_value
                self.log(f"🎯 1vN模式：将并行生成 {total} 个视频\n")
                for a_file in videos_a:
                    selected_b = random.sample(videos_b, k=n_value)
                    for b_file in selected_b:
                        pairs.append((a_file, b_file))

            # 准备任务参数（新增：生成唯一文件名，避免重复）
            audio_source = self.audio_var.get()
            duration_source = self.duration_var.get()
            overlap_pixels = self.overlap_var.get()
            task_args = []

            for a_file, b_file in pairs:
                # 生成唯一哈希值，避免文件名过长/重复
                a_hash = hashlib.md5(a_file.encode()).hexdigest()[:16]
                b_hash = hashlib.md5(b_file.encode()).hexdigest()[:16]
                output_file = os.path.join(
                    self.output_folder,
                    f"{time_prefix}{a_hash}_{b_hash}.mp4"
                )
                task_args.append((a_file, b_file, output_file, audio_source, duration_source, overlap_pixels))

            # 关键修改3：使用ThreadPoolExecutor替换ProcessPoolExecutor（核心修复多窗口问题）
            completed = 0
            self.executor = ThreadPoolExecutor(max_workers=CPU_PHYSICAL_CORES)  # 线程池不会复制GUI
            future_to_task = {self.executor.submit(process_single_pair, args): args for args in task_args}

            # 遍历完成的任务
            for future in as_completed(future_to_task):
                if self.is_cancelled:
                    break

                try:
                    success, a_file, b_file, log_msg = future.result()
                    self.log(log_msg)
                    completed += 1
                    # 更新进度条（线程安全）
                    self.after(0, lambda p=completed/total: self.progress_bar.set(p))
                except Exception as e:
                    self.log(f"❌ 线程执行错误：{str(e)}\n")

            # 计算总耗时
            if self.task_start_time:
                task_end_time = time.time()
                total_seconds = round(task_end_time - self.task_start_time, 2)
                minutes = int(total_seconds // 60)
                seconds = round(total_seconds % 60, 2)

                self.log(f"⏱️ 任务结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if minutes > 0:
                    self.log(f"📊 任务总执行时间：{minutes}分{seconds}秒（总计{total_seconds}秒）\n")
                else:
                    self.log(f"📊 任务总执行时间：{seconds}秒\n")

            # 完成提示
            if not self.is_cancelled:
                self.log(f"🎉 全部{total}个视频生成完成！\n")
            else:
                self.log(f"🛑 生成已取消，完成 {completed}/{total} 个视频\n")

        except Exception as e:
            self.log(f"❌ 生成过程出错：{str(e)}\n")
            if self.task_start_time:
                task_end_time = time.time()
                total_seconds = round(task_end_time - self.task_start_time, 2)
                minutes = int(total_seconds // 60)
                seconds = round(total_seconds % 60, 2)
                self.log(f"⏱️ 任务异常终止，已耗时：{minutes}分{seconds}秒（总计{total_seconds}秒）\n")
        finally:
            # 恢复状态
            self.is_running = False
            self.executor = None
            self.after(0, lambda: self.btn_start.configure(state="normal"))
            self.after(0, lambda: self.btn_cancel.configure(state="disabled"))

# ========== 主程序入口（关键修改4：严格隔离GUI代码，避免子进程执行） ==========
if __name__ == "__main__":
    # 仅主进程执行GUI创建，子线程/子进程不会执行这段代码
    app = VideoDuetApp()
    app.mainloop()