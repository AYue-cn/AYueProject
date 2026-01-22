# 基础算法逻辑
import os
import random
import numpy as np
from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip

import customtkinter as ctk
from tkinter import filedialog
import threading
import tkinter as tk

# 设置自定义主题（可选）
ctk.set_appearance_mode("System")  # "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


def create_duet(a_path, b_path, output_path, log_callback):
    try:
        # 加载视频
        clip_a = VideoFileClip(a_path).resize(height=1080)
        clip_b = VideoFileClip(b_path).resize(height=1080)

        duration = clip_a.duration

        # 处理 B 时长：长则裁剪，短则循环
        if clip_b.duration > duration:
            clip_b = clip_b.subclip(0, duration)
        else:
            clip_b = clip_b.loop(duration=duration)

        # 获取宽度
        w = clip_a.w
        if clip_b.w != w:
            clip_b = clip_b.resize(width=w)

        # 计算重叠区
        pos_right = 1080 - w
        overlap = w - pos_right

        # 创建左蒙板（右边渐隐）
        left_mask_array = np.ones((1080, w), dtype=np.float32)
        if overlap > 0:
            fade_out = np.linspace(1.0, 0.0, int(overlap))
            left_mask_array[:, -int(overlap):] = np.tile(fade_out, (1080, 1))

        mask_left = ImageClip(left_mask_array, ismask=True).set_duration(duration)

        # 创建右蒙板（左边渐显）
        right_mask_array = np.ones((1080, w), dtype=np.float32)
        if overlap > 0:
            fade_in = np.linspace(0.0, 1.0, int(overlap))
            right_mask_array[:, :int(overlap)] = np.tile(fade_in, (1080, 1))

        mask_right = ImageClip(right_mask_array, ismask=True).set_duration(duration)

        # 应用蒙板
        clip_a = clip_a.set_mask(mask_left)
        clip_b = clip_b.set_mask(mask_right)

        # 合成最终视频
        final = CompositeVideoClip([
            clip_a.set_position((0, 0)),
            clip_b.set_position((pos_right, 0))
        ], size=(1080, 1080))

        # 音频使用 A 的
        final = final.set_audio(clip_a.audio)

        # 输出
        final.write_videofile(output_path, fps=clip_a.fps, codec="libx264", audio_codec="aac", threads=8,
                              preset="medium")

        log_callback(f"生成完成：{output_path}\n")
    except Exception as e:
        log_callback(f"错误：处理 {os.path.basename(a_path)} + {os.path.basename(b_path)} 时出错：{str(e)}\n")


class VideoDuetApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("短视频平行拼接工具（左右渐变蒙板）")
        self.geometry("1920x500")
        self.resizable(False, False)

        # 变量
        self.folder_a = ""
        self.folder_b = ""
        self.output_folder = ""
        self.num_generate = ctk.StringVar(value="5")

        # ===== 布局 =====
        padding_y = 15

        # A 文件夹
        ctk.CTkLabel(self, text="A 文件夹（左边视频）：").grid(row=0, column=0, padx=20, pady=padding_y, sticky="w")
        self.label_a = ctk.CTkLabel(self, text="未选择", text_color="gray")
        self.label_a.grid(row=0, column=1, padx=20, pady=padding_y, sticky="w")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_folder_a).grid(row=0, column=2, padx=20,
                                                                                  pady=padding_y)

        # B 文件夹
        ctk.CTkLabel(self, text="B 文件夹（右边视频）：").grid(row=1, column=0, padx=20, pady=padding_y, sticky="w")
        self.label_b = ctk.CTkLabel(self, text="未选择", text_color="gray")
        self.label_b.grid(row=1, column=1, padx=20, pady=padding_y, sticky="w")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_folder_b).grid(row=1, column=2, padx=20,
                                                                                  pady=padding_y)

        # 输出文件夹
        ctk.CTkLabel(self, text="输出文件夹：").grid(row=2, column=0, padx=20, pady=padding_y, sticky="w")
        self.label_out = ctk.CTkLabel(self, text="未选择", text_color="gray")
        self.label_out.grid(row=2, column=1, padx=20, pady=padding_y, sticky="w")
        ctk.CTkButton(self, text="选择文件夹", command=self.choose_output_folder).grid(row=2, column=2, padx=20,
                                                                                       pady=padding_y)

        # 生成数量
        ctk.CTkLabel(self, text="生成视频数量：").grid(row=3, column=0, padx=20, pady=padding_y, sticky="w")
        entry_num = ctk.CTkEntry(self, textvariable=self.num_generate, width=100)
        entry_num.grid(row=3, column=1, padx=20, pady=padding_y, sticky="w")

        # 开始按钮
        self.btn_start = ctk.CTkButton(self, text="开始生成", font=ctk.CTkFont(size=16, weight="bold"), height=40,
                                       command=self.start_generation)
        self.btn_start.grid(row=4, column=0, columnspan=3, pady=30)

        # 日志框
        ctk.CTkLabel(self, text="运行日志：").grid(row=5, column=0, padx=20, pady=(10, 5), sticky="w")
        self.log_text = ctk.CTkTextbox(self, height=150, width=650)
        self.log_text.grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 20))
        self.log_text.insert("end", "就绪。请选择文件夹并点击开始生成。\n")

    def log(self, message):
        self.log_text.insert("end", message)
        self.log_text.see("end")
        self.update_idletasks()

    def choose_folder_a(self):
        path = filedialog.askdirectory(title="选择 A 文件夹")
        if path:
            self.folder_a = path
            self.label_a.configure(text=path, text_color="white")

    def choose_folder_b(self):
        path = filedialog.askdirectory(title="选择 B 文件夹")
        if path:
            self.folder_b = path
            self.label_b.configure(text=path, text_color="white")

    def choose_output_folder(self):
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_folder = path
            self.label_out.configure(text=path, text_color="white")

    def start_generation(self):
        # 校验
        if not self.folder_a or not self.folder_b or not self.output_folder:
            self.log("错误：请先选择所有文件夹！\n")
            return
        try:
            num = int(self.num_generate.get())
            if num <= 0:
                raise ValueError
        except:
            self.log("错误：生成数量必须是正整数！\n")
            return

        # 禁用按钮，防止重复点击
        self.btn_start.configure(state="disabled", text="正在生成中...")
        self.log(f"开始生成 {num} 个视频...\n")

        # 用线程运行，避免界面卡死
        thread = threading.Thread(target=self.generate_videos, args=(num,))
        thread.daemon = True
        thread.start()

    def generate_videos(self, num_to_generate):
        try:
            os.makedirs(self.output_folder, exist_ok=True)

            videos_a = [os.path.join(self.folder_a, f) for f in os.listdir(self.folder_a)
                        if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
            videos_b = [os.path.join(self.folder_b, f) for f in os.listdir(self.folder_b)
                        if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]

            if not videos_a or not videos_b:
                self.log("错误：A 或 B 文件夹中没有找到视频文件！\n")
                return

            selected_a = random.choices(videos_a, k=num_to_generate)
            selected_b = random.choices(videos_b, k=num_to_generate)

            for i in range(num_to_generate):
                a_file = selected_a[i]
                b_file = selected_b[i]
                output_file = os.path.join(self.output_folder, f"duet_{i + 1:02d}.mp4")
                self.log(
                    f"正在生成第 {i + 1}/{num_to_generate} 个：{os.path.basename(a_file)} + {os.path.basename(b_file)}\n")
                create_duet(a_file, b_file, output_file, self.log)

            self.log("全部生成完成！\n")
        except Exception as e:
            self.log(f"生成过程出错：{str(e)}\n")
        finally:
            # 恢复按钮
            self.after(0, lambda: self.btn_start.configure(state="normal", text="开始生成"))


if __name__ == "__main__":
    app = VideoDuetApp()
    app.mainloop()