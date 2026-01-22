import os
import sys
import random
import numpy as np
import json
from datetime import datetime
import tkinter.messagebox as msgbox
from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip

import customtkinter as ctk
from tkinter import filedialog, Menu
import threading
import subprocess

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "video_duet_config.json"


def preprocess_clip(clip):
    """预处理视频：统一视频尺寸为9:16竖屏（1080高），避免拉伸"""
    target_ratio = 9 / 16
    current_ratio = clip.w / clip.h
    if abs(current_ratio - target_ratio) > 0.05:
        if current_ratio > target_ratio:
            target_w = int(clip.h * target_ratio)
            clip = clip.crop(x_center=clip.w // 2, width=target_w)
        else:
            target_h = int(clip.w / target_ratio)
            clip = clip.crop(y_center=clip.h // 2, height=target_h)
    return clip.resize(height=1080)


def create_duet(a_path, b_path, output_path, log_callback, audio_source, duration_source, overlap_pixels):
    clip_a = None
    clip_b = None
    final = None
    try:
        # 加载原始视频
        raw_a = VideoFileClip(a_path)
        raw_b = VideoFileClip(b_path)

        # 预处理视频
        clip_a = preprocess_clip(raw_a)
        clip_b = preprocess_clip(raw_b)

        w = clip_a.w

        # ========== 核心修改1：记录需要调整的视频，并后续赋值回原变量 ==========
        duration = 0
        if duration_source == "A 的时长":
            duration_clip = clip_a
            adjust_clip = clip_b  # 要调整的是B视频
            audio_default = clip_a
            duration = duration_clip.duration
            log_callback(f"调试：以A视频时长({duration:.2f}秒)为基准，B视频原时长({adjust_clip.duration:.2f}秒)\n")
        else:
            duration_clip = clip_b
            adjust_clip = clip_a  # 要调整的是A视频
            audio_default = clip_b
            duration = duration_clip.duration
            log_callback(f"调试：以B视频时长({duration:.2f}秒)为基准，A视频原时长({adjust_clip.duration:.2f}秒)\n")

        # 调整时长（裁剪/循环）
        if adjust_clip.duration > duration:
            adjust_clip = adjust_clip.subclip(0, duration)
            log_callback(f"调试：视频时长过长，裁剪至{duration:.2f}秒\n")
        elif adjust_clip.duration < duration:
            # ========== 核心修改2：确保loop方法正确生效 ==========
            adjust_clip = adjust_clip.loop(duration=duration)  # loop会重复视频直到达到指定时长
            log_callback(f"调试：视频时长不足，循环至{duration:.2f}秒\n")

        # ========== 核心修改3：将调整后的视频赋值回原变量 ==========
        if duration_source == "A 的时长":
            clip_b = adjust_clip  # 把循环后的B视频赋值回原变量
        else:
            clip_a = adjust_clip  # 把循环后的A视频赋值回原变量

        # 选择音频来源
        audio_clip = clip_a if audio_source == "A 的音频" else clip_b

        # 计算重叠区域和位置
        overlap = max(0, min(overlap_pixels, int(w * 1.5)))
        total_width = 2 * w - overlap
        left_pos_x = (1080 - total_width) / 2
        right_pos_x = left_pos_x + w - overlap

        # 生成渐变蒙板
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

        # 确定合成帧率
        fps = max(clip_a.fps or 30, clip_b.fps or 30)

        # 合成最终视频（此时clip_a/clip_b已是调整后的版本）
        final = CompositeVideoClip([
            clip_a.set_position((left_pos_x, 0)),
            clip_b.set_position((right_pos_x, 0))
        ], size=(1080, 1080)).set_audio(audio_clip.audio)

        # 写入视频文件
        log_callback(f"开始写入视频文件：{os.path.basename(output_path)} （详细进度请查看控制台）\n")
        final.write_videofile(output_path, fps=fps, codec="libx264", audio_codec="aac",
                              threads=8, preset="medium")

        log_callback(f"生成完成：{output_path}\n")
    except Exception as e:
        log_callback(f"错误：{os.path.basename(a_path)} + {os.path.basename(b_path)} → {str(e)}\n")
    finally:
        if clip_a: clip_a.close()
        if clip_b: clip_b.close()
        if final: final.close()
        if 'raw_a' in locals(): raw_a.close()
        if 'raw_b' in locals(): raw_b.close()


class VideoDuetApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("阿岳视频拼接助手v3.0")
        self.geometry("950x900")
        self.resizable(True, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 窗口图标（可选）
        icon_path = "4odpx-r40oi-001.ico"
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # 顶部菜单栏
        menu_bar = Menu(self)
        help_menu = Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="关于", command=self.show_about)
        menu_bar.add_cascade(label="帮助", menu=help_menu)
        self.config(menu=menu_bar)

        # 加载配置
        self.config = self.load_config()

        # 默认文件夹路径
        current_dir = os.getcwd()
        default_a = os.path.join(current_dir, "A")
        default_b = os.path.join(current_dir, "B")
        default_out = os.path.join(current_dir, "O")

        # 界面变量初始化
        self.folder_a = self.config.get("folder_a", default_a if os.path.isdir(default_a) else "")
        self.folder_b = self.config.get("folder_b", default_b if os.path.isdir(default_b) else "")
        self.output_folder = self.config.get("output_folder", default_out if os.path.isdir(default_out) else "")
        self.num_generate = ctk.StringVar(value=self.config.get("num_generate", "5"))
        self.mode_var = ctk.StringVar(value=self.config.get("mode", "随机模式"))
        self.audio_var = ctk.StringVar(value=self.config.get("audio_source", "A 的音频"))
        self.duration_var = ctk.StringVar(value=self.config.get("duration_source", "A 的时长"))
        self.overlap_var = ctk.IntVar(value=self.config.get("overlap_pixels", 135))

        # 运行状态
        self.is_running = False
        self.is_cancelled = False

        # 布局参数
        pad_y = 10
        pad_x = 20
        row = 0

        # 拼接模式选择
        ctk.CTkLabel(self, text="拼接模式：", font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.mode_seg = ctk.CTkSegmentedButton(
            self, values=["随机模式", "穷举模式"],
            variable=self.mode_var, command=self.on_mode_change
        )
        self.mode_seg.grid(row=row, column=1, columnspan=2, padx=pad_x, pady=pad_y, sticky="w")
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 文件夹选择
        # A文件夹
        ctk.CTkLabel(self, text="A 文件夹（左边视频）：").grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.label_a = ctk.CTkLabel(self, text="", text_color="gray")
        self.label_a.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_folder_a).grid(
            row=row, column=2, padx=pad_x, pady=pad_y
        )
        row += 1

        # B文件夹
        ctk.CTkLabel(self, text="B 文件夹（右边视频）：").grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.label_b = ctk.CTkLabel(self, text="", text_color="gray")
        self.label_b.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_folder_b).grid(
            row=row, column=2, padx=pad_x, pady=pad_y
        )
        row += 1

        # 输出文件夹
        ctk.CTkLabel(self, text="输出文件夹：").grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.label_out = ctk.CTkLabel(self, text="", text_color="gray")
        self.label_out.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_output_folder).grid(
            row=row, column=2, padx=pad_x, pady=pad_y
        )
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 生成数量
        ctk.CTkLabel(self, text="生成数量（随机模式）：").grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.entry_num = ctk.CTkEntry(self, textvariable=self.num_generate, width=100)
        self.entry_num.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="w")
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 音频/时长/蒙板设置
        # 音频来源
        ctk.CTkLabel(self, text="音频来源：").grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        ctk.CTkOptionMenu(self, values=["A 的音频", "B 的音频"], variable=self.audio_var).grid(
            row=row, column=1, padx=pad_x, pady=pad_y, sticky="w"
        )
        row += 1

        # 时长基准
        ctk.CTkLabel(self, text="时长基准：").grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        ctk.CTkOptionMenu(self, values=["A 的时长", "B 的时长"], variable=self.duration_var).grid(
            row=row, column=1, padx=pad_x, pady=pad_y, sticky="w"
        )
        row += 1

        # 渐变蒙板宽度
        ctk.CTkLabel(self, text="渐变蒙板宽度（像素）：").grid(
            row=row, column=0, padx=pad_x, pady=pad_y, sticky="w"
        )
        self.overlap_slider = ctk.CTkSlider(
            self, from_=0, to=700, variable=self.overlap_var,
            command=self.update_overlap_label
        )
        self.overlap_slider.grid(row=row, column=1, padx=pad_x, pady=pad_y, sticky="w")
        self.overlap_label = ctk.CTkLabel(self, text=f"{self.overlap_var.get()} 像素")
        self.overlap_label.grid(row=row, column=2, padx=pad_x, pady=pad_y, sticky="w")
        row += 1

        # 分割线
        self.add_divider(row)
        row += 1

        # 按钮区域
        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.grid(row=row, column=0, columnspan=3, pady=(15, 10), padx=pad_x, sticky="ew")

        # 开始生成按钮
        self.btn_start = ctk.CTkButton(
            self.btn_frame, text="开始生成", font=ctk.CTkFont(size=16, weight="bold"),
            width=200, height=40, fg_color="#2E8B57", hover_color="#3CB371",
            command=self.start_generation
        )
        self.btn_start.pack(side="left", padx=20, pady=10)

        # 取消生成按钮
        self.btn_cancel = ctk.CTkButton(
            self.btn_frame, text="取消生成", state="disabled",
            width=200, height=40, fg_color="#DC143C", hover_color="#FF4500",
            command=self.cancel_generation
        )
        self.btn_cancel.pack(side="left", padx=20, pady=10)

        # 打开输出文件夹按钮
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

        # 分割线
        self.add_divider(row)
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

        self.log_text = ctk.CTkTextbox(self, height=220, width=900, wrap="word")
        self.log_text.grid(row=row, column=0, columnspan=3, padx=pad_x, pady=(0, 20))
        self.log_text.insert("end", "就绪。请选择文件夹并点击开始生成。\n")
        self.log_text.insert("end", "注：单个视频的详细写入进度会打印在控制台（运行脚本时可见）。\n")

        # 布局优化
        self.grid_columnconfigure(1, weight=1)
        self.on_mode_change()
        self.update_folder_labels()

    def add_divider(self, row):
        """添加横向分割线"""
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
                self.log(f"无法打开输出文件夹：{str(e)}\n")
        else:
            self.log("错误：输出文件夹未设置或不存在！\n")

    def clear_log(self):
        """清空日志"""
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "日志已清空。\n")

    def show_about(self):
        """显示关于对话框"""
        msgbox.showinfo(
            "关于",
            "阿岳视频拼接助手v3.0\n\n作者：阿岳\nEmail：zyclovewyc@gmail.com\n版本：3.0\n功能：左右渐变蒙板拼接短视频\n支持随机/穷举模式、音频/时长选择、渐变宽度调节等\n\n感谢使用！"
        )

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_config(self):
        """保存配置文件"""
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
        """窗口关闭回调"""
        self.save_config()
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
        """获取文件夹中的视频文件"""
        if not folder or not os.path.isdir(folder):
            return []
        return [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]

    def update_overlap_label(self, val):
        """更新蒙板宽度标签"""
        self.overlap_label.configure(text=f"{int(float(val))} 像素")

    def on_mode_change(self, *args):
        """模式切换回调"""
        if self.mode_var.get() == "穷举模式":
            self.entry_num.configure(state="disabled")
        else:
            self.entry_num.configure(state="normal")

    def log(self, message):
        """日志写入"""
        self.log_text.insert("end", message)
        self.log_text.see("end")
        self.update_idletasks()

    def choose_folder_a(self):
        """选择A文件夹"""
        path = filedialog.askdirectory(title="选择 A 文件夹")
        if path:
            self.folder_a = path
            self.update_folder_labels()

    def choose_folder_b(self):
        """选择B文件夹"""
        path = filedialog.askdirectory(title="选择 B 文件夹")
        if path:
            self.folder_b = path
            self.update_folder_labels()

    def choose_output_folder(self):
        """选择输出文件夹"""
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_folder = path
            self.update_folder_labels()

    def start_generation(self):
        """开始生成视频"""
        if not self.folder_a or not self.folder_b or not self.output_folder:
            self.log("错误：请先选择所有文件夹！\n")
            return

        if self.mode_var.get() == "随机模式":
            try:
                num = int(self.num_generate.get())
                if num <= 0:
                    raise ValueError
            except:
                self.log("错误：生成数量必须是正整数！\n")
                return

        # 穷举模式数量确认
        videos_a_temp = self.get_video_files(self.folder_a)
        videos_b_temp = self.get_video_files(self.folder_b)
        if self.mode_var.get() == "穷举模式":
            total = len(videos_a_temp) * len(videos_b_temp)
            if total > 50:
                if not msgbox.askyesno(
                        "确认生成数量",
                        f"穷举模式将生成 {total} 个视频，可能需要很长时间。\n\n是否继续？"
                ):
                    self.log("用户取消生成。\n")
                    return

        # 初始化状态
        self.is_running = True
        self.is_cancelled = False
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.set(0)
        self.log(f"开始生成（模式：{self.mode_var.get()}）...\n")

        # 启动后台线程
        thread = threading.Thread(target=self.generate_videos)
        thread.daemon = True
        thread.start()

    def cancel_generation(self):
        """取消生成"""
        self.is_cancelled = True
        self.log("正在取消，请等待当前视频完成...\n")

    def generate_videos(self):
        """后台生成视频"""
        try:
            os.makedirs(self.output_folder, exist_ok=True)

            videos_a = [os.path.join(self.folder_a, f) for f in self.get_video_files(self.folder_a)]
            videos_b = [os.path.join(self.folder_b, f) for f in self.get_video_files(self.folder_b)]

            if not videos_a or not videos_b:
                self.log("错误：A 或 B 文件夹中没有找到视频文件！\n")
                return

            time_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")

            if self.mode_var.get() == "随机模式":
                num = int(self.num_generate.get())
                selected_a = random.choices(videos_a, k=num)
                selected_b = random.choices(videos_b, k=num)
                pairs = list(zip(selected_a, selected_b))
                total = num
                self.log(f"随机模式：将生成 {total} 个视频\n")
            else:
                pairs = [(a, b) for a in videos_a for b in videos_b]
                total = len(pairs)
                self.log(f"穷举模式：将生成 {total} 个视频（{len(videos_a)} × {len(videos_b)}）\n")

            audio_source = self.audio_var.get()
            duration_source = self.duration_var.get()
            overlap_pixels = self.overlap_var.get()

            for idx, (a_file, b_file) in enumerate(pairs):
                if self.is_cancelled:
                    self.log("生成已取消！\n")
                    break

                a_name = os.path.basename(a_file)[:-4]
                b_name = os.path.basename(b_file)[:-4]
                output_file = os.path.join(
                    self.output_folder,
                    f"{time_prefix}{a_name}_{b_name}.mp4"
                )

                self.log(f"正在生成 {idx + 1}/{total}：{a_name} + {b_name}\n")
                create_duet(
                    a_file, b_file, output_file, self.log,
                    audio_source, duration_source, overlap_pixels
                )

                progress = (idx + 1) / total
                self.after(0, lambda p=progress: self.progress_bar.set(p))

            if not self.is_cancelled:
                self.log("全部生成完成！\n")
        except Exception as e:
            self.log(f"生成过程出错：{str(e)}\n")
        finally:
            self.is_running = False
            self.after(0, lambda: self.btn_start.configure(state="normal"))
            self.after(0, lambda: self.btn_cancel.configure(state="disabled"))


if __name__ == "__main__":
    app = VideoDuetApp()
    app.mainloop()