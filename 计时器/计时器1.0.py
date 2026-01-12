import customtkinter as ctk
import tkinter as tk
import winsound
import threading
import time
from tkinter import StringVar, IntVar, messagebox

# 设置 customtkinter 外观
ctk.set_appearance_mode("dark")  # 深色主题
ctk.set_default_color_theme("blue")  # 蓝色配色

class CountdownTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("阿岳牌秒表 1.0")
        self.root.geometry("500x460")
        self.root.resizable(False, False)

        # 核心变量
        self.minutes = IntVar(value=1)  # 默认分钟数
        self.seconds = IntVar(value=0)  # 默认秒数
        self.total_seconds = IntVar(value=60)  # 总秒数
        self.timer_running = False
        self.timer_thread = None
        self.sound_playing = False

        # 格式化显示的时间字符串 (MM:SS)
        self.time_str = StringVar(value=self.format_time(self.total_seconds.get()))

        # 创建UI界面
        self.create_widgets()

    def format_time(self, seconds):
        """将秒数格式化为 MM:SS 格式"""
        mins, secs = divmod(seconds, 60)
        return f"{mins:02d}:{secs:02d}"

    def create_widgets(self):
        """创建所有UI组件，Spinbox设为只读（仅箭头微调）"""
        # 主容器
        main_frame = ctk.CTkFrame(self.root, corner_radius=20, border_width=2)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # 标题
        title_label = ctk.CTkLabel(
            main_frame,
            text="精准倒计时器",
            font=ctk.CTkFont(size=30, weight="bold", family="Microsoft YaHei")
        )
        title_label.pack(pady=20)

        # 时间显示面板
        time_panel = ctk.CTkFrame(main_frame, corner_radius=15, width=400, height=120)
        time_panel.pack(pady=10, fill="x", padx=30)
        time_panel.pack_propagate(False)

        # 时间显示标签
        time_display = ctk.CTkLabel(
            time_panel,
            textvariable=self.time_str,
            font=ctk.CTkFont(size=70, weight="bold", family="Arial"),
        )
        time_display.pack(expand=True)

        # 时间设置框架
        setting_frame = ctk.CTkFrame(main_frame, corner_radius=15)
        setting_frame.pack(pady=15, padx=30, fill="x")

        # 时间设置标签
        setting_label = ctk.CTkLabel(
            setting_frame,
            text="设置倒计时:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        setting_label.pack(side="left", padx=15, pady=15)

        # 分钟 Spinbox（只读，仅箭头）
        minute_label = ctk.CTkLabel(setting_frame, text="分钟:", font=ctk.CTkFont(size=14))
        minute_label.pack(side="left", padx=(15, 5), pady=15)

        self.minute_spinbox = tk.Spinbox(
            setting_frame,
            from_=0,
            to=59,
            textvariable=self.minutes,
            width=5,
            font=("Microsoft YaHei", 14),
            command=self.update_total_seconds,
            state="readonly"  # 关键：禁用手动输入，仅保留上下箭头
        )
        # 核心修改：将fg改为黑色，同时调整背景为浅灰色提升对比度
        self.minute_spinbox.configure(
            bg="#e0e0e0",       # 浅灰色背景
            fg="#000000",       # 黑色文字
            selectbackground="#4a4a4a",
            selectforeground="white"
        )
        self.minute_spinbox.pack(side="left", padx=(0, 15), pady=15)

        # 秒数 Spinbox（只读，仅箭头）
        second_label = ctk.CTkLabel(setting_frame, text="秒数:", font=ctk.CTkFont(size=14))
        second_label.pack(side="left", padx=(15, 5), pady=15)

        self.second_spinbox = tk.Spinbox(
            setting_frame,
            from_=0,
            to=59,
            textvariable=self.seconds,
            width=5,
            font=("Microsoft YaHei", 14),
            command=self.update_total_seconds,
            state="readonly"  # 关键：禁用手动输入，仅保留上下箭头
        )
        # 核心修改：将fg改为黑色，同时调整背景为浅灰色提升对比度
        self.second_spinbox.configure(
            bg="#e0e0e0",       # 浅灰色背景
            fg="#000000",       # 黑色文字
            selectbackground="#4a4a4a",
            selectforeground="white"
        )
        self.second_spinbox.pack(side="left", padx=(0, 15), pady=15)

        # 应用按钮（防止设置00:00）
        apply_btn = ctk.CTkButton(
            setting_frame,
            text="应用",
            command=self.apply_time_setting,
            width=80,
            height=35,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        apply_btn.pack(side="left", padx=15, pady=15)

        # 控制按钮框架
        btn_frame = ctk.CTkFrame(main_frame, corner_radius=15)
        btn_frame.pack(pady=10, padx=30, fill="x")

        # 开始按钮
        self.start_btn = ctk.CTkButton(
            btn_frame,
            text="开始",
            command=self.start_timer,
            width=120,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#28a745",
            hover_color="#218838"
        )
        self.start_btn.pack(side="left", padx=10, pady=15)

        # 暂停按钮
        self.pause_btn = ctk.CTkButton(
            btn_frame,
            text="暂停",
            command=self.pause_timer,
            width=120,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#ffc107",
            hover_color="#e0a800",
            state="disabled"
        )
        self.pause_btn.pack(side="left", padx=10, pady=15)

        # 重置按钮
        self.reset_btn = ctk.CTkButton(
            btn_frame,
            text="重置",
            command=self.reset_timer,
            width=120,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#dc3545",
            hover_color="#c82333"
        )
        self.reset_btn.pack(side="left", padx=10, pady=15)

        # 消音按钮（初始隐藏）
        self.mute_btn = ctk.CTkButton(
            main_frame,
            text="消音",
            command=self.stop_sound,
            width=120,
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#6f42c1",
            hover_color="#5a32a3",
            state="hidden"
        )
        self.mute_btn.pack(pady=15)

    def update_total_seconds(self):
        """更新总秒数（Spinbox值变化时）"""
        try:
            mins = int(self.minutes.get())
            secs = int(self.seconds.get())
            self.total_seconds.set(mins * 60 + secs)
            self.time_str.set(self.format_time(self.total_seconds.get()))
        except ValueError:
            pass

    def apply_time_setting(self):
        """应用时间设置，验证有效性"""
        try:
            mins = int(self.minutes.get())
            secs = int(self.seconds.get())
            total = mins * 60 + secs

            if total == 0:
                messagebox.showerror("错误", "倒计时时间不能为0！")
                return

            self.total_seconds.set(total)
            self.time_str.set(self.format_time(total))
            self.reset_timer()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")

    def start_timer(self):
        """开始/继续计时"""
        if not self.timer_running and self.total_seconds.get() > 0:
            self.timer_running = True
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal")

            # 禁用Spinbox和应用按钮，防止计时中修改时间
            self.minute_spinbox.config(state="disabled")
            self.second_spinbox.config(state="disabled")

            # 启动计时线程
            self.timer_thread = threading.Thread(target=self.run_timer, daemon=True)
            self.timer_thread.start()

    def pause_timer(self):
        """暂停计时"""
        self.timer_running = False
        self.start_btn.configure(state="normal", text="继续")
        self.pause_btn.configure(state="disabled")

        # 启用Spinbox（恢复为只读模式，而非normal）
        self.minute_spinbox.config(state="readonly")
        self.second_spinbox.config(state="readonly")

    def reset_timer(self):
        """重置计时"""
        self.timer_running = False
        self.start_btn.configure(state="normal", text="开始")
        self.pause_btn.configure(state="disabled")

        # 恢复初始显示时间
        self.time_str.set(self.format_time(self.total_seconds.get()))

        # 启用Spinbox（恢复为只读模式）
        self.minute_spinbox.config(state="readonly")
        self.second_spinbox.config(state="readonly")

        # 停止提示音
        self.stop_sound()

    def run_timer(self):
        """计时核心逻辑"""
        current_time = self.total_seconds.get()

        while self.timer_running and current_time > 0:
            time.sleep(1)
            current_time -= 1
            self.time_str.set(self.format_time(current_time))

            # 更新剩余时间（用于暂停后继续）
            self.total_seconds.set(current_time)
            # 同步更新Spinbox显示
            self.minutes.set(current_time // 60)
            self.seconds.set(current_time % 60)

        # 时间到触发提示音
        if current_time == 0 and self.timer_running:
            self.timer_running = False
            self.start_btn.configure(state="normal", text="开始")
            self.pause_btn.configure(state="disabled")

            # 启用Spinbox（恢复为只读模式）
            self.minute_spinbox.config(state="readonly")
            self.second_spinbox.config(state="readonly")

            self.play_alert_sound()

    def play_alert_sound(self):
        """播放Windows系统提示音（循环）"""
        self.sound_playing = True
        self.mute_btn.configure(state="normal")

        # 独立线程播放声音，避免阻塞UI
        def sound_loop():
            while self.sound_playing:
                # 使用Windows系统提示音
                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
                time.sleep(0.8)  # 提示音间隔

        sound_thread = threading.Thread(target=sound_loop, daemon=True)
        sound_thread.start()

    def stop_sound(self):
        """停止提示音"""
        self.sound_playing = False
        winsound.PlaySound(None, winsound.SND_PURGE)  # 清除声音播放队列
        self.mute_btn.configure(state="hidden")

if __name__ == "__main__":
    # 创建主窗口
    root = ctk.CTk()
    # 初始化计时器应用
    app = CountdownTimer(root)
    # 运行主循环
    root.mainloop()