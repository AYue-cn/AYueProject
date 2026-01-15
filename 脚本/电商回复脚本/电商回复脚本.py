import customtkinter as ctk
import pyperclip
import pyautogui
import time
import platform
from pynput import keyboard
import threading

# ===================== 全局配置 =====================
ctk.set_appearance_mode("light")  # 界面风格：light/dark/system
ctk.set_default_color_theme("blue")  # 主题颜色：blue/green/dark-blue

# 全局变量：控制监听状态和自定义快捷键
listener = None
is_listening = False
OS_TYPE = platform.system()
# 快捷键映射（下拉框显示名 → pynput对应的Key对象）
HOTKEY_MAP = {
    "F1": keyboard.Key.f1,
    "F2": keyboard.Key.f2,
    "F3": keyboard.Key.f3,
    "F4": keyboard.Key.f4,
    "F5": keyboard.Key.f5,
    "F6": keyboard.Key.f6,
    "F7": keyboard.Key.f7,
    "F8": keyboard.Key.f8,
    "F9": keyboard.Key.f9,
    "F10": keyboard.Key.f10,
    "F11": keyboard.Key.f11,
    "F12": keyboard.Key.f12
}
selected_hotkey = "F7"  # 默认快捷键


class ClipboardToolGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        # 窗口基本设置
        self.title("剪贴板拼接工具 - 自定义快捷键")
        self.geometry("750x650")  # 扩大窗口适配新组件
        self.resizable(True, True)

        # 初始化界面组件
        self._create_widgets()
        # 初始化快捷键监听器
        self.keyboard_listener = None

    def _create_widgets(self):
        """创建所有界面组件（拆分前缀/后缀+自定义快捷键）"""
        # 1. 标题栏
        title_label = ctk.CTkLabel(
            self, text="剪贴板拼接工具（前缀+剪贴板+后缀）", font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=10)

        # 2. 前缀/后缀输入区域
        prefix_suffix_frame = ctk.CTkFrame(self)
        prefix_suffix_frame.pack(padx=20, pady=10, fill="x")

        # 前缀文本框
        prefix_label = ctk.CTkLabel(
            prefix_suffix_frame, text="前缀文本：", font=ctk.CTkFont(size=12)
        )
        prefix_label.pack(padx=10, pady=5, anchor="w")
        self.prefix_text = ctk.CTkTextbox(prefix_suffix_frame, height=60)
        self.prefix_text.pack(padx=10, pady=5, fill="x")
        self.prefix_text.insert("0.0", "【前缀】")  # 默认前缀

        # 后缀文本框
        suffix_label = ctk.CTkLabel(
            prefix_suffix_frame, text="后缀文本：", font=ctk.CTkFont(size=12)
        )
        suffix_label.pack(padx=10, pady=5, anchor="w")
        self.suffix_text = ctk.CTkTextbox(prefix_suffix_frame, height=60)
        self.suffix_text.pack(padx=10, pady=5, fill="x")
        self.suffix_text.insert("0.0", "【后缀】")  # 默认后缀

        # 3. 快捷键设置 + 控制按钮区域
        control_frame = ctk.CTkFrame(self)
        control_frame.pack(padx=20, pady=10, fill="x")

        # 快捷键选择下拉框
        hotkey_frame = ctk.CTkFrame(control_frame)
        hotkey_frame.pack(padx=10, pady=5, fill="x")

        hotkey_label = ctk.CTkLabel(
            hotkey_frame, text="选择触发快捷键：", font=ctk.CTkFont(size=12)
        )
        hotkey_label.pack(side="left", padx=10, pady=5)

        self.hotkey_option = ctk.CTkOptionMenu(
            hotkey_frame,
            values=list(HOTKEY_MAP.keys()),  # F1-F12选项
            command=self.on_hotkey_change,
            width=100
        )
        self.hotkey_option.set(selected_hotkey)  # 默认选中F7
        self.hotkey_option.pack(side="left", padx=10, pady=5)

        # 启动/停止按钮
        self.start_btn = ctk.CTkButton(
            control_frame, text="启动监听", command=self.toggle_listener, width=120
        )
        self.start_btn.pack(padx=10, pady=10)

        # 4. 日志/结果显示区域
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(padx=20, pady=10, fill="both", expand=True)

        log_label = ctk.CTkLabel(
            log_frame, text="操作日志/结果：", font=ctk.CTkFont(size=12)
        )
        log_label.pack(padx=10, pady=5, anchor="w")

        # 日志显示框（只读）
        self.log_text = ctk.CTkTextbox(log_frame, state="disabled")
        self.log_text.pack(padx=10, pady=5, fill="both", expand=True)

        # 5. 系统提示区域
        tip_label = ctk.CTkLabel(
            self,
            text=self._get_system_tip(),
            font=ctk.CTkFont(size=10),
            text_color="orange"
        )
        tip_label.pack(padx=20, pady=5, anchor="w")

    def _get_system_tip(self):
        """根据系统生成权限提示"""
        if OS_TYPE == "Darwin":
            return "💡 macOS提示：需给Python/终端开启「辅助功能」权限（系统设置→隐私与安全性→辅助功能）"
        elif OS_TYPE == "Linux":
            return "💡 Linux提示：需先执行 sudo apt install python3-xlib 安装依赖"
        else:
            return "💡 Windows提示：请勿以管理员身份运行，避免模拟输入失效"

    def on_hotkey_change(self, value):
        """切换快捷键下拉框时的回调"""
        global selected_hotkey
        selected_hotkey = value
        if is_listening:
            # 如果正在监听，先停止再重启（使新快捷键生效）
            self.stop_listener()
            self.start_listener()
            self.log(f"🔄 快捷键已切换为{value}，监听已重启")
        else:
            self.log(f"🔧 快捷键已设置为{value}（启动监听后生效）")

    def log(self, message):
        """向日志框输出信息（线程安全）"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see("end")  # 自动滚动到最后
        self.log_text.configure(state="disabled")

    def process_clipboard(self):
        """核心功能：前缀 + 剪贴板 + 后缀 → 模拟粘贴"""
        try:
            # 1. 读取剪贴板
            clip_content = pyperclip.paste().strip()
            if not clip_content:
                self.log("⚠️ 剪贴板为空！请先复制文本后按快捷键")
                return

            # 2. 读取前缀和后缀文本（去除首尾空白和换行）
            prefix_content = self.prefix_text.get("0.0", "end").strip()
            suffix_content = self.suffix_text.get("0.0", "end").strip()

            # 3. 拼接文本：前缀 + 剪贴板 + 后缀
            result_text = f"{prefix_content}{clip_content}{suffix_content}"
            self.log(f"✅ 拼接完成：{result_text[:50]}..." if len(result_text) > 50 else f"✅ 拼接完成：{result_text}")

            # 4. 模拟Ctrl+V粘贴到当前文本框
            pyperclip.copy(result_text)
            time.sleep(0.2)  # 延迟确保焦点稳定

            if OS_TYPE == "Darwin":  # macOS
                pyautogui.hotkey('command', 'v')
            else:  # Windows/Linux
                pyautogui.hotkey('ctrl', 'v')

            self.log("✅ 已自动粘贴到当前激活的文本框！")

        except Exception as e:
            self.log(f"❌ 操作失败：{str(e)}")

    def on_press(self, key):
        """快捷键监听回调（适配自定义快捷键）"""
        try:
            # 匹配选中的快捷键（比如F7对应keyboard.Key.f7）
            target_key = HOTKEY_MAP[selected_hotkey]
            if key == target_key and is_listening:
                self.process_clipboard()
        except (AttributeError, KeyError):
            pass

    def start_listener(self):
        """启动快捷键监听（后台线程）"""
        global listener, is_listening
        is_listening = True
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()
        self.log(f"🚀 快捷键监听已启动（按下{selected_hotkey}触发）")
        self.start_btn.configure(text="停止监听")

    def stop_listener(self):
        """停止快捷键监听"""
        global listener, is_listening
        if listener:
            listener.stop()
            listener = None
        is_listening = False
        self.log("🛑 快捷键监听已停止")
        self.start_btn.configure(text="启动监听")

    def toggle_listener(self):
        """切换监听状态（启动/停止）"""
        if not is_listening:
            # 启动监听（用线程避免界面卡死）
            threading.Thread(target=self.start_listener, daemon=True).start()
        else:
            self.stop_listener()

    def on_closing(self):
        """窗口关闭时停止监听"""
        self.stop_listener()
        self.destroy()


if __name__ == "__main__":
    # 禁用pyautogui的失败安全
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.1

    # 启动GUI
    app = ClipboardToolGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)  # 关闭窗口时停止监听
    app.log(f"📌 程序已启动，当前默认快捷键：{selected_hotkey}")
    app.log("📝 使用步骤：1. 编辑前缀/后缀 2. 选择快捷键 3. 启动监听 4. 复制文本→激活文本框→按快捷键")
    app.mainloop()