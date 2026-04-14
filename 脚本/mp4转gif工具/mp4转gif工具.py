import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import imageio
from PIL import Image
import os

# 主程序类
class MP4toGIFConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("wxymp42gif - MP4转GIF工具")
        self.root.geometry("450x280")
        self.root.resizable(False, False)

        # 变量
        self.mp4_path = tk.StringVar()
        self.scale = tk.DoubleVar(value=0.5)  # 默认缩小一半
        self.fps = tk.IntVar(value=10)        # 默认10帧

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        # 文件选择
        ttk.Label(self.root, text="选择MP4文件：").place(x=20, y=30)
        ttk.Entry(self.root, textvariable=self.mp4_path, width=35).place(x=120, y=30)
        ttk.Button(self.root, text="浏览", command=self.select_file).place(x=350, y=28)

        # 缩小比例
        ttk.Label(self.root, text="缩小比例：").place(x=20, y=90)
        # 修复：去掉 resolution，改用 tk.Scale 支持小数精度
        tk.Scale(self.root, from_=0.1, to=1.0, variable=self.scale,
                 resolution=0.1, orient=tk.HORIZONTAL, length=200).place(x=100, y=90)
        ttk.Label(self.root, textvariable=self.scale).place(x=320, y=90)

        # 帧率
        ttk.Label(self.root, text="帧率：").place(x=20, y=150)
        tk.Scale(self.root, from_=1, to=30, variable=self.fps,
                 orient=tk.HORIZONTAL, length=200).place(x=100, y=150)
        ttk.Label(self.root, textvariable=self.fps).place(x=320, y=150)

        # 转换按钮
        self.convert_btn = ttk.Button(self.root, text="开始转换", command=self.convert)
        self.convert_btn.place(x=160, y=210, width=130)

    def select_file(self):
        path = filedialog.askopenfilename(
            title="选择MP4文件",
            filetypes=[("MP4文件", "*.mp4"), ("所有文件", "*.*")]
        )
        if path:
            self.mp4_path.set(path)

    def convert(self):
        mp4 = self.mp4_path.get().strip()
        if not mp4 or not os.path.exists(mp4):
            messagebox.showerror("错误", "请选择有效的MP4文件！")
            return

        scale = self.scale.get()
        fps = self.fps.get()
        gif_path = os.path.splitext(mp4)[0] + ".gif"

        self.convert_btn.config(state=tk.DISABLED, text="转换中...")
        self.root.update()

        try:
            # 读取视频
            reader = imageio.get_reader(mp4)
            frames = []

            for frame in reader:
                # 缩小尺寸
                img = Image.fromarray(frame)
                new_size = (int(img.width * scale), int(img.height * scale))
                img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
                frames.append(imageio.core.asarray(img_resized))

            # 保存GIF
            imageio.mimsave(gif_path, frames, fps=fps, loop=0)
            messagebox.showinfo("完成", f"GIF已保存：\n{gif_path}")

        except Exception as e:
            messagebox.showerror("转换失败", f"错误信息：\n{str(e)}")

        finally:
            self.convert_btn.config(state=tk.NORMAL, text="开始转换")

# 启动程序
if __name__ == "__main__":
    main_root = tk.Tk()
    app = MP4toGIFConverter(main_root)
    main_root.mainloop()