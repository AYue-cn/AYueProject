import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import json
import os
import threading
import time
import sys
import subprocess

# ===================== 全局配置（仅保留聊天相关） =====================
# 基础配置
HOST_OPTIONS = {
    "海外节点": "https://api.grsai.com",
    "国内直连": "https://grsai.dakka.com.cn"
}
DEFAULT_HOST = "国内直连"
DEFAULT_MODEL_CHAT = "gemini-3-pro"
DEFAULT_ENCODING = "utf-8"

# 支持的聊天模型
SUPPORTED_CHAT_MODELS = [
    "nano-banana-fast", "nano-banana", "gemini-3-pro",
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"
]

# 文字颜色配置（用于区分不同角色）
COLOR_USER = "#4A90E2"  # 蓝色（用户消息）
COLOR_ASSISTANT = "#E27D60"  # 珊瑚色（AI消息）
COLOR_SYSTEM = "#85DCBA"  # 薄荷绿（系统消息）


# ===================== 路径修复（先定义函数） =====================
def get_base_dir():
    """获取程序真实运行目录（适配EXE打包）"""
    if hasattr(sys, 'frozen'):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(__file__)


# ===================== 初始化全局路径（函数定义后再初始化） =====================
BASE_DIR = get_base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")  # 现在get_base_dir已定义，不会报错


# ===================== 配置文件操作 =====================
def load_config():
    """加载配置文件，不存在则创建默认配置"""
    default_config = {
        "api_key": "默认APIKEY",  # 默认值（首次运行用）
        "default_host": DEFAULT_HOST,
        "default_model": DEFAULT_MODEL_CHAT,
        "stream": True
    }

    try:
        if not os.path.exists(CONFIG_FILE):
            # 创建默认配置文件
            save_config(default_config)
            log_debug(f"创建默认配置文件：{CONFIG_FILE}")
            return default_config

        with open(CONFIG_FILE, "r", encoding=DEFAULT_ENCODING) as f:
            config = json.load(f)
        # 补全缺失的配置项
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        return config
    except Exception as e:
        log_debug(f"加载配置文件失败，使用默认配置：{e}")
        return default_config


def save_config(config):
    """保存配置到JSON文件"""
    try:
        with open(CONFIG_FILE, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        log_debug(f"保存配置文件失败：{e}")
        messagebox.showerror("错误", f"保存配置失败：{str(e)}")
        return False


# ===================== 调试日志 =====================
def log_debug(msg):
    """调试日志输出"""
    print(f"[DEBUG {time.strftime('%H:%M:%S')}] {msg}")


# ===================== 基础工具函数 =====================
def read_txt_file(file_path: str) -> str:
    """读取TXT文件内容"""
    try:
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在：{file_path}")
            return ""
        with open(file_path, "r", encoding=DEFAULT_ENCODING) as f:
            content = f.read()
        messagebox.showinfo("成功", f"读取文件成功（{len(content)} 字符）")
        return content
    except Exception as e:
        messagebox.showerror("错误", f"读取文件失败：{str(e)}")
        return ""


def write_txt_file(file_path: str, content: str, append: bool = False) -> bool:
    """写入内容到TXT文件"""
    try:
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        mode = "a" if append else "w"
        with open(file_path, mode, encoding=DEFAULT_ENCODING) as f:
            f.write(content)
        messagebox.showinfo("成功", f"内容已保存到：{file_path}")
        return True
    except Exception as e:
        messagebox.showerror("错误", f"写入文件失败：{str(e)}")
        return False


# ===================== 核心聊天类 =====================
class Gemini3ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 加载配置文件
        self.config = load_config()

        # 设置CustomTkinter主题
        ctk.set_appearance_mode("system")  # system/light/dark
        ctk.set_default_color_theme("blue")  # blue/green/dark-blue

        # 窗口配置
        self.title("Gemini3 AI 聊天助手")
        self.geometry("1000x700")
        self.minsize(800, 1000)  # 修正最小尺寸（原1000太高）

        # 聊天状态
        self.chat_messages = [{"role": "system", "content": "你是专业友好的AI助手，用中文清晰准确回答问题。"}]
        self.current_chat_model = self.config.get("default_model", DEFAULT_MODEL_CHAT)
        self.current_host = self.config.get("default_host", DEFAULT_HOST)
        self.current_stream = self.config.get("stream", True)
        self.last_chat_reply = ""
        self.is_chat_requesting = False

        # 从配置加载API Key
        self.api_key_value = self.config.get("api_key", "")

        # 创建UI
        self._create_ui()

    def _create_ui(self):
        """创建聊天界面"""
        # 顶部配置栏
        config_frame = ctk.CTkFrame(self, corner_radius=8)
        config_frame.pack(fill="x", padx=20, pady=10, ipady=10)

        # API Key配置（增加保存按钮）
        api_label = ctk.CTkLabel(config_frame, text="API Key：")
        api_label.pack(side="left", padx=(20, 5))
        self.api_entry = ctk.CTkEntry(config_frame, show="*", width=400)
        self.api_entry.insert(0, self.api_key_value)  # 从配置加载值
        self.api_entry.pack(side="left", padx=5)

        # 保存API Key按钮
        save_api_btn = ctk.CTkButton(
            config_frame, text="保存Key", command=self._save_api_key,
            width=80, corner_radius=6, fg_color="#2ECC71"
        )
        save_api_btn.pack(side="left", padx=5)

        # 节点选择
        host_label = ctk.CTkLabel(config_frame, text="节点：")
        host_label.pack(side="left", padx=(20, 5))
        self.host_combo = ctk.CTkComboBox(
            config_frame, values=list(HOST_OPTIONS.keys()), width=120
        )
        self.host_combo.set(self.current_host)
        self.host_combo.pack(side="left", padx=5)
        self.host_combo.bind("<<ComboboxSelected>>", self._on_host_change)

        # 模型选择
        model_label = ctk.CTkLabel(config_frame, text="模型：")
        model_label.pack(side="left", padx=(20, 5))
        self.model_combo = ctk.CTkComboBox(
            config_frame, values=SUPPORTED_CHAT_MODELS, width=180
        )
        self.model_combo.set(self.current_chat_model)
        self.model_combo.pack(side="left", padx=5)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_chat_model_change)

        # 流式响应开关
        self.stream_switch = ctk.CTkCheckBox(
            config_frame, text="流式响应", command=self._on_stream_toggle
        )
        if self.current_stream:
            self.stream_switch.select()
        self.stream_switch.pack(side="left", padx=(20, 20))

        # 聊天显示区
        chat_display_frame = ctk.CTkFrame(self, corner_radius=8)
        chat_display_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        display_label = ctk.CTkLabel(chat_display_frame, text="聊天记录", font=("Arial", 14, "bold"))
        display_label.pack(anchor="w", padx=20, pady=10)

        # 原生Text组件
        self.chat_text = tk.Text(
            chat_display_frame, font=("微软雅黑", 12), wrap="word",
            bg=self._get_background_color(),
            fg=self._get_foreground_color(),
            bd=0, relief="flat"
        )
        self.chat_text.tag_configure("user", foreground=COLOR_USER)
        self.chat_text.tag_configure("assistant", foreground=COLOR_ASSISTANT)
        self.chat_text.tag_configure("system", foreground=COLOR_SYSTEM)

        chat_scrollbar = ctk.CTkScrollbar(
            chat_display_frame, command=self.chat_text.yview
        )
        self.chat_text.configure(yscrollcommand=chat_scrollbar.set)

        self.chat_text.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(0, 20))
        chat_scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=(0, 20))

        self.chat_text.insert("end", "欢迎使用Gemini3 AI聊天助手！\n\n", "system")

        # 输入区
        input_frame = ctk.CTkFrame(self, corner_radius=8)
        input_frame.pack(fill="x", padx=20, pady=(0, 20), ipady=10)

        input_label = ctk.CTkLabel(input_frame, text="输入消息", font=("Arial", 14, "bold"))
        input_label.pack(anchor="w", padx=20, pady=10)

        self.chat_input_text = ctk.CTkTextbox(
            input_frame, font=("微软雅黑", 12), wrap="word",
            corner_radius=8, height=120
        )
        self.chat_input_text.pack(fill="x", padx=20, pady=(0, 10))

        # 按钮区
        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20)

        load_btn = ctk.CTkButton(
            btn_frame, text="加载文件", command=self._load_chat_file,
            width=100, corner_radius=6
        )
        load_btn.pack(side="left", padx=5)

        clear_btn = ctk.CTkButton(
            btn_frame, text="清空记录", command=self._clear_chat_history,
            width=100, corner_radius=6, fg_color="#E74C3C"
        )
        clear_btn.pack(side="left", padx=5)

        self.send_btn = ctk.CTkButton(
            btn_frame, text="发送消息", command=self._send_chat_message,
            width=100, corner_radius=6, fg_color="#3498DB"
        )
        self.send_btn.pack(side="left", padx=5)

        save_reply_btn = ctk.CTkButton(
            btn_frame, text="保存回复", command=self._save_chat_reply,
            width=100, corner_radius=6
        )
        save_reply_btn.pack(side="left", padx=5)

        save_all_btn = ctk.CTkButton(
            btn_frame, text="保存全部", command=self._save_chat_all,
            width=100, corner_radius=6
        )
        save_all_btn.pack(side="left", padx=5)

    def _save_api_key(self):
        """保存API Key到配置文件"""
        new_api_key = self.api_entry.get().strip()
        if not new_api_key:
            messagebox.showwarning("提示", "API Key不能为空！")
            return

        self.config["api_key"] = new_api_key
        if save_config(self.config):
            self.api_key_value = new_api_key
            messagebox.showinfo("成功", "API Key已保存！")

    def _get_background_color(self):
        """适配主题的背景色"""
        if ctk.get_appearance_mode() == "dark":
            return "#2B2B2B"
        else:
            return "#F5F5F5"

    def _get_foreground_color(self):
        """适配主题的文字色"""
        if ctk.get_appearance_mode() == "dark":
            return "#FFFFFF"
        else:
            return "#000000"

    def _on_host_change(self, event):
        """切换节点"""
        self.current_host = self.host_combo.get()
        self.config["default_host"] = self.current_host
        save_config(self.config)
        self._append_chat_message(f"系统：已切换至 {self.current_host} 节点", "system")

    def _on_chat_model_change(self, event):
        """切换聊天模型"""
        self.current_chat_model = self.model_combo.get()
        self.config["default_model"] = self.current_chat_model
        save_config(self.config)
        self._append_chat_message(f"系统：已切换至 {self.current_chat_model} 模型", "system")

    def _on_stream_toggle(self):
        """切换流式响应"""
        self.current_stream = self.stream_switch.get()
        self.config["stream"] = self.current_stream
        save_config(self.config)
        status = "开启" if self.current_stream else "关闭"
        self._append_chat_message(f"系统：流式响应功能已{status}", "system")

    def _clear_chat_history(self):
        """清空聊天历史"""
        self.chat_messages = [self.chat_messages[0]]
        self.last_chat_reply = ""
        self.chat_text.delete(1.0, "end")
        self._append_chat_message("系统：所有对话历史已清空", "system")

    def _load_chat_file(self):
        """加载TXT文件到输入框"""
        file_path = filedialog.askopenfilename(
            title="选择文本文件",
            filetypes=[("TXT文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            content = read_txt_file(file_path)
            if content:
                self.chat_input_text.delete(1.0, "end")
                self.chat_input_text.insert("end", content)

    def _append_chat_message(self, text, tag):
        """追加聊天消息"""
        self.chat_text.insert("end", text + "\n\n", tag)
        self.chat_text.see("end")

    def _send_chat_message(self):
        """发送聊天消息"""
        if self.is_chat_requesting:
            messagebox.showwarning("提示", "AI正在处理请求，请稍候！")
            return

        # 从输入框读取API Key（优先使用输入框最新值）
        api_key = self.api_entry.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请先输入API-Key！")
            return

        user_input = self.chat_input_text.get(1.0, "end").strip()
        if not user_input:
            messagebox.showwarning("提示", "请输入对话内容！")
            return

        self.chat_input_text.delete(1.0, "end")
        self._append_chat_message(f"用户：{user_input}", "user")
        self.chat_messages.append({"role": "user", "content": user_input})

        self.is_chat_requesting = True
        self.send_btn.configure(state="disabled", text="处理中...")

        def chat_api_call():
            base_url = HOST_OPTIONS[self.current_host]
            url = f"{base_url}/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            payload = {
                "model": self.current_chat_model,
                "stream": self.current_stream,
                "messages": self.chat_messages
            }

            assistant_content = ""
            try:
                response = requests.post(
                    url, headers=headers, json=payload, stream=self.current_stream, timeout=30
                )
                response.raise_for_status()

                if self.current_stream:
                    self.after(0, lambda: self.chat_text.insert("end", "AI：", "assistant"))
                    for line in response.iter_lines():
                        if not self.is_chat_requesting:
                            break
                        if line:
                            line_data = line.decode("utf-8").lstrip("data: ")
                            if line_data == "[DONE]":
                                break
                            try:
                                data = json.loads(line_data)
                                delta = data["choices"][0]["delta"]
                                content = delta.get("content", "")
                                if content:
                                    assistant_content += content
                                    self.after(0, lambda c=content: self._update_chat_stream(c))
                            except:
                                continue
                    self.after(0, lambda: self.chat_text.insert("end", "\n\n"))
                else:
                    data = response.json()
                    assistant_content = data["choices"][0]["message"]["content"]
                    self.after(0, lambda: self._append_chat_message(f"AI：{assistant_content}", "assistant"))

                self.last_chat_reply = assistant_content
                self.chat_messages.append({"role": "assistant", "content": assistant_content})

            except Exception as e:
                error_msg = f"系统：API请求错误 - {str(e)}"
                self.after(0, lambda: self._append_chat_message(error_msg, "system"))
                log_debug(f"Chat API Error: {e}")
            finally:
                self.is_chat_requesting = False
                self.after(0, lambda: self.send_btn.configure(state="normal", text="发送消息"))

        threading.Thread(target=chat_api_call, daemon=True).start()

    def _update_chat_stream(self, content):
        """更新流式响应内容"""
        self.chat_text.insert("end", content)
        self.chat_text.see("end")

    def _save_chat_reply(self):
        """保存最新回复"""
        if not self.last_chat_reply:
            messagebox.showwarning("提示", "暂无回复内容可保存！")
            return

        file_path = filedialog.asksaveasfilename(
            title="保存AI回复",
            defaultextension=".txt",
            filetypes=[("TXT文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            write_txt_file(file_path, self.last_chat_reply)

    def _save_chat_all(self):
        """保存全部聊天历史"""
        if len(self.chat_messages) <= 1:
            messagebox.showwarning("提示", "暂无聊天历史可保存！")
            return

        history_content = "===== Gemini3 AI 聊天记录 =====\n"
        history_content += f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        history_content += f"使用模型：{self.current_chat_model}\n"
        history_content += "=================================\n\n"

        for msg in self.chat_messages[1:]:
            role = "用户" if msg["role"] == "user" else "AI"
            history_content += f"{role}：\n{msg['content']}\n\n"

        file_path = filedialog.asksaveasfilename(
            title="保存聊天历史",
            defaultextension=".txt",
            filetypes=[("TXT文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            write_txt_file(file_path, history_content)


# ===================== 程序入口 =====================
if __name__ == "__main__":
    try:
        app = Gemini3ChatApp()


        def on_closing():
            if messagebox.askokcancel("退出", "确定退出Gemini3 AI聊天助手吗？"):
                app.destroy()


        app.protocol("WM_DELETE_WINDOW", on_closing)
        app.mainloop()
    except Exception as e:
        messagebox.showerror("启动失败", f"程序启动失败：{str(e)}")
        sys.exit(1)