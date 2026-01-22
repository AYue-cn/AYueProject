# 基础算法逻辑
# 可视化窗口优化，

import os
import random
import numpy as np
from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip

import customtkinter as ctk
from tkinter import filedialog
import threading

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def create_duet(a_path, b_path, output_path, log_callback, audio_source, duration_source, overlap_pixels):
    try:
        # 加载并缩放视频
        clip_a = VideoFileClip(a_path).resize(height=1080)
        clip_b = VideoFileClip(b_path).resize(height=1080)

        # 假设比例一致，取 A 的宽度（如果不同可取平均）
        w = clip_a.w

        # 时长基准
        if duration_source == "A 的时长":
            duration_clip = clip_a
            adjust_clip = clip_b
        else:
            duration_clip = clip_b
            adjust_clip = clip_a

        duration = duration_clip.duration

        # 调整另一个视频的时长
        if adjust_clip.duration > duration:
            adjust_clip = adjust_clip.subclip(0, duration)
        elif adjust_clip.duration < duration:
            adjust_clip = adjust_clip.loop(duration=duration)

        # 音频来源（独立选择）
        if audio_source == "A 的音频":
            audio_clip = clip_a
        else:
            audio_clip = clip_b

        # 重叠宽度控制（渐变蒙板宽度）
        overlap = max(0, min(overlap_pixels, int(w * 1.5)))  # 安全上限，避免极端值
        total_width = 2 * w - overlap
        left_pos_x = (1080 - total_width) / 2
        right_pos_x = left_pos_x + w - overlap

        # 创建蒙板（仅当有重叠时）
        if overlap > 0:
            # 左视频：右边渐隐
            left_mask_array = np.ones((1080, w), dtype=np.float32)
            fade_out = np.linspace(1.0, 0.0, int(overlap))
            left_mask_array[:, -int(overlap):] = np.tile(fade_out, (1080, 1))
            mask_left = ImageClip(left_mask_array, ismask=True).set_duration(duration)

            # 右视频：左边渐显
            right_mask_array = np.ones((1080, w), dtype=np.float32)
            fade_in = np.linspace(0.0, 1.0, int(overlap))
            right_mask_array[:, :int(overlap)] = np.tile(fade_in, (1080, 1))
            mask_right = ImageClip(right_mask_array, ismask=True).set_duration(duration)

            clip_a = clip_a.set_mask(mask_left)
            clip_b = clip_b.set_mask(mask_right)
        else:
            # 无渐变，直接全显示（硬拼接）
            clip_a = clip_a.set_mask(None)
            clip_b = clip_b.set_mask(None)

        # 合成
        final = CompositeVideoClip([
            clip_a.set_position((left_pos_x, 0)),
            clip_b.set_position((right_pos_x, 0))
        ], size=(1080, 1080))

        # 设置音频
        final = final.set_audio(audio_clip.audio)

        # 输出
        final.write_videofile(output_path, fps=duration_clip.fps, codec="libx264", audio_codec="aac",
                              threads=8, preset="medium")

        log_callback(f"生成完成：{output_path}\n")
    except Exception as e:
        log_callback(f"错误：{os.path.basename(a_path)} + {os.path.basename(b_path)} → {str(e)}\n")


class VideoDuetApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("阿岳视频拼接助手v2.0")
        self.geometry("900x750")
        self.resizable(True, False)

        # 当前脚本目录（用于默认文件夹）
        current_dir = os.getcwd()
        default_a = os.path.join(current_dir, "A")
        default_b = os.path.join(current_dir, "B")
        default_out = os.path.join(current_dir, "O")

        # 变量
        self.folder_a = default_a if os.path.isdir(default_a) else ""
        self.folder_b = default_b if os.path.isdir(default_b) else ""
        self.output_folder = default_out if os.path.isdir(default_out) else ""
        self.num_generate = ctk.StringVar(value="5")
        self.mode_var = ctk.StringVar(value="随机模式")
        self.audio_var = ctk.StringVar(value="A 的音频")
        self.duration_var = ctk.StringVar(value="A 的时长")
        self.overlap_var = ctk.IntVar(value=135)  # 默认约135像素（完美填充）

        # 布局
        pad_y = 12
        row = 0

        # 模式选择
        ctk.CTkLabel(self, text="拼接模式：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        self.mode_seg = ctk.CTkSegmentedButton(self, values=["随机模式", "穷举模式"],
                                               variable=self.mode_var, command=self.on_mode_change)
        self.mode_seg.grid(row=row, column=1, columnspan=2, padx=20, pady=pad_y, sticky="w")
        row += 1

        # A 文件夹
        ctk.CTkLabel(self, text="A 文件夹（左边视频）：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        self.label_a = ctk.CTkLabel(self, text=self.shorten_path(self.folder_a),
                                    text_color="white" if self.folder_a else "gray")
        self.label_a.grid(row=row, column=1, padx=20, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_folder_a).grid(row=row, column=2, padx=20,
                                                                                  pady=pad_y)
        row += 1

        # B 文件夹
        ctk.CTkLabel(self, text="B 文件夹（右边视频）：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        self.label_b = ctk.CTkLabel(self, text=self.shorten_path(self.folder_b),
                                    text_color="white" if self.folder_b else "gray")
        self.label_b.grid(row=row, column=1, padx=20, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_folder_b).grid(row=row, column=2, padx=20,
                                                                                  pady=pad_y)
        row += 1

        # 输出文件夹
        ctk.CTkLabel(self, text="输出文件夹：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        self.label_out = ctk.CTkLabel(self, text=self.shorten_path(self.output_folder),
                                      text_color="white" if self.output_folder else "gray")
        self.label_out.grid(row=row, column=1, padx=20, pady=pad_y, sticky="ew")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_output_folder).grid(row=row, column=2, padx=20,
                                                                                       pady=pad_y)
        row += 1

        # 生成数量（仅随机模式有效）
        ctk.CTkLabel(self, text="生成数量（随机模式）：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        self.entry_num = ctk.CTkEntry(self, textvariable=self.num_generate, width=100)
        self.entry_num.grid(row=row, column=1, padx=20, pady=pad_y, sticky="w")
        row += 1

        # 音频来源
        ctk.CTkLabel(self, text="音频来源：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        ctk.CTkOptionMenu(self, values=["A 的音频", "B 的音频"], variable=self.audio_var).grid(row=row, column=1,
                                                                                               padx=20, pady=pad_y,
                                                                                               sticky="w")
        row += 1

        # 时长基准
        ctk.CTkLabel(self, text="时长基准：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        ctk.CTkOptionMenu(self, values=["A 的时长", "B 的时长"], variable=self.duration_var).grid(row=row, column=1,
                                                                                                  padx=20, pady=pad_y,
                                                                                                  sticky="w")
        row += 1

        # 渐变蒙板宽度
        ctk.CTkLabel(self, text="渐变蒙板宽度（像素）：").grid(row=row, column=0, padx=20, pady=pad_y, sticky="w")
        self.overlap_slider = ctk.CTkSlider(self, from_=0, to=700, variable=self.overlap_var,
                                            command=self.update_overlap_label)
        self.overlap_slider.grid(row=row, column=1, padx=20, pady=pad_y, sticky="w")
        self.overlap_label = ctk.CTkLabel(self, text=f"{self.overlap_var.get()} 像素")
        self.overlap_label.grid(row=row, column=2, padx=20, pady=pad_y, sticky="w")
        row += 1

        # 开始按钮
        self.btn_start = ctk.CTkButton(self, text="开始生成", font=ctk.CTkFont(size=16, weight="bold"),
                                       height=40, command=self.start_generation)
        self.btn_start.grid(row=row, column=0, columnspan=3, pady=30)
        row += 1

        # 日志
        ctk.CTkLabel(self, text="运行日志：").grid(row=row, column=0, padx=20, pady=(10, 5), sticky="w")
        row += 1
        self.log_text = ctk.CTkTextbox(self, height=200, width=850, wrap="word")
        self.log_text.grid(row=row, column=0, columnspan=3, padx=20, pady=(0, 20))
        self.log_text.insert("end", "就绪。请选择文件夹并点击开始生成。\n")

        # 列权重（让路径标签扩展）
        self.grid_columnconfigure(1, weight=1)

        # 初始化模式状态
        self.on_mode_change()

    def shorten_path(self, path):
        if not path:
            return "未选择"
        if len(path) > 60:
            return "..." + path[-57:]
        return path

    def update_overlap_label(self, val):
        self.overlap_label.configure(text=f"{int(float(val))} 像素")

    def on_mode_change(self, *args):
        if self.mode_var.get() == "穷举模式":
            self.entry_num.configure(state="disabled")
        else:
            self.entry_num.configure(state="normal")

    def log(self, message):
        self.log_text.insert("end", message)
        self.log_text.see("end")
        self.update_idletasks()

    def choose_folder_a(self):
        path = filedialog.askdirectory(title="选择 A 文件夹")
        if path:
            self.folder_a = path
            self.label_a.configure(text=self.shorten_path(path), text_color="white")

    def choose_folder_b(self):
        path = filedialog.askdirectory(title="选择 B 文件夹")
        if path:
            self.folder_b = path
            self.label_b.configure(text=self.shorten_path(path), text_color="white")

    def choose_output_folder(self):
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_folder = path
            self.label_out.configure(text=self.shorten_path(path), text_color="white")

    def start_generation(self):
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

        self.btn_start.configure(state="disabled", text="正在生成中...")
        self.log(f"开始生成（模式：{self.mode_var.get()}）...\n")

        thread = threading.Thread(target=self.generate_videos)
        thread.daemon = True
        thread.start()

    def generate_videos(self):
        try:
            os.makedirs(self.output_folder, exist_ok=True)

            videos_a = [os.path.join(self.folder_a, f) for f in os.listdir(self.folder_a)
                        if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
            videos_b = [os.path.join(self.folder_b, f) for f in os.listdir(self.folder_b)
                        if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]

            if not videos_a or not videos_b:
                self.log("错误：A 或 B 文件夹中没有找到视频文件！\n")
                return

            # 根据模式准备列表
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

            # 公共参数
            audio_source = self.audio_var.get()
            duration_source = self.duration_var.get()
            overlap_pixels = self.overlap_var.get()

            for idx, (a_file, b_file) in enumerate(pairs):
                output_file = os.path.join(self.output_folder, f"duet_{idx + 1:04d}.mp4")
                self.log(f"正在生成 {idx + 1}/{total}：{os.path.basename(a_file)} + {os.path.basename(b_file)}\n")
                create_duet(a_file, b_file, output_file, self.log,
                            audio_source, duration_source, overlap_pixels)

            self.log("全部生成完成！\n")
        except Exception as e:
            self.log(f"生成过程出错：{str(e)}\n")
        finally:
            self.after(0, lambda: self.btn_start.configure(state="normal", text="开始生成"))


if __name__ == "__main__":
    app = VideoDuetApp()
    app.mainloop()
