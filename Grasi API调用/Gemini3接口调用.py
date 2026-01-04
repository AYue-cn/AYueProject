import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import requests
import json
import os
import threading
import webbrowser
import time
import base64
import urllib.request
from io import BytesIO
from typing import List, Dict
from PIL import Image, ImageTk
import sys

# ===================== 全局配置 =====================
# 基础配置
HOST_OPTIONS = {
    "海外节点": "https://api.grsai.com",
    "国内直连": "https://grsai.dakka.com.cn"
}
DEFAULT_HOST = "国内直连"
DEFAULT_API_KEY = "sk-f959a7f1bfb74f36bade9ac6208a62df"
DEFAULT_WEBHOOK = "-1"  # 强制同步返回任务ID
DEFAULT_SHUT_PROGRESS = False
DEFAULT_MODEL_CHAT = "gemini-3-pro"
DEFAULT_MODEL_VIDEO = "sora-2"

# Nano Banana新增配置
DEFAULT_MODEL_DRAW = "nano-banana-fast"
SUPPORTED_DRAW_MODELS = ["nano-banana-fast", "nano-banana", "nano-banana-pro", "nano-banana-pro-vt"]
ASPECT_RATIO_OPTIONS_DRAW = ["auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "5:4", "4:5", "21:9"]
IMAGE_SIZE_OPTIONS = ["1K", "2K", "4K"]

# 其他配置
SUPPORTED_CHAT_MODELS = [
    "nano-banana-fast", "nano-banana", "gemini-3-pro",
    "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"
]
ASPECT_RATIO_OPTIONS_VIDEO = ["9:16", "16:9"]
DURATION_OPTIONS = [10, 15]
SIZE_OPTIONS_VIDEO = ["small", "large"]
REFRESH_INTERVAL = 5
DEFAULT_ENCODING = "utf-8"
THUMBNAIL_SIZE = (100, 80)  # 缩略图尺寸
MAX_REF_IMAGES = 5  # 最多选择5张参考图

# 缓存配置
CACHE_EXPIRE_SECONDS = 86400  # 缓存过期时间：24小时（86400秒）
CACHE_KEY_DRAW_PREFIX = "draw_prompt_prefix"  # 绘画前缀提示词缓存键
CACHE_KEY_DRAW_SUFFIX = "draw_prompt_suffix"  # 绘画后缀提示词缓存键
CACHE_KEY_VIDEO_PREFIX = "video_prompt_prefix"  # 视频前缀提示词缓存键
CACHE_KEY_VIDEO_SUFFIX = "video_prompt_suffix"  # 视频后缀提示词缓存键


# ===================== 路径修复（核心） =====================
def get_base_dir():
    """获取程序真实运行目录（适配EXE打包）"""
    if hasattr(sys, 'frozen'):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(__file__)


# 初始化全局路径
BASE_DIR = get_base_dir()
CACHE_FILE = os.path.join(BASE_DIR, "cache.txt")  # 缓存文件
TASK_STORAGE_FILE = os.path.join(BASE_DIR, "tasks.json")  # 任务文件


# ===================== 调试日志（新增） =====================
def log_debug(msg):
    """调试日志输出"""
    print(f"[DEBUG {time.strftime('%H:%M:%S')}] {msg}")


# ===================== 缓存工具函数（增强版） =====================
def load_cache() -> List[Dict]:
    """加载缓存文件，自动过滤过期记录"""
    cache_data = []
    try:
        if not os.path.exists(CACHE_FILE):
            return cache_data

        with open(CACHE_FILE, "r", encoding=DEFAULT_ENCODING) as f:
            raw_data = f.read()
            if raw_data:
                cache_data = json.loads(raw_data)

        # 过滤超过24小时的记录
        current_ts = time.time()
        valid_cache = []
        for item in cache_data:
            if isinstance(item, dict) and "timestamp" in item:
                if (current_ts - item["timestamp"]) <= CACHE_EXPIRE_SECONDS:
                    valid_cache.append(item)

        # 保存过滤后的缓存
        save_cache(overwrite=True, cache_list=valid_cache)
        return valid_cache
    except Exception as e:
        log_debug(f"加载缓存失败：{e}")
        messagebox.showwarning("警告", f"加载缓存失败：{str(e)}，将创建新缓存")
        return []


def save_cache(cache_item: Dict = None, overwrite: bool = False, cache_list: List[Dict] = None):
    """保存缓存记录"""
    try:
        if overwrite and cache_list is not None:
            current_cache = cache_list
        else:
            current_cache = load_cache()

        if cache_item and isinstance(cache_item, dict):
            cache_item["timestamp"] = time.time()
            cache_item["create_time"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            current_cache.append(cache_item)

        with open(CACHE_FILE, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(current_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_debug(f"保存缓存失败：{e}")
        messagebox.showerror("错误", f"保存缓存失败：{str(e)}")


def get_cached_value(key: str) -> str:
    """获取指定键的缓存值"""
    cache_data = load_cache()
    # 倒序查找最新的缓存值
    for item in reversed(cache_data):
        if isinstance(item, dict) and item.get("key") == key and "value" in item:
            return item["value"]
    return ""


def save_cached_value(key: str, value: str, description: str = ""):
    """保存指定键的缓存值"""
    save_cache({
        "key": key,
        "value": value,
        "description": description
    })


def get_latest_api_key() -> str:
    """从缓存获取最近使用的API-Key"""
    cache_data = load_cache()
    sorted_cache = sorted(
        [item for item in cache_data if isinstance(item, dict)],
        key=lambda x: x.get("timestamp", 0),
        reverse=True
    )
    for item in sorted_cache:
        if "api_key" in item and item["api_key"].strip():
            return item["api_key"]
    return DEFAULT_API_KEY


# ===================== 基础工具函数 =====================
def read_txt_file(file_path: str) -> str:
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


def download_file(file_url: str, save_path: str) -> bool:
    """通用文件下载（支持图片/视频）"""
    try:
        if not file_url.startswith("http"):
            messagebox.showerror("错误", "无效的文件URL！")
            return False

        # 进度回调
        def reporthook(count, block_size, total_size):
            percent = int(count * block_size * 100 / total_size) if total_size > 0 else 0
            print(f"下载进度：{percent}%", end="\r")

        urllib.request.urlretrieve(file_url, save_path, reporthook=reporthook)
        messagebox.showinfo("成功", f"文件已保存到：{save_path}")
        return True
    except Exception as e:
        messagebox.showerror("错误", f"文件下载失败：{str(e)}")
        return False


def file_to_base64(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{base64_data}"
    except Exception as e:
        messagebox.showerror("错误", f"文件转Base64失败：{str(e)}")
        return ""


# ===================== 任务管理核心修复 =====================
def load_tasks() -> List[Dict]:
    """加载所有任务（绘画+视频）- 修复路径和格式问题"""
    try:
        # 确保任务文件目录存在
        if not os.path.exists(os.path.dirname(TASK_STORAGE_FILE)):
            os.makedirs(os.path.dirname(TASK_STORAGE_FILE))

        if not os.path.exists(TASK_STORAGE_FILE):
            # 创建空任务文件
            with open(TASK_STORAGE_FILE, "w", encoding=DEFAULT_ENCODING) as f:
                json.dump([], f, ensure_ascii=False)
            log_debug("任务文件不存在，已创建空文件")
            return []

        with open(TASK_STORAGE_FILE, "r", encoding=DEFAULT_ENCODING) as f:
            tasks = json.load(f)

        # 格式校验
        if not isinstance(tasks, list):
            log_debug("任务文件格式错误，重置为空列表")
            save_tasks([])
            return []

        log_debug(f"成功加载{len(tasks)}个任务")
        return tasks
    except Exception as e:
        log_debug(f"加载任务失败：{e}")
        messagebox.showwarning("警告", f"加载任务失败：{str(e)}，将创建新任务列表")
        # 重置任务文件
        save_tasks([])
        return []


def save_tasks(tasks: List[Dict]) -> bool:
    """保存所有任务 - 修复路径和原子写入"""
    try:
        # 确保目录存在
        if not os.path.exists(os.path.dirname(TASK_STORAGE_FILE)):
            os.makedirs(os.path.dirname(TASK_STORAGE_FILE))

        # 原子写入（避免文件损坏）
        temp_file = TASK_STORAGE_FILE + ".tmp"
        with open(temp_file, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, TASK_STORAGE_FILE)

        log_debug(f"成功保存{len(tasks)}个任务")
        return True
    except Exception as e:
        log_debug(f"保存任务失败：{e}")
        messagebox.showerror("错误", f"保存任务失败：{str(e)}")
        return False


# ===================== 核心应用类 =====================
class GRS_AIMultiTool_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("阿岳AI助手（Gemini3+NanoBanana+Sora2）")
        self.root.geometry("1500x950")
        self.root.resizable(True, True)

        # 修复Tkinter线程兼容
        self.root.after(0, lambda: None)
        threading.Thread(target=lambda: None, daemon=True).start()

        # 全局状态
        self.cache_data = load_cache()
        self.api_key = tk.StringVar(value=get_latest_api_key())
        self.current_host = tk.StringVar(value=DEFAULT_HOST)

        # 聊天相关状态
        self.chat_messages = [{"role": "system", "content": "你是专业友好的AI助手，用中文清晰准确回答问题。"}]
        self.current_chat_model = DEFAULT_MODEL_CHAT
        self.current_stream = True
        self.last_chat_reply = ""
        self.is_chat_requesting = False

        # 绘画相关状态
        self.draw_ref_images = []
        self.is_draw_requesting = False
        self.current_draw_model = DEFAULT_MODEL_DRAW

        # 视频相关状态
        self.video_ref_images = []
        self.is_video_requesting = False

        # 任务管理状态（强制初始化）
        self.tasks = load_tasks()  # 确保任务列表加载
        self.refresh_thread = None
        self.is_refreshing = True

        # 创建UI
        self._create_main_ui()

        # 启动任务自动刷新（修复线程启动逻辑）
        self._start_refresh_thread()

        # 初始化提示（显示任务数量）
        messagebox.showinfo("提示",
                            f"程序初始化完成！\n已加载缓存记录：{len(self.cache_data)}条\n已加载任务记录：{len(self.tasks)}条")

    def _create_main_ui(self):
        """创建主界面"""
        # 顶部API配置栏
        api_frame = ttk.Frame(self.root, padding="10")
        api_frame.pack(fill=tk.X, anchor=tk.N)

        # API-Key输入
        ttk.Label(api_frame, text="API-Key：").pack(side=tk.LEFT, padx=5)
        api_entry = ttk.Entry(api_frame, textvariable=self.api_key, show="*", width=40)
        api_entry.pack(side=tk.LEFT, padx=5)

        # 保存API-Key按钮
        save_api_btn = ttk.Button(api_frame, text="保存API-Key", command=self._save_api_key)
        save_api_btn.pack(side=tk.LEFT, padx=5)

        # 节点选择
        ttk.Label(api_frame, text="节点选择：").pack(side=tk.LEFT, padx=5)
        host_combo = ttk.Combobox(
            api_frame, textvariable=self.current_host, values=list(HOST_OPTIONS.keys()),
            state="readonly", width=10
        )
        host_combo.pack(side=tk.LEFT, padx=5)

        # 主标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建各功能标签页
        self._create_chat_tab()  # AI聊天
        self._create_draw_tab()  # NanoBanana绘画
        self._create_video_tab()  # Sora2视频
        self._create_task_tab()  # 任务管理
        self._create_cache_tab()  # 缓存管理

    def _save_api_key(self):
        """保存API-Key到缓存"""
        api_key = self.api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "API-Key不能为空！")
            return

        save_cache({
            "api_key": api_key,
            "description": "保存API-Key"
        })
        messagebox.showinfo("成功", "API-Key已保存到缓存！")

    # ===================== AI聊天标签页（无修改） =====================
    def _create_chat_tab(self):
        """创建Gemini3聊天标签页"""
        chat_tab = ttk.Frame(self.notebook)
        self.notebook.add(chat_tab, text="Gemini3 AI聊天")

        # 聊天控制区
        ctrl_frame = ttk.Frame(chat_tab, padding="10")
        ctrl_frame.pack(fill=tk.X, anchor=tk.N)

        # 模型选择
        ttk.Label(ctrl_frame, text="聊天模型：").pack(side=tk.LEFT, padx=5)
        self.chat_model_var = tk.StringVar(value=self.current_chat_model)
        chat_model_combo = ttk.Combobox(
            ctrl_frame, textvariable=self.chat_model_var, values=SUPPORTED_CHAT_MODELS,
            state="readonly", width=20
        )
        chat_model_combo.pack(side=tk.LEFT, padx=5)
        chat_model_combo.bind("<<ComboboxSelected>>", self._on_chat_model_change)

        # 流式响应开关
        self.stream_var = tk.BooleanVar(value=self.current_stream)
        stream_check = ttk.Checkbutton(
            ctrl_frame, text="流式响应", variable=self.stream_var, command=self._on_stream_toggle
        )
        stream_check.pack(side=tk.LEFT, padx=10)

        # 清空历史按钮
        clear_chat_btn = ttk.Button(ctrl_frame, text="清空历史", command=self._clear_chat_history)
        clear_chat_btn.pack(side=tk.LEFT, padx=5)

        # 聊天显示区
        display_frame = ttk.Frame(chat_tab, padding="10")
        display_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(display_frame, text="对话历史：").pack(anchor=tk.W)
        self.chat_text = scrolledtext.ScrolledText(
            display_frame, wrap=tk.WORD, font=("微软雅黑", 10), state=tk.DISABLED
        )
        self.chat_text.pack(fill=tk.BOTH, expand=True, pady=5)
        # 设置文字颜色
        self.chat_text.tag_configure("user", foreground="#2E86AB", font=("微软雅黑", 10, "bold"))
        self.chat_text.tag_configure("assistant", foreground="#A23B72", font=("微软雅黑", 10))
        self.chat_text.tag_configure("system", foreground="#F18F01", font=("微软雅黑", 9, "italic"))

        # 输入区
        input_frame = ttk.Frame(chat_tab, padding="10")
        input_frame.pack(fill=tk.X, anchor=tk.S)

        ttk.Label(input_frame, text="输入内容：").pack(anchor=tk.W)
        self.chat_input_text = scrolledtext.ScrolledText(
            input_frame, wrap=tk.WORD, font=("微软雅黑", 10), height=6
        )
        self.chat_input_text.pack(fill=tk.X, pady=5)

        # 按钮区
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill=tk.X)

        load_chat_btn = ttk.Button(btn_frame, text="加载TXT文件", command=self._load_chat_file)
        load_chat_btn.pack(side=tk.LEFT, padx=5)

        self.send_chat_btn = ttk.Button(btn_frame, text="发送消息", command=self._send_chat_message)
        self.send_chat_btn.pack(side=tk.LEFT, padx=5)

        save_reply_btn = ttk.Button(btn_frame, text="保存最新回复", command=self._save_chat_reply)
        save_reply_btn.pack(side=tk.LEFT, padx=5)

        save_all_btn = ttk.Button(btn_frame, text="保存全部历史", command=self._save_chat_all)
        save_all_btn.pack(side=tk.LEFT, padx=5)

    def _on_chat_model_change(self, event):
        """切换聊天模型"""
        self.current_chat_model = self.chat_model_var.get()
        self._append_chat_message(f"系统：已切换至 {self.current_chat_model} 模型", "system")

    def _on_stream_toggle(self):
        """切换流式响应"""
        self.current_stream = self.stream_var.get()
        status = "开启" if self.current_stream else "关闭"
        self._append_chat_message(f"系统：流式响应功能已{status}", "system")

    def _clear_chat_history(self):
        """清空聊天历史"""
        self.chat_messages = [self.chat_messages[0]]
        self.last_chat_reply = ""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete(1.0, tk.END)
        self.chat_text.config(state=tk.DISABLED)
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
                self.chat_input_text.delete(1.0, tk.END)
                self.chat_input_text.insert(tk.END, content)
                save_cache({
                    "type": "chat_load_file",
                    "file_path": file_path,
                    "description": "加载聊天文本文件"
                })

    def _append_chat_message(self, text, tag):
        """追加聊天消息"""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, text + "\n\n", tag)
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def _send_chat_message(self):
        """发送聊天消息"""
        if self.is_chat_requesting:
            messagebox.showwarning("提示", "AI正在处理请求，请稍候！")
            return

        api_key = self.api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请先输入并保存API-Key！")
            return

        user_input = self.chat_input_text.get(1.0, tk.END).strip()
        if not user_input:
            messagebox.showwarning("提示", "请输入对话内容！")
            return

        # 清空输入框
        self.chat_input_text.delete(1.0, tk.END)
        self._append_chat_message(f"用户：{user_input}", "user")
        self.chat_messages.append({"role": "user", "content": user_input})

        # 保存请求记录
        save_cache({
            "type": "chat_request",
            "model": self.current_chat_model,
            "user_input": user_input,
            "stream": self.current_stream,
            "description": "发送聊天请求"
        })

        # 异步调用API
        self.is_chat_requesting = True
        self.send_chat_btn.config(state=tk.DISABLED)

        def chat_api_call():
            base_url = HOST_OPTIONS[self.current_host.get()]
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
                    # 流式响应处理
                    self.root.after(0, lambda: self._append_chat_message("AI助手：", "assistant"))
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
                                    self.root.after(0, lambda c=content: self._update_chat_stream(c))
                            except:
                                continue
                    self.root.after(0, lambda: self.chat_text.insert(tk.END, "\n\n"))
                else:
                    # 非流式响应
                    data = response.json()
                    assistant_content = data["choices"][0]["message"]["content"]
                    self.root.after(0, lambda: self._append_chat_message(f"AI助手：{assistant_content}", "assistant"))

                # 保存回复
                self.last_chat_reply = assistant_content
                self.chat_messages.append({"role": "assistant", "content": assistant_content})

                # 保存响应记录
                save_cache({
                    "type": "chat_response",
                    "model": self.current_chat_model,
                    "user_input": user_input,
                    "assistant_reply": assistant_content,
                    "description": "收到聊天回复"
                })

            except Exception as e:
                error_msg = f"API请求错误：{str(e)}"
                self.root.after(0, lambda: self._append_chat_message(f"系统：{error_msg}", "system"))
                save_cache({
                    "type": "chat_error",
                    "error": str(e),
                    "description": "聊天请求失败"
                })
            finally:
                self.is_chat_requesting = False
                self.root.after(0, lambda: self.send_chat_btn.config(state=tk.NORMAL))

        threading.Thread(target=chat_api_call, daemon=True).start()

    def _update_chat_stream(self, content):
        """更新流式响应内容"""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, content)
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

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
            save_cache({
                "type": "chat_save_reply",
                "file_path": file_path,
                "description": "保存最新AI回复"
            })

    def _save_chat_all(self):
        """保存全部聊天历史"""
        if len(self.chat_messages) <= 1:
            messagebox.showwarning("提示", "暂无聊天历史可保存！")
            return

        history_content = "===== 阿岳AI助手 聊天历史 =====\n"
        history_content += f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        history_content += f"使用模型：{self.current_chat_model}\n"
        history_content += "=================================\n\n"

        for msg in self.chat_messages[1:]:
            role = "用户" if msg["role"] == "user" else "AI助手"
            history_content += f"{role}：\n{msg['content']}\n\n"

        file_path = filedialog.asksaveasfilename(
            title="保存聊天历史",
            defaultextension=".txt",
            filetypes=[("TXT文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            write_txt_file(file_path, history_content)
            save_cache({
                "type": "chat_save_all",
                "file_path": file_path,
                "message_count": len(self.chat_messages) - 1,
                "description": "保存全部聊天历史"
            })

    # ===================== NanoBanana绘画标签页（移除独立轮询） =====================
    def _create_draw_tab(self):
        """创建NanoBanana绘画标签页（三输入框提示词）"""
        draw_tab = ttk.Frame(self.notebook)
        self.notebook.add(draw_tab, text="NanoBanana 绘画")

        # 参数配置区
        param_frame = ttk.LabelFrame(draw_tab, text="绘画参数配置", padding="10")
        param_frame.pack(fill=tk.X, anchor=tk.N, padx=10, pady=5)

        # 1. 基础模型配置
        basic_frame = ttk.Frame(param_frame)
        basic_frame.pack(fill=tk.X, pady=5)

        # 模型选择
        ttk.Label(basic_frame, text="绘画模型：").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        self.draw_model_var = tk.StringVar(value=self.current_draw_model)
        draw_model_combo = ttk.Combobox(
            basic_frame, textvariable=self.draw_model_var, values=SUPPORTED_DRAW_MODELS,
            state="readonly", width=20
        )
        draw_model_combo.grid(row=0, column=1, padx=5, pady=3)
        draw_model_combo.bind("<<ComboboxSelected>>", self._on_draw_model_change)

        # 图像比例
        ttk.Label(basic_frame, text="图像比例：").grid(row=0, column=2, padx=5, pady=3, sticky=tk.W)
        self.draw_aspect_ratio = tk.StringVar(value=ASPECT_RATIO_OPTIONS_DRAW[0])
        aspect_combo = ttk.Combobox(
            basic_frame, textvariable=self.draw_aspect_ratio, values=ASPECT_RATIO_OPTIONS_DRAW,
            state="readonly", width=10
        )
        aspect_combo.grid(row=0, column=3, padx=5, pady=3)

        # 分辨率
        ttk.Label(basic_frame, text="分辨率：").grid(row=0, column=4, padx=5, pady=3, sticky=tk.W)
        self.draw_image_size = tk.StringVar(value=IMAGE_SIZE_OPTIONS[0])
        self.size_combo_draw = ttk.Combobox(
            basic_frame, textvariable=self.draw_image_size, values=IMAGE_SIZE_OPTIONS,
            state="readonly", width=10
        )
        self.size_combo_draw.grid(row=0, column=5, padx=5, pady=3)

        # 2. 提示词配置（三输入框）
        prompt_frame = ttk.LabelFrame(param_frame, text="提示词配置（自动保存前缀/后缀）")
        prompt_frame.pack(fill=tk.X, pady=5)

        # 前缀提示词
        ttk.Label(prompt_frame, text="前缀提示词：").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        self.draw_prefix_text = scrolledtext.ScrolledText(
            prompt_frame, wrap=tk.WORD, font=("微软雅黑", 10), height=2
        )
        self.draw_prefix_text.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
        # 加载缓存的前缀提示词
        cached_prefix = get_cached_value(CACHE_KEY_DRAW_PREFIX)
        if cached_prefix:
            self.draw_prefix_text.insert(tk.END, cached_prefix)
        # 失去焦点时自动保存
        self.draw_prefix_text.bind("<FocusOut>", lambda e: self._save_draw_prefix())

        # 主体提示词
        ttk.Label(prompt_frame, text="主体提示词：").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W)
        self.draw_main_text = scrolledtext.ScrolledText(
            prompt_frame, wrap=tk.WORD, font=("微软雅黑", 10), height=4
        )
        self.draw_main_text.grid(row=1, column=1, padx=5, pady=3, sticky=tk.EW)

        # 后缀提示词
        ttk.Label(prompt_frame, text="后缀提示词：").grid(row=2, column=0, padx=5, pady=3, sticky=tk.W)
        self.draw_suffix_text = scrolledtext.ScrolledText(
            prompt_frame, wrap=tk.WORD, font=("微软雅黑", 10), height=2
        )
        self.draw_suffix_text.grid(row=2, column=1, padx=5, pady=3, sticky=tk.EW)
        # 加载缓存的后缀提示词
        cached_suffix = get_cached_value(CACHE_KEY_DRAW_SUFFIX)
        if cached_suffix:
            self.draw_suffix_text.insert(tk.END, cached_suffix)
        # 失去焦点时自动保存
        self.draw_suffix_text.bind("<FocusOut>", lambda e: self._save_draw_suffix())

        # 设置列权重
        prompt_frame.columnconfigure(1, weight=1)

        # 3. 参考图配置
        ref_frame = ttk.Frame(param_frame)
        ref_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ref_frame, text="参考图：").pack(side=tk.LEFT, padx=5)
        select_ref_btn = ttk.Button(
            ref_frame, text="选择参考图（最多5张）", command=self._select_draw_ref_images
        )
        select_ref_btn.pack(side=tk.LEFT, padx=5)
        clear_ref_btn = ttk.Button(
            ref_frame, text="清空参考图", command=self._clear_draw_ref_images
        )
        clear_ref_btn.pack(side=tk.LEFT, padx=5)

        # 参考图预览区
        self.draw_ref_frame = ttk.Frame(param_frame)
        self.draw_ref_frame.pack(fill=tk.X, pady=5)

        # 4. 高级配置
        adv_frame = ttk.Frame(param_frame)
        adv_frame.pack(fill=tk.X, pady=5)

        ttk.Label(adv_frame, text="WebHook：").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        self.draw_webhook = ttk.Entry(adv_frame, width=30)
        self.draw_webhook.insert(0, DEFAULT_WEBHOOK)  # 强制设为-1
        self.draw_webhook.grid(row=0, column=1, padx=5, pady=3)

        self.draw_shut_progress = tk.BooleanVar(value=DEFAULT_SHUT_PROGRESS)
        shut_progress_check = ttk.Checkbutton(
            adv_frame, text="关闭进度推送", variable=self.draw_shut_progress
        )
        shut_progress_check.grid(row=0, column=2, padx=5, pady=3)

        # 操作按钮区
        btn_frame = ttk.Frame(draw_tab, padding="10")
        btn_frame.pack(fill=tk.X)

        self.generate_draw_btn = ttk.Button(
            btn_frame, text="生成图片", command=self._generate_draw
        )
        self.generate_draw_btn.pack(side=tk.LEFT, padx=5)

        # 任务ID显示
        ttk.Label(btn_frame, text="任务ID：").pack(side=tk.LEFT, padx=5)
        self.current_draw_task_id = ttk.Entry(btn_frame, width=30)
        self.current_draw_task_id.pack(side=tk.LEFT, padx=5)

        # 结果显示区
        result_frame = ttk.LabelFrame(draw_tab, text="生成日志", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.draw_result_text = scrolledtext.ScrolledText(
            result_frame, wrap=tk.WORD, font=("微软雅黑", 10), state=tk.DISABLED
        )
        self.draw_result_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 提示信息
        hint_label = ttk.Label(draw_tab, text="✅ 任务提交后请在【任务管理】标签页查看进度和结果", foreground="green")
        hint_label.pack(pady=5)

        # 初始化分辨率状态
        self._update_draw_size_state()

    def _save_draw_prefix(self):
        """保存绘画前缀提示词到缓存"""
        prefix = self.draw_prefix_text.get(1.0, tk.END).strip()
        if prefix:
            save_cached_value(CACHE_KEY_DRAW_PREFIX, prefix, "保存绘画前缀提示词")

    def _save_draw_suffix(self):
        """保存绘画后缀提示词到缓存"""
        suffix = self.draw_suffix_text.get(1.0, tk.END).strip()
        if suffix:
            save_cached_value(CACHE_KEY_DRAW_SUFFIX, suffix, "保存绘画后缀提示词")

    def _on_draw_model_change(self, event):
        """切换绘画模型"""
        self.current_draw_model = self.draw_model_var.get()
        self._update_draw_size_state()
        self._append_draw_result(f"系统：已切换至 {self.current_draw_model} 模型")

    def _update_draw_size_state(self):
        """更新分辨率可选状态（仅Pro版支持高分辨率）"""
        if self.current_draw_model == "nano-banana-pro" or self.current_draw_model == "nano-banana-pro-vt":
            self.size_combo_draw.configure(state="readonly")
        else:
            self.size_combo_draw.configure(state="disabled")
            self.draw_image_size.set("1K")

    def _select_draw_ref_images(self):
        """选择绘画参考图"""
        file_paths = filedialog.askopenfilenames(
            title="选择参考图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png"), ("所有文件", "*.*")]
        )
        if not file_paths:
            return

        # 检查数量限制
        if len(file_paths) + len(self.draw_ref_images) > MAX_REF_IMAGES:
            messagebox.showwarning("提示", f"最多只能选择{MAX_REF_IMAGES}张参考图！")
            file_paths = file_paths[:MAX_REF_IMAGES - len(self.draw_ref_images)]

        # 添加参考图
        for file_path in file_paths:
            try:
                # 转换为Base64
                base64_str = file_to_base64(file_path)
                if not base64_str:
                    continue

                # 创建预览缩略图
                image = Image.open(file_path)
                image.thumbnail(THUMBNAIL_SIZE)
                photo = ImageTk.PhotoImage(image)

                # 保存参考图信息
                self.draw_ref_images.append({
                    "path": file_path,
                    "base64": base64_str,
                    "photo": photo
                })

                # 创建预览标签
                ref_label = ttk.Label(self.draw_ref_frame, image=photo)
                ref_label.image = photo  # 防止GC
                ref_label.pack(side=tk.LEFT, padx=5, pady=5)

                self._append_draw_result(f"已添加参考图：{os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("错误", f"处理参考图失败：{str(e)}")

    def _clear_draw_ref_images(self):
        """清空绘画参考图"""
        self.draw_ref_images.clear()
        for widget in self.draw_ref_frame.winfo_children():
            widget.destroy()
        self._append_draw_result("已清空所有参考图")

    def _append_draw_result(self, text):
        """追加绘画日志"""
        self.draw_result_text.config(state=tk.NORMAL)
        self.draw_result_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.draw_result_text.see(tk.END)
        self.draw_result_text.config(state=tk.DISABLED)

    def _generate_draw(self):
        """生成图片（移除独立轮询，仅提交任务并记录TaskID）"""
        if self.is_draw_requesting:
            messagebox.showwarning("提示", "图片生成中，请稍候！")
            return

        api_key = self.api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请先输入并保存API-Key！")
            return

        # 获取并拼接提示词
        prefix = self.draw_prefix_text.get(1.0, tk.END).strip()
        main = self.draw_main_text.get(1.0, tk.END).strip()
        suffix = self.draw_suffix_text.get(1.0, tk.END).strip()

        if not main:
            messagebox.showwarning("提示", "主体提示词不能为空！")
            return

        full_prompt = f"{prefix} {main} {suffix}".strip()

        # 强制WebHook为-1（确保同步返回TaskID）
        webhook = self.draw_webhook.get().strip() or DEFAULT_WEBHOOK
        if webhook != "-1":
            self.draw_webhook.delete(0, tk.END)
            self.draw_webhook.insert(0, "-1")
            webhook = "-1"
            self._append_draw_result("警告：WebHook已强制设为-1（确保同步返回TaskID）")

        # 构建请求参数
        payload = {
            "model": self.current_draw_model,
            "prompt": full_prompt,
            "aspectRatio": self.draw_aspect_ratio.get(),
            "imageSize": self.draw_image_size.get(),
            "urls": [img["base64"] for img in self.draw_ref_images],
            "webHook": webhook,
            "shutProgress": self.draw_shut_progress.get()
        }

        # 清空日志
        self.draw_result_text.config(state=tk.NORMAL)
        self.draw_result_text.delete(1.0, tk.END)
        self.draw_result_text.config(state=tk.DISABLED)
        self.current_draw_task_id.delete(0, tk.END)

        # 标记请求中
        self.is_draw_requesting = True
        self.generate_draw_btn.config(state=tk.DISABLED)
        self._append_draw_result(f"开始生成图片，提示词：{full_prompt}")
        self._append_draw_result(f"使用模型：{self.current_draw_model}，分辨率：{self.draw_image_size.get()}")
        self._append_draw_result(f"WebHook：{webhook}（同步返回TaskID）")

        # 异步调用API
        def draw_api_call():
            base_url = HOST_OPTIONS[self.current_host.get()]
            url = f"{base_url}/v1/draw/nano-banana"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            try:
                # WebHook=-1时，API会同步返回TaskID，无需流式处理
                response = requests.post(
                    url, headers=headers, json=payload, stream=False, timeout=60
                )
                response.raise_for_status()

                # 解析响应（核心：精准提取TaskID）
                response_data = response.json()
                log_debug(f"绘画API响应原始数据：{json.dumps(response_data, ensure_ascii=False)}")

                # 优先提取TaskID（兼容所有字段名）
                task_id = None
                if response_data.get("code") == 0:
                    # 层级1：直接返回
                    task_id = response_data.get("id") or response_data.get("taskId") or response_data.get("task_id")
                    # 层级2：在data中
                    if not task_id and "data" in response_data:
                        task_id = response_data["data"].get("id") or response_data["data"].get("taskId") or \
                                  response_data["data"].get("task_id")

                # 校验TaskID（WebHook=-1时必须返回）
                if not task_id or not isinstance(task_id, str) or task_id.strip() == "":
                    raise Exception(f"API未返回有效TaskID！响应数据：{json.dumps(response_data, ensure_ascii=False)}")

                # 立即更新TaskID显示
                self.root.after(0, lambda: self.current_draw_task_id.insert(0, task_id))
                self.root.after(0, lambda: self._append_draw_result(f"✅ 成功获取TaskID：{task_id}"))
                self.root.after(0, lambda: self._append_draw_result(
                    "📌 任务已提交至任务列表，请到【任务管理】标签页查看进度和结果"))

                # 立即创建任务记录（核心修复）
                new_task = {
                    "id": task_id,
                    "type": "draw",
                    "status": "running",
                    "progress": 0,
                    "prompt": full_prompt,
                    "model": self.current_draw_model,
                    "aspectRatio": self.draw_aspect_ratio.get(),
                    "imageSize": self.draw_image_size.get(),
                    "file_url": "",
                    "failure_reason": "",
                    "error": "",
                    "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "temp": False  # 非临时ID
                }

                # 去重添加任务
                task_exists = any(t.get("id") == task_id for t in self.tasks)
                if not task_exists:
                    self.tasks.append(new_task)
                    save_tasks(self.tasks)
                    self.root.after(0, self._update_task_tree)
                    log_debug(f"绘画任务已添加到列表：{task_id}")

                # 保存缓存
                save_cache({
                    "type": "draw_generate",
                    "task_id": task_id,
                    "prompt": full_prompt,
                    "model": self.current_draw_model,
                    "description": "生成NanoBanana图片（同步获取TaskID）"
                })

            except Exception as e:
                log_debug(f"绘画生成请求失败：{e}")
                error_msg = f"❌ 生成请求失败：{str(e)}"
                self.root.after(0, lambda: self._append_draw_result(error_msg))
                save_cache({
                    "type": "draw_error",
                    "error": str(e),
                    "description": "NanoBanana生成失败"
                })
            finally:
                self.is_draw_requesting = False
                self.root.after(0, lambda: self.generate_draw_btn.config(state=tk.NORMAL))

        threading.Thread(target=draw_api_call, daemon=True).start()

    # ===================== Sora2视频标签页（移除独立轮询） =====================
    def _create_video_tab(self):
        """创建Sora2视频标签页（三输入框提示词）"""
        video_tab = ttk.Frame(self.notebook)
        self.notebook.add(video_tab, text="Sora2 视频")

        # 参数配置区
        param_frame = ttk.LabelFrame(video_tab, text="视频参数配置", padding="10")
        param_frame.pack(fill=tk.X, anchor=tk.N, padx=10, pady=5)

        # 1. 基础配置
        basic_frame = ttk.Frame(param_frame)
        basic_frame.pack(fill=tk.X, pady=5)

        # 视频比例
        ttk.Label(basic_frame, text="视频比例：").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        self.video_aspect_ratio = tk.StringVar(value=ASPECT_RATIO_OPTIONS_VIDEO[0])
        aspect_combo = ttk.Combobox(
            basic_frame, textvariable=self.video_aspect_ratio, values=ASPECT_RATIO_OPTIONS_VIDEO,
            state="readonly", width=10
        )
        aspect_combo.grid(row=0, column=1, padx=5, pady=3)

        # 时长
        ttk.Label(basic_frame, text="时长(秒)：").grid(row=0, column=2, padx=5, pady=3, sticky=tk.W)
        self.video_duration = tk.IntVar(value=DURATION_OPTIONS[0])
        duration_combo = ttk.Combobox(
            basic_frame, textvariable=self.video_duration, values=DURATION_OPTIONS,
            state="readonly", width=10
        )
        duration_combo.grid(row=0, column=3, padx=5, pady=3)

        # 清晰度
        ttk.Label(basic_frame, text="清晰度：").grid(row=0, column=4, padx=5, pady=3, sticky=tk.W)
        self.video_size = tk.StringVar(value=SIZE_OPTIONS_VIDEO[0])
        size_combo = ttk.Combobox(
            basic_frame, textvariable=self.video_size, values=SIZE_OPTIONS_VIDEO,
            state="readonly", width=10
        )
        size_combo.grid(row=0, column=5, padx=5, pady=3)

        # 2. 提示词配置（三输入框）
        prompt_frame = ttk.LabelFrame(param_frame, text="提示词配置（自动保存前缀/后缀）")
        prompt_frame.pack(fill=tk.X, pady=5)

        # 前缀提示词
        ttk.Label(prompt_frame, text="前缀提示词：").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        self.video_prefix_text = scrolledtext.ScrolledText(
            prompt_frame, wrap=tk.WORD, font=("微软雅黑", 10), height=2
        )
        self.video_prefix_text.grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
        # 加载缓存的前缀提示词
        cached_prefix = get_cached_value(CACHE_KEY_VIDEO_PREFIX)
        if cached_prefix:
            self.video_prefix_text.insert(tk.END, cached_prefix)
        # 失去焦点时自动保存
        self.video_prefix_text.bind("<FocusOut>", lambda e: self._save_video_prefix())

        # 主体提示词
        ttk.Label(prompt_frame, text="主体提示词：").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W)
        self.video_main_text = scrolledtext.ScrolledText(
            prompt_frame, wrap=tk.WORD, font=("微软雅黑", 10), height=4
        )
        self.video_main_text.grid(row=1, column=1, padx=5, pady=3, sticky=tk.EW)

        # 后缀提示词
        ttk.Label(prompt_frame, text="后缀提示词：").grid(row=2, column=0, padx=5, pady=3, sticky=tk.W)
        self.video_suffix_text = scrolledtext.ScrolledText(
            prompt_frame, wrap=tk.WORD, font=("微软雅黑", 10), height=2
        )
        self.video_suffix_text.grid(row=2, column=1, padx=5, pady=3, sticky=tk.EW)
        # 加载缓存的后缀提示词
        cached_suffix = get_cached_value(CACHE_KEY_VIDEO_SUFFIX)
        if cached_suffix:
            self.video_suffix_text.insert(tk.END, cached_suffix)
        # 失去焦点时自动保存
        self.video_suffix_text.bind("<FocusOut>", lambda e: self._save_video_suffix())

        # 设置列权重
        prompt_frame.columnconfigure(1, weight=1)

        # 3. 参考图配置
        ref_frame = ttk.Frame(param_frame)
        ref_frame.pack(fill=tk.X, pady=5)

        ttk.Label(ref_frame, text="参考图：").pack(side=tk.LEFT, padx=5)
        select_ref_btn = ttk.Button(
            ref_frame, text="选择参考图（最多5张）", command=self._select_video_ref_images
        )
        select_ref_btn.pack(side=tk.LEFT, padx=5)
        clear_ref_btn = ttk.Button(
            ref_frame, text="清空参考图", command=self._clear_video_ref_images
        )
        clear_ref_btn.pack(side=tk.LEFT, padx=5)

        # 参考图预览区
        self.video_ref_frame = ttk.Frame(param_frame)
        self.video_ref_frame.pack(fill=tk.X, pady=5)

        # 4. 高级配置
        adv_frame = ttk.Frame(param_frame)
        adv_frame.pack(fill=tk.X, pady=5)

        # Remix ID
        ttk.Label(adv_frame, text="Remix ID：").grid(row=0, column=0, padx=5, pady=3, sticky=tk.W)
        self.video_remix_id = ttk.Entry(adv_frame, width=20)
        self.video_remix_id.grid(row=0, column=1, padx=5, pady=3)

        # 角色配置
        ttk.Label(adv_frame, text="角色配置：").grid(row=0, column=2, padx=5, pady=3, sticky=tk.W)
        self.video_characters = ttk.Entry(adv_frame, width=30)
        self.video_characters.grid(row=0, column=3, padx=5, pady=3)
        ttk.Label(adv_frame, text="格式：url,时间戳;...", font=("微软雅黑", 8)).grid(row=0, column=4, padx=5, pady=3)

        # WebHook（强制-1）
        ttk.Label(adv_frame, text="WebHook：").grid(row=1, column=0, padx=5, pady=3, sticky=tk.W)
        self.video_webhook = ttk.Entry(adv_frame, width=30)
        self.video_webhook.insert(0, DEFAULT_WEBHOOK)  # 强制设为-1
        self.video_webhook.grid(row=1, column=1, padx=5, pady=3)

        self.video_shut_progress = tk.BooleanVar(value=DEFAULT_SHUT_PROGRESS)
        shut_progress_check = ttk.Checkbutton(
            adv_frame, text="关闭进度推送", variable=self.video_shut_progress
        )
        shut_progress_check.grid(row=1, column=2, padx=5, pady=3)

        # 操作按钮区
        btn_frame = ttk.Frame(video_tab, padding="10")
        btn_frame.pack(fill=tk.X)

        self.generate_video_btn = ttk.Button(
            btn_frame, text="生成视频", command=self._generate_video
        )
        self.generate_video_btn.pack(side=tk.LEFT, padx=5)

        # 任务ID显示
        ttk.Label(btn_frame, text="任务ID：").pack(side=tk.LEFT, padx=5)
        self.current_video_task_id = ttk.Entry(btn_frame, width=30)
        self.current_video_task_id.pack(side=tk.LEFT, padx=5)

        # 结果显示区
        result_frame = ttk.LabelFrame(video_tab, text="生成日志", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.video_result_text = scrolledtext.ScrolledText(
            result_frame, wrap=tk.WORD, font=("微软雅黑", 10), state=tk.DISABLED
        )
        self.video_result_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 提示信息
        hint_label = ttk.Label(video_tab, text="✅ 任务提交后请在【任务管理】标签页查看进度和结果", foreground="green")
        hint_label.pack(pady=5)

    def _save_video_prefix(self):
        """保存视频前缀提示词到缓存"""
        prefix = self.video_prefix_text.get(1.0, tk.END).strip()
        if prefix:
            save_cached_value(CACHE_KEY_VIDEO_PREFIX, prefix, "保存视频前缀提示词")

    def _save_video_suffix(self):
        """保存视频后缀提示词到缓存"""
        suffix = self.video_suffix_text.get(1.0, tk.END).strip()
        if suffix:
            save_cached_value(CACHE_KEY_VIDEO_SUFFIX, suffix, "保存视频后缀提示词")

    def _select_video_ref_images(self):
        """选择视频参考图"""
        file_paths = filedialog.askopenfilenames(
            title="选择参考图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png"), ("所有文件", "*.*")]
        )
        if not file_paths:
            return

        if len(file_paths) + len(self.video_ref_images) > MAX_REF_IMAGES:
            messagebox.showwarning("提示", f"最多只能选择{MAX_REF_IMAGES}张参考图！")
            file_paths = file_paths[:MAX_REF_IMAGES - len(self.video_ref_images)]

        for file_path in file_paths:
            try:
                base64_str = file_to_base64(file_path)
                if not base64_str:
                    continue

                image = Image.open(file_path)
                image.thumbnail(THUMBNAIL_SIZE)
                photo = ImageTk.PhotoImage(image)

                self.video_ref_images.append({
                    "path": file_path,
                    "base64": base64_str,
                    "photo": photo
                })

                ref_label = ttk.Label(self.video_ref_frame, image=photo)
                ref_label.image = photo
                ref_label.pack(side=tk.LEFT, padx=5, pady=5)

                self._append_video_result(f"已添加参考图：{os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("错误", f"处理参考图失败：{str(e)}")

    def _clear_video_ref_images(self):
        """清空视频参考图"""
        self.video_ref_images.clear()
        for widget in self.video_ref_frame.winfo_children():
            widget.destroy()
        self._append_video_result("已清空所有参考图")

    def _append_video_result(self, text):
        """追加视频日志"""
        self.video_result_text.config(state=tk.NORMAL)
        self.video_result_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.video_result_text.see(tk.END)
        self.video_result_text.config(state=tk.DISABLED)

    def _generate_video(self):
        """生成视频（移除独立轮询，仅提交任务并记录TaskID）"""
        if self.is_video_requesting:
            messagebox.showwarning("提示", "视频生成中，请稍候！")
            return

        api_key = self.api_key.get().strip()
        if not api_key:
            messagebox.showwarning("提示", "请先输入并保存API-Key！")
            return

        # 获取并拼接提示词
        prefix = self.video_prefix_text.get(1.0, tk.END).strip()
        main = self.video_main_text.get(1.0, tk.END).strip()
        suffix = self.video_suffix_text.get(1.0, tk.END).strip()

        if not main:
            messagebox.showwarning("提示", "主体提示词不能为空！")
            return

        full_prompt = f"{prefix} {main} {suffix}".strip()

        # 强制WebHook为-1（确保同步返回TaskID）
        webhook = self.video_webhook.get().strip() or DEFAULT_WEBHOOK
        if webhook != "-1":
            self.video_webhook.delete(0, tk.END)
            self.video_webhook.insert(0, "-1")
            webhook = "-1"
            self._append_video_result("警告：WebHook已强制设为-1（确保同步返回TaskID）")

        # 构建请求参数
        payload = {
            "model": DEFAULT_MODEL_VIDEO,
            "prompt": full_prompt,
            "aspectRatio": self.video_aspect_ratio.get(),
            "duration": self.video_duration.get(),
            "size": self.video_size.get(),
            "url": self.video_ref_images[0]["base64"] if self.video_ref_images else "",
            "remixTargetId": self.video_remix_id.get().strip(),
            "characters": [],
            "webHook": webhook,
            "shutProgress": self.video_shut_progress.get()
        }

        # 解析角色配置
        char_input = self.video_characters.get().strip()
        if char_input:
            try:
                chars = []
                for char in char_input.split(";"):
                    if "," in char:
                        url, ts = char.split(",", 1)
                        chars.append({"url": url.strip(), "timestamps": ts.strip()})
                payload["characters"] = chars
            except:
                messagebox.showwarning("提示", "角色配置格式错误！请使用：url,时间戳;url2,时间戳2")

        # 清空日志
        self.video_result_text.config(state=tk.NORMAL)
        self.video_result_text.delete(1.0, tk.END)
        self.video_result_text.config(state=tk.DISABLED)
        self.current_video_task_id.delete(0, tk.END)

        # 标记请求中
        self.is_video_requesting = True
        self.generate_video_btn.config(state=tk.DISABLED)
        self._append_video_result(f"开始生成视频，提示词：{full_prompt}")
        self._append_video_result(f"时长：{self.video_duration.get()}秒，清晰度：{self.video_size.get()}")
        self._append_video_result(f"WebHook：{webhook}（同步返回TaskID）")

        # 异步调用API
        def video_api_call():
            base_url = HOST_OPTIONS[self.current_host.get()]
            url = f"{base_url}/v1/video/sora-video"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            try:
                # WebHook=-1时，API会同步返回TaskID，无需流式处理
                response = requests.post(
                    url, headers=headers, json=payload, stream=False, timeout=60
                )
                response.raise_for_status()

                # 解析响应（核心：精准提取TaskID）
                response_data = response.json()
                log_debug(f"视频API响应原始数据：{json.dumps(response_data, ensure_ascii=False)}")

                # 优先提取TaskID（兼容所有字段名）
                task_id = None
                if response_data.get("code") == 0:
                    # 层级1：直接返回
                    task_id = response_data.get("id") or response_data.get("taskId") or response_data.get("task_id")
                    # 层级2：在data中
                    if not task_id and "data" in response_data:
                        task_id = response_data["data"].get("id") or response_data["data"].get("taskId") or \
                                  response_data["data"].get("task_id")

                # 校验TaskID（WebHook=-1时必须返回）
                if not task_id or not isinstance(task_id, str) or task_id.strip() == "":
                    raise Exception(f"API未返回有效TaskID！响应数据：{json.dumps(response_data, ensure_ascii=False)}")

                # 立即更新TaskID显示
                self.root.after(0, lambda: self.current_video_task_id.insert(0, task_id))
                self.root.after(0, lambda: self._append_video_result(f"✅ 成功获取TaskID：{task_id}"))
                self.root.after(0, lambda: self._append_video_result(
                    "📌 任务已提交至任务列表，请到【任务管理】标签页查看进度和结果"))

                # 立即创建任务记录（核心修复）
                new_task = {
                    "id": task_id,
                    "type": "video",
                    "status": "running",
                    "progress": 0,
                    "prompt": full_prompt,
                    "model": DEFAULT_MODEL_VIDEO,
                    "aspectRatio": self.video_aspect_ratio.get(),
                    "duration": self.video_duration.get(),
                    "size": self.video_size.get(),
                    "file_url": "",
                    "failure_reason": "",
                    "error": "",
                    "create_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "temp": False  # 非临时ID
                }

                # 去重添加任务
                task_exists = any(t.get("id") == task_id for t in self.tasks)
                if not task_exists:
                    self.tasks.append(new_task)
                    save_tasks(self.tasks)
                    self.root.after(0, self._update_task_tree)
                    log_debug(f"视频任务已添加到列表：{task_id}")

                # 保存缓存
                save_cache({
                    "type": "video_generate",
                    "task_id": task_id,
                    "prompt": full_prompt,
                    "model": DEFAULT_MODEL_VIDEO,
                    "description": "生成Sora2视频（同步获取TaskID）"
                })

            except Exception as e:
                log_debug(f"视频生成请求失败：{e}")
                error_msg = f"❌ 生成请求失败：{str(e)}"
                self.root.after(0, lambda: self._append_video_result(error_msg))
                save_cache({
                    "type": "video_error",
                    "error": str(e),
                    "description": "Sora2生成失败"
                })
            finally:
                self.is_video_requesting = False
                self.root.after(0, lambda: self.generate_video_btn.config(state=tk.NORMAL))

        threading.Thread(target=video_api_call, daemon=True).start()

    # ===================== 任务管理标签页（支持多选+批量下载） =====================
    def _create_task_tab(self):
        """创建任务管理标签页（支持多选+批量下载）"""
        task_tab = ttk.Frame(self.notebook)
        self.notebook.add(task_tab, text="任务管理（绘画+视频）")

        # 任务控制区
        ctrl_frame = ttk.Frame(task_tab, padding="10")
        ctrl_frame.pack(fill=tk.X, anchor=tk.N)

        # 自动刷新开关
        self.refresh_var = tk.BooleanVar(value=self.is_refreshing)
        refresh_check = ttk.Checkbutton(
            ctrl_frame, text="自动刷新任务（5秒/次）", variable=self.refresh_var,
            command=self._toggle_refresh
        )
        refresh_check.pack(side=tk.LEFT, padx=5)

        # 手动刷新按钮
        refresh_btn = ttk.Button(
            ctrl_frame, text="手动刷新任务", command=self._manual_refresh_tasks
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)

        # 清空已完成任务
        clear_btn = ttk.Button(
            ctrl_frame, text="清空已完成/失败任务", command=self._clear_finished_tasks
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

        # 任务列表区
        list_frame = ttk.LabelFrame(task_tab, text="任务列表（支持Ctrl/Shift多选）", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建任务表格（设置为多选模式）
        columns = ("id", "type", "status", "progress", "prompt", "file_url", "create_time")
        self.task_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=15, selectmode="extended"  # 关键：extended支持多选
        )

        # 设置列标题和宽度
        column_widths = {
            "id": 120,
            "type": 80,
            "status": 80,
            "progress": 80,
            "prompt": 300,
            "file_url": 400,
            "create_time": 150
        }
        for col in columns:
            self.task_tree.heading(col, text=col)
            self.task_tree.column(col, width=column_widths[col], minwidth=80)

        # 滚动条配置
        task_scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        task_scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.task_tree.xview)
        self.task_tree.configure(yscrollcommand=task_scroll_y.set, xscrollcommand=task_scroll_x.set)

        # 布局
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 布局补全
        task_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        task_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 任务操作区（新增批量操作按钮）
        op_frame = ttk.Frame(task_tab, padding="10")
        op_frame.pack(fill=tk.X)

        # 批量打开URL
        batch_open_url_btn = ttk.Button(
            op_frame, text="批量打开选中文件URL", command=self._batch_open_task_url
        )
        batch_open_url_btn.pack(side=tk.LEFT, padx=5)

        # 批量保存文件（核心新增）
        batch_download_btn = ttk.Button(
            op_frame, text="批量保存选中文件", command=self._batch_download_task_files
        )
        batch_download_btn.pack(side=tk.LEFT, padx=5)

        # 打开单个URL（保留原有功能）
        open_url_btn = ttk.Button(
            op_frame, text="打开选中文件URL", command=self._open_task_url
        )
        open_url_btn.pack(side=tk.LEFT, padx=5)

        # 一键保存单个文件（保留原有功能）
        download_btn = ttk.Button(
            op_frame, text="一键保存选中文件", command=self._download_task_file
        )
        download_btn.pack(side=tk.LEFT, padx=5)

        # 查看详情（仅支持单个选中）
        detail_btn = ttk.Button(
            op_frame, text="查看任务详情", command=self._show_task_detail
        )
        detail_btn.pack(side=tk.LEFT, padx=5)

        # 批量删除任务（新增）
        batch_delete_btn = ttk.Button(
            op_frame, text="批量删除选中任务", command=self._batch_delete_selected_tasks
        )
        batch_delete_btn.pack(side=tk.LEFT, padx=5)

        # 删除单个任务（保留原有功能）
        delete_btn = ttk.Button(
            op_frame, text="删除选中任务", command=self._delete_selected_task
        )
        delete_btn.pack(side=tk.LEFT, padx=5)

        # 初始化任务列表
        self._update_task_tree()

    # ===================== 多选批量操作核心方法 =====================
    def _batch_open_task_url(self):
        """批量打开选中任务的文件URL"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中至少一个任务！")
            return

        success_count = 0
        fail_count = 0
        fail_tasks = []

        for item_id in selected:
            item = self.task_tree.item(item_id)
            file_url = item["values"][5]
            task_id = item["values"][0]

            if not file_url or not file_url.startswith("http"):
                fail_count += 1
                fail_tasks.append(task_id)
                continue

            try:
                webbrowser.open(file_url)
                success_count += 1
                # 记录缓存
                save_cache({
                    "type": "batch_open_url",
                    "task_id": task_id,
                    "url": file_url,
                    "description": "批量打开任务URL"
                })
            except Exception as e:
                fail_count += 1
                fail_tasks.append(f"{task_id}（{str(e)}）")

        # 结果提示
        msg = f"批量打开完成！\n成功：{success_count}个\n失败：{fail_count}个"
        if fail_tasks:
            msg += f"\n失败任务ID：{', '.join(fail_tasks)}"
        messagebox.showinfo("批量操作结果", msg)

    def _batch_download_task_files(self):
        """批量保存选中任务的文件"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中至少一个任务！")
            return

        # 选择保存目录（批量下载统一保存到指定文件夹）
        save_dir = filedialog.askdirectory(title="选择批量保存目录")
        if not save_dir:
            return

        # 异步批量下载（避免UI卡顿）
        def batch_download():
            success_count = 0
            fail_count = 0
            fail_tasks = []

            for item_id in selected:
                item = self.task_tree.item(item_id)
                task_id = item["values"][0]
                task_type = item["values"][1]
                file_url = item["values"][5]

                if not file_url or not file_url.startswith("http"):
                    fail_count += 1
                    fail_tasks.append(task_id)
                    continue

                # 自动匹配扩展名
                ext = ".jpg" if task_type == "draw" else ".mp4"
                file_name = f"{task_type}_{task_id}{ext}"
                save_path = os.path.join(save_dir, file_name)

                try:
                    # 调用下载函数（带进度）
                    urllib.request.urlretrieve(file_url, save_path)
                    success_count += 1
                    # 记录缓存
                    save_cache({
                        "type": "batch_download",
                        "task_id": task_id,
                        "save_path": save_path,
                        "description": "批量下载任务文件"
                    })
                except Exception as e:
                    fail_count += 1
                    fail_tasks.append(f"{task_id}（{str(e)}）")

            # 主线程提示结果
            self.root.after(0, lambda: self._show_batch_result(success_count, fail_count, fail_tasks))

        # 启动下载线程
        threading.Thread(target=batch_download, daemon=True).start()
        messagebox.showinfo("提示", "批量下载已开始！请等待完成提示（大文件可能耗时较长）")

    def _show_batch_result(self, success, fail, fail_tasks):
        """显示批量操作结果"""
        msg = f"批量下载完成！\n成功：{success}个\n失败：{fail}个"
        if fail_tasks:
            msg += f"\n失败任务ID：{', '.join(fail_tasks)}"
        messagebox.showinfo("批量下载结果", msg)

    def _batch_delete_selected_tasks(self):
        """批量删除选中任务"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中至少一个任务！")
            return

        # 确认删除
        if not messagebox.askyesno("确认", f"确定删除选中的{len(selected)}个任务？此操作不可恢复！"):
            return

        # 收集要删除的任务ID
        delete_task_ids = []
        for item_id in selected:
            item = self.task_tree.item(item_id)
            task_id = item["values"][0]
            delete_task_ids.append(task_id)

        # 移除任务
        self.tasks = [t for t in self.tasks if t.get("id") not in delete_task_ids]
        save_tasks(self.tasks)
        self._update_task_tree()

        # 记录缓存
        save_cache({
            "type": "batch_delete_tasks",
            "deleted_count": len(delete_task_ids),
            "deleted_task_ids": delete_task_ids,
            "description": "批量删除选中任务"
        })

        messagebox.showinfo("成功", f"已批量删除{len(delete_task_ids)}个任务！")

    # ===================== 原有单任务操作方法（兼容多选） =====================
    def _update_task_tree(self):
        """更新任务列表显示（线程安全）"""

        # 清空现有内容
        def clear_tree():
            for item in self.task_tree.get_children():
                self.task_tree.delete(item)

        self.root.after(0, clear_tree)

        # 按创建时间倒序排序
        sorted_tasks = sorted(
            self.tasks,
            key=lambda x: x.get("create_time", ""),
            reverse=True
        )

        # 插入任务数据
        def insert_tasks():
            for task in sorted_tasks:
                # 处理提示词截断
                prompt = task.get("prompt", "")
                if len(prompt) > 50:
                    prompt = prompt[:50] + "..."

                # 组装行数据
                values = (
                    task.get("id", ""),
                    task.get("type", ""),
                    task.get("status", ""),
                    f"{task.get('progress', 0)}%",
                    prompt,
                    task.get("file_url", ""),
                    task.get("create_time", "")
                )

                # 插入行并标记状态颜色
                item_id = self.task_tree.insert("", tk.END, values=values)
                status = task.get("status", "")
                if status == "running":
                    self.task_tree.item(item_id, tags=("running",))
                elif status == "succeeded":
                    self.task_tree.item(item_id, tags=("succeeded",))
                elif status == "failed":
                    self.task_tree.item(item_id, tags=("failed",))

        # 主线程执行UI操作
        self.root.after(0, insert_tasks)

        # 设置标签颜色
        self.task_tree.tag_configure("running", foreground="orange")
        self.task_tree.tag_configure("succeeded", foreground="green")
        self.task_tree.tag_configure("failed", foreground="red")

    def _start_refresh_thread(self):
        """启动自动刷新线程（防重复启动）"""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return

        def refresh_loop():
            while self.is_refreshing:
                try:
                    updated = False
                    # 只轮询运行中的任务
                    for i, task in enumerate(self.tasks):
                        if task.get("status") == "running":
                            result = self._poll_task_result(task["id"])
                            if result:
                                # 更新任务状态
                                self.tasks[i]["status"] = result.get("status", "running")
                                self.tasks[i]["progress"] = result.get("progress", 0)
                                self.tasks[i]["file_url"] = result.get("results", [{}])[0].get("url", "")
                                self.tasks[i]["failure_reason"] = result.get("failure_reason", "")
                                self.tasks[i]["error"] = result.get("error", "")
                                updated = True
                    # 有更新才保存并刷新UI
                    if updated:
                        save_tasks(self.tasks)
                        self.root.after(0, self._update_task_tree)
                except Exception as e:
                    log_debug(f"自动刷新失败：{e}")
                time.sleep(REFRESH_INTERVAL)

        self.refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        self.refresh_thread.start()
        log_debug("任务自动刷新线程已启动")

    def _toggle_refresh(self):
        """切换自动刷新状态"""
        self.is_refreshing = self.refresh_var.get()
        status = "开启" if self.is_refreshing else "关闭"
        messagebox.showinfo("提示", f"任务自动刷新已{status}")
        if self.is_refreshing and (not self.refresh_thread or not self.refresh_thread.is_alive()):
            self._start_refresh_thread()

    def _manual_refresh_tasks(self):
        """手动刷新所有任务"""

        def refresh():
            updated_count = 0
            try:
                for i, task in enumerate(self.tasks):
                    if task.get("status") == "running":
                        result = self._poll_task_result(task["id"])
                        if result:
                            self.tasks[i]["status"] = result.get("status", "running")
                            self.tasks[i]["progress"] = result.get("progress", 0)
                            self.tasks[i]["file_url"] = result.get("results", [{}])[0].get("url", "")
                            self.tasks[i]["failure_reason"] = result.get("failure_reason", "")
                            self.tasks[i]["error"] = result.get("error", "")
                            updated_count += 1
                save_tasks(self.tasks)
                self.root.after(0, self._update_task_tree)
                self.root.after(0, lambda: messagebox.showinfo("提示", f"手动刷新完成！更新了{updated_count}个任务"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"手动刷新失败：{str(e)}"))

        threading.Thread(target=refresh, daemon=True).start()

    def _poll_task_result(self, task_id):
        """通用任务轮询接口（兼容绘画/视频）"""
        api_key = self.api_key.get().strip()
        if not api_key or not task_id:
            return None

        base_url = HOST_OPTIONS[self.current_host.get()]
        poll_urls = [
            f"{base_url}/v1/task/result",
            f"{base_url}/v1/draw/result",
            f"{base_url}/v1/video/result"
        ]

        for url in poll_urls:
            try:
                response = requests.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}"
                    },
                    json={"id": task_id},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        return data.get("data", {})
            except Exception as e:
                log_debug(f"轮询接口 {url} 失败：{e}")
                continue
        return None

    def _clear_finished_tasks(self):
        """清空已完成/失败任务"""
        if not self.tasks:
            messagebox.showinfo("提示", "暂无任务可清空！")
            return

        # 保留运行中任务
        unfinished = [t for t in self.tasks if t.get("status") == "running"]
        cleared = len(self.tasks) - len(unfinished)

        # 更新任务列表
        self.tasks = unfinished
        save_tasks(self.tasks)
        self._update_task_tree()

        # 记录缓存
        save_cache({
            "type": "clear_finished_tasks",
            "cleared_count": cleared,
            "remaining": len(unfinished),
            "description": "清空已完成/失败任务"
        })

        messagebox.showinfo("提示", f"已清空{cleared}个任务，剩余{len(unfinished)}个运行中任务")

    def _open_task_url(self):
        """打开选中任务的文件URL（单任务）"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中任务！")
            return

        # 仅处理第一个选中项
        item = self.task_tree.item(selected[0])
        file_url = item["values"][5]

        if not file_url or not file_url.startswith("http"):
            messagebox.showwarning("提示", "无有效文件URL！")
            return

        try:
            webbrowser.open(file_url)
            save_cache({
                "type": "open_task_url",
                "task_id": item["values"][0],
                "url": file_url,
                "description": "打开任务文件URL"
            })
        except Exception as e:
            messagebox.showerror("错误", f"打开URL失败：{str(e)}")

    def _download_task_file(self):
        """下载选中任务的文件（单任务）"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中任务！")
            return

        # 仅处理第一个选中项
        item = self.task_tree.item(selected[0])
        task_id = item["values"][0]
        task_type = item["values"][1]
        file_url = item["values"][5]

        if not file_url or not file_url.startswith("http"):
            messagebox.showwarning("提示", "无有效文件URL！")
            return

        # 自动匹配文件扩展名
        ext = ".jpg" if task_type == "draw" else ".mp4"
        default_name = f"{task_type}_{task_id}{ext}"

        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            title=f"保存{task_type.upper()}文件",
            defaultextension=ext,
            initialfile=default_name,
            filetypes=[(f"{task_type}文件", f"*{ext}"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        # 异步下载
        def download():
            try:
                download_file(file_url, file_path)
                save_cache({
                    "type": "download_task_file",
                    "task_id": task_id,
                    "save_path": file_path,
                    "description": "下载任务文件"
                })
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"下载失败：{str(e)}"))

        threading.Thread(target=download, daemon=True).start()

    def _show_task_detail(self):
        """查看任务详情（仅支持单个选中）"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中任务！")
            return
        # 仅处理第一个选中项
        if len(selected) > 1:
            messagebox.showwarning("提示", "仅支持查看单个任务的详情，请只选中一个任务！")
            return

        # 获取任务ID
        item = self.task_tree.item(selected[0])
        task_id = item["values"][0]

        # 查找任务详情
        task_detail = None
        for task in self.tasks:
            if task.get("id") == task_id:
                task_detail = task
                break

        if not task_detail:
            messagebox.showwarning("提示", "未找到任务详情！")
            return

        # 构建详情文本
        detail_text = "===== 任务详情 =====\n"
        for k, v in task_detail.items():
            if v is None:
                v = ""
            detail_text += f"{k}：{v}\n"

        # 弹窗显示
        detail_win = tk.Toplevel(self.root)
        detail_win.title(f"任务详情 - {task_id}")
        detail_win.geometry("800x600")
        detail_win.resizable(True, True)

        # 详情文本框
        text_widget = scrolledtext.ScrolledText(
            detail_win, wrap=tk.WORD, font=("微软雅黑", 10)
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, detail_text)
        text_widget.config(state=tk.DISABLED)

        # 复制按钮
        copy_btn = ttk.Button(
            detail_win, text="复制详情",
            command=lambda: self._copy_to_clipboard(detail_text)
        )
        copy_btn.pack(pady=5)

    def _delete_selected_task(self):
        """删除选中任务（单任务）"""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中任务！")
            return
        # 仅处理第一个选中项
        if len(selected) > 1:
            messagebox.showwarning("提示", "仅支持删除单个任务，请只选中一个任务！")
            return

        # 确认删除
        if not messagebox.askyesno("确认", "确定删除选中任务？此操作不可恢复！"):
            return

        # 获取任务ID
        item = self.task_tree.item(selected[0])
        task_id = item["values"][0]

        # 移除任务
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        save_tasks(self.tasks)
        self._update_task_tree()

        # 记录缓存
        save_cache({
            "type": "delete_task",
            "task_id": task_id,
            "description": "删除选中任务"
        })

        messagebox.showinfo("成功", f"任务 {task_id} 已删除！")

    def _copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("成功", "详情已复制到剪贴板！")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败：{str(e)}")

    # ===================== 缓存管理标签页（完整实现） =====================
    def _create_cache_tab(self):
        """创建缓存管理标签页"""
        cache_tab = ttk.Frame(self.notebook)
        self.notebook.add(cache_tab, text="缓存管理")

        # 缓存显示区
        display_frame = ttk.LabelFrame(cache_tab, text="缓存记录（24小时内）", padding="10")
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.cache_text = scrolledtext.ScrolledText(
            display_frame, wrap=tk.WORD, font=("微软雅黑", 9), state=tk.DISABLED
        )
        self.cache_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 操作按钮区
        btn_frame = ttk.Frame(cache_tab, padding="10")
        btn_frame.pack(fill=tk.X)

        # 刷新缓存
        refresh_cache_btn = ttk.Button(btn_frame, text="刷新缓存列表", command=self._refresh_cache_display)
        refresh_cache_btn.pack(side=tk.LEFT, padx=5)

        # 清空缓存
        clear_cache_btn = ttk.Button(btn_frame, text="清空所有缓存", command=self._clear_cache)
        clear_cache_btn.pack(side=tk.LEFT, padx=5)

        # 导出缓存
        export_cache_btn = ttk.Button(btn_frame, text="导出缓存记录", command=self._export_cache)
        export_cache_btn.pack(side=tk.LEFT, padx=5)

        # 恢复提示词
        restore_draw_btn = ttk.Button(btn_frame, text="恢复绘画提示词", command=self._restore_draw_prompt)
        restore_draw_btn.pack(side=tk.LEFT, padx=5)

        restore_video_btn = ttk.Button(btn_frame, text="恢复视频提示词", command=self._restore_video_prompt)
        restore_video_btn.pack(side=tk.LEFT, padx=5)

        # 初始化显示
        self._refresh_cache_display()

    def _refresh_cache_display(self):
        """刷新缓存显示"""
        self.cache_data = load_cache()

        # 更新文本框
        self.cache_text.config(state=tk.NORMAL)
        self.cache_text.delete(1.0, tk.END)

        if not self.cache_data:
            self.cache_text.insert(tk.END, "暂无缓存记录（仅保留24小时内）")
        else:
            # 按时间倒序显示
            sorted_cache = sorted(
                self.cache_data,
                key=lambda x: x.get("timestamp", 0),
                reverse=True
            )
            for i, item in enumerate(sorted_cache, 1):
                self.cache_text.insert(tk.END, f"===== 缓存记录 {i} =====\n")
                for k, v in item.items():
                    if k == "timestamp":
                        continue
                    self.cache_text.insert(tk.END, f"{k}：{v}\n")
                self.cache_text.insert(tk.END, "\n")

        self.cache_text.config(state=tk.DISABLED)

    def _clear_cache(self):
        """清空所有缓存"""
        if not self.cache_data:
            messagebox.showinfo("提示", "暂无缓存可清空！")
            return

        if messagebox.askyesno("确认", "确定清空所有缓存？提示词缓存也会被清除！"):
            save_cache(overwrite=True, cache_list=[])
            self.cache_data = []
            self._refresh_cache_display()
            messagebox.showinfo("成功", "所有缓存已清空！")

    def _export_cache(self):
        """导出缓存到JSON文件"""
        if not self.cache_data:
            messagebox.showwarning("提示", "暂无缓存可导出！")
            return

        file_path = filedialog.asksaveasfilename(
            title="导出缓存记录",
            defaultextension=".json",
            initialfile=f"cache_export_{time.strftime('%Y%m%d%H%M%S')}.json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding=DEFAULT_ENCODING) as f:
                    json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"缓存已导出到：{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败：{str(e)}")

    def _restore_draw_prompt(self):
        """恢复绘画提示词"""
        prefix = get_cached_value(CACHE_KEY_DRAW_PREFIX)
        suffix = get_cached_value(CACHE_KEY_DRAW_SUFFIX)

        if not prefix and not suffix:
            messagebox.showwarning("提示", "暂无绘画提示词缓存！")
            return

        if prefix:
            self.draw_prefix_text.delete(1.0, tk.END)
            self.draw_prefix_text.insert(tk.END, prefix)
        if suffix:
            self.draw_suffix_text.delete(1.0, tk.END)
            self.draw_suffix_text.insert(tk.END, suffix)

        messagebox.showinfo("成功", "绘画提示词已从缓存恢复！")

    def _restore_video_prompt(self):
        """恢复视频提示词"""
        prefix = get_cached_value(CACHE_KEY_VIDEO_PREFIX)
        suffix = get_cached_value(CACHE_KEY_VIDEO_SUFFIX)

        if not prefix and not suffix:
            messagebox.showwarning("提示", "暂无视频提示词缓存！")
            return

        if prefix:
            self.video_prefix_text.delete(1.0, tk.END)
            self.video_prefix_text.insert(tk.END, prefix)
        if suffix:
            self.video_suffix_text.delete(1.0, tk.END)
            self.video_suffix_text.insert(tk.END, suffix)

        messagebox.showinfo("成功", "视频提示词已从缓存恢复！")


# ===================== 程序入口 =====================
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = GRS_AIMultiTool_GUI(root)


        # 窗口关闭处理
        def on_closing():
            if messagebox.askokcancel("退出", "确定退出阿岳AI助手吗？"):
                # 保存任务和缓存
                save_tasks(app.tasks)
                app._save_draw_prefix()
                app._save_draw_suffix()
                app._save_video_prefix()
                app._save_video_suffix()
                root.destroy()


        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("启动失败", f"程序启动失败：{str(e)}")
        sys.exit(1)