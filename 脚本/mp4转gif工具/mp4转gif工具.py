import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import imageio
from PIL import Image, ImageTk
import os
import sys

# 🔴 核心：打包后资源路径自动解析函数
def resource_path(relative_path):
    try:
        # 打包成exe后，资源会被解压到这个临时目录
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境下，用当前目录
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 主题设置
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class wxymp42gif:
    def __init__(self, root):
        self.root = root
        self.root.title("OiNk mp4转gif工具")
        self.root.geometry("540x640")
        self.root.resizable(False, False)

        # 🔴 从exe内部加载LOGO（打包后也能找到）
        try:
            self.logo_img = Image.open(resource_path("2026-04-14_102258_213.ico"))
            self.logo_img = self.logo_img.resize((120, 120), Image.Resampling.LANCZOS)
            self.logo = ImageTk.PhotoImage(self.logo_img)
        except:
            self.logo = None

        # 🔴 从exe内部加载窗口图标
        try:
            self.root.iconbitmap(resource_path("2026-04-14_102258_213.ico"))
        except:
            pass

        # 变量
        self.mp4_path = tk.StringVar()
        self.scale_val = tk.DoubleVar(value=0.5)
        self.fps_val = tk.IntVar(value=10)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self.root, corner_radius=15)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # LOGO（有就显示，没有也不崩溃）
        if self.logo:
            logo_label = ctk.CTkLabel(main_frame, image=self.logo, text="")
            logo_label.pack(pady=10)

        # 软件名称
        title_label = ctk.CTkLabel(
            main_frame,
            text="OiNk mp4转gif工具",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack(pady=5)

        sub_label = ctk.CTkLabel(
            main_frame,
            text="MP4 转 GIF 高效转换工具",
            font=ctk.CTkFont(size=14)
        )
        sub_label.pack(pady=(0, 10))

        # ========== 文件选择 ==========
        ctk.CTkLabel(main_frame, text="选择MP4文件：", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20, pady=(10, 5))
        file_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        file_frame.pack(fill="x", padx=20)

        self.file_entry = ctk.CTkEntry(file_frame, placeholder_text="未选择文件", height=38)
        self.file_entry.pack(side="left", fill="x", expand=True)

        browse_btn = ctk.CTkButton(file_frame, text="浏览", width=100, command=self.select_file)
        browse_btn.pack(side="right", padx=(10, 0))

        # ========== 缩小比例 ==========
        ctk.CTkLabel(main_frame, text="缩小比例：", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20, pady=(15, 5))
        self.scale_slider = ctk.CTkSlider(
            main_frame, from_=0.1, to=1.0, number_of_steps=9, variable=self.scale_val
        )
        self.scale_slider.pack(fill="x", padx=20)

        self.scale_label = ctk.CTkLabel(main_frame, text="0.5", font=ctk.CTkFont(size=13))
        self.scale_label.pack()
        self.scale_val.trace("w", self.update_scale_label)

        # ========== 帧率 ==========
        ctk.CTkLabel(main_frame, text="帧率 FPS：", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20, pady=(15, 5))
        self.fps_slider = ctk.CTkSlider(
            main_frame, from_=1, to=30, number_of_steps=29, variable=self.fps_val
        )
        self.fps_slider.pack(fill="x", padx=20)

        self.fps_label = ctk.CTkLabel(main_frame, text="10", font=ctk.CTkFont(size=13))
        self.fps_label.pack()
        self.fps_val.trace("w", self.update_fps_label)

        # ========== 转换按钮 ==========
        self.convert_btn = ctk.CTkButton(
            main_frame,
            text="开始转换",
            height=48,
            font=ctk.CTkFont(size=17, weight="bold"),
            command=self.convert
        )
        self.convert_btn.pack(fill="x", padx=20, pady=25)

    def update_scale_label(self, *args):
        self.scale_label.configure(text=f"{self.scale_val.get():.1f}")

    def update_fps_label(self, *args):
        self.fps_label.configure(text=str(int(self.fps_val.get())))

    def select_file(self):
        path = filedialog.askopenfilename(
            title="选择MP4文件",
            filetypes=[("MP4视频", "*.mp4"), ("所有文件", "*.*")]
        )
        if path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, path)

    def convert(self):
        mp4 = self.file_entry.get().strip()
        if not mp4 or not os.path.exists(mp4):
            messagebox.showerror("错误", "请选择有效的MP4文件！")
            return

        scale = self.scale_val.get()
        fps = self.fps_val.get()
        gif_path = os.path.splitext(mp4)[0] + ".gif"

        self.convert_btn.configure(state="disabled", text="转换中...")
        self.root.update()

        try:
            reader = imageio.get_reader(mp4)
            frames = []
            for frame in reader:
                img = Image.fromarray(frame)
                w = int(img.width * scale)
                h = int(img.height * scale)
                img_resized = img.resize((w, h), Image.Resampling.LANCZOS)
                frames.append(imageio.core.asarray(img_resized))

            imageio.mimsave(gif_path, frames, fps=fps, loop=0)
            messagebox.showinfo("✅ 转换完成", f"GIF已保存：\n{gif_path}")
        except Exception as e:
            messagebox.showerror("❌ 转换失败", f"错误：\n{str(e)}")
        finally:
            self.convert_btn.configure(state="normal", text="开始转换")

if __name__ == "__main__":
    root = ctk.CTk()
    app = wxymp42gif(root)
    root.mainloop()