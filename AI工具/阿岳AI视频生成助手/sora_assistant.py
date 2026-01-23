# -*- coding: utf-8 -*-
"""
Sora视频助手（完整优化版）
核心功能：
1.  任务创建（前缀/主体/后缀提示词，模板选择）
2.  任务管理（列表展示、进度跟踪、状态更新）
3.  新增可复制API ID列（完整显示，点击复制）
4.  优化表格列宽（复用/详情/操作列紧凑显示）
5.  详情窗口（无横向滚动、自动换行、Base64超长数据简写）
6.  视频下载（自动/手动下载，仅以任务ID命名，避免特殊字符）
7.  修复前缀模板选择延迟绑定问题
8.  屏蔽HTTPS不安全请求警告
9.  支持ICO文件打包（无需和EXE同目录）
10. 启动默认最大化窗口
11. 新增Markdown解析功能：基于markdown+bs4将MD转为纯文本
"""
import sys  # 新增：用于获取打包后的临时目录
import os
import tkinter as tk
from tkinter import filedialog, messagebox, Menu
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
import requests
import urllib3
import threading
import time
import json
import uuid
import base64
import re
from markdown_it import MarkdownIt
from mdit_plain.renderer import RendererPlain
from dataclasses import dataclass, field
from typing import List

# 屏蔽不安全的HTTPS请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==================== 资源路径兼容（打包/开发环境） ====================
def get_resource_path(relative_path):
    """
    获取打包后/开发环境下的资源文件路径
    :param relative_path: 资源文件的相对路径（如 "4odpx-r40oi-001.ico"）
    :return: 实际可用的绝对路径
    """
    try:
        # 打包后：PyInstaller 创建的临时目录（sys._MEIPASS）
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境：使用当前脚本所在目录
        base_path = os.path.abspath(".")

    # 拼接绝对路径
    return os.path.join(base_path, relative_path)


# ==================== 配置常量 ====================
APP_NAME = "Sora视频助手4.2"
ICON_FILE = get_resource_path("4odpx-r40oi-001.ico")  # 兼容打包/开发环境的ICO路径
API_FILE_PATH = "api.txt"
CONFIG_FILE = "config.json"
TASKS_CACHE_FILE = "tasks.json"
DEFAULT_DOWNLOAD_DIR = "./sora_videos"
MAX_HISTORY_COUNT = 10
VIDEO_DOWNLOAD_TIMEOUT = 300
MIN_VALID_VIDEO_SIZE = 10240

DEFAULT_API_HOSTS = [
    "https://grsai.dakka.com.cn",
    "https://grsaiapi.com"
]

DEFAULT_PREFIX_TEMPLATES = {
    "通用高清预设": "8K分辨率，超高画质，细节拉满，自然光，真实质感，电影级调色",
    "短视频优化": "横屏，适合大屏观看，动态构图，视觉冲击力强",
    "阿岳默认": "中国2D动漫，无字幕，无水印，无气泡，无背景音乐，有音效，转场流畅，运镜丝滑，",
    "无": ""
}

DEFAULT_MAIN_TEMPLATES = {
    "高清实拍风格": "高清实拍，8K分辨率，细节拉满，自然光，真实质感，电影级调色",
    "卡通动画风格": "卡通风格，迪士尼画风，色彩鲜艳，线条简洁，角色生动，动态流畅",
    "赛博朋克风格": "赛博朋克，霓虹灯光，未来都市，高对比度，蓝紫配色，科技感十足",
    "古风意境风格": "古风意境，水墨画风，山水元素，淡雅色调，传统服饰，诗意氛围",
    "无": ""
}

DEFAULT_SUFFIX_TEMPLATES = {
    "无水印/无文字": "无水印，无字幕，无文字，纯画面",
    "流畅动态": "无卡顿，无模糊，动态流畅，过渡自然",
    "无": ""
}


# ==================== Markdown解析工具函数（基于markdown+bs4） ====================
def parse_markdown_text_to_plain(md_text: str) -> str:
    """
    将Markdown文本解析为纯文本
    :param md_text: Markdown格式的文本内容
    :return: 提取后的纯文本字符串
    """
    if not md_text or md_text.strip() == "":
        return ""

    try:
        # 初始化MD解析器 + 纯文本渲染器
        md = MarkdownIt(renderer_cls=RendererPlain)
        # 解析并渲染为纯文本
        text = md.render(md_text)
        # 3. 清理多余的空行（保留单个空行）
        plain_text = "\n".join([line.strip() for line in text.split("\n") if line.strip()])

        return plain_text

    except Exception as e:
        print(f"Markdown解析失败：{str(e)}")
        # 解析失败时返回原始文本（避免内容丢失）
        return md_text.strip()


# ==================== 辅助函数：Base64判断与简写 ====================
def is_base64(s: str) -> bool:
    """判断字符串是否为标准超长Base64格式"""
    if not s:
        return False
    try:
        s_stripped = s.rstrip('=')
        if not re.fullmatch(r'[A-Za-z0-9+/]+', s_stripped):
            return False
        base64.b64decode(s, validate=True)
        return len(s) > 100
    except (base64.binascii.Error, ValueError):
        return False


def shorten_base64_in_data(data: dict or list or str) -> dict or list or str:
    """递归遍历数据，将超长Base64简写为"base64" """
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = shorten_base64_in_data(value)
        return data
    elif isinstance(data, list):
        return [shorten_base64_in_data(item) for item in data]
    elif isinstance(data, str) and is_base64(data):
        return "base64"
    else:
        return data


# ==================== 任务数据类 ====================
@dataclass
class SoraTask:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    prefix_prompt: str = ""
    main_prompt: str = ""
    suffix_prompt: str = ""
    full_prompt: str = ""
    ref_image_path: str = ""
    ref_image_base64: str = ""
    aspect_ratio: str = "16:9"
    duration: int = 15
    size: str = "small"
    status: str = "pending"
    progress: int = 0
    error: str = ""
    api_task_id: str = ""
    video_url: str = ""
    remove_watermark: bool = True
    download_path: str = ""
    download_failed: bool = False
    request_json: str = ""
    response_json: str = ""


# ==================== 配置读写函数 ====================
def load_config():
    default = {
        "download_dir": DEFAULT_DOWNLOAD_DIR,
        "prefix_history": [],
        "suffix_history": [],
        "prefix_templates": DEFAULT_PREFIX_TEMPLATES,
        "main_templates": DEFAULT_MAIN_TEMPLATES,
        "suffix_templates": DEFAULT_SUFFIX_TEMPLATES,
        "api_host": DEFAULT_API_HOSTS[0],
        "api_hosts": DEFAULT_API_HOSTS
    }
    if not os.path.exists(CONFIG_FILE):
        return default
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        default.update(data)
        return default
    except:
        return default


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except:
        pass


def read_api_key():
    if os.path.exists(API_FILE_PATH):
        try:
            with open(API_FILE_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except:
            return ""
    return ""


def save_api_key(key):
    try:
        with open(API_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(key.strip())
        return True
    except:
        return False


def save_tasks(tasks: List[SoraTask]):
    try:
        data = [vars(t) for t in tasks]
        with open(TASKS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass


def load_tasks() -> List[SoraTask]:
    if not os.path.exists(TASKS_CACHE_FILE):
        return []
    try:
        with open(TASKS_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [SoraTask(**item) for item in data]
    except:
        return []


# ==================== 工具函数 ====================
def image_to_base64(path: str) -> str:
    try:
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except:
        return ""


# ==================== 主程序类 ====================
class SoraVideoGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        # 关键修改：默认最大化窗口（替代固定尺寸1920x1000）
        self.root.state('zoomed')
        self.root.resizable(True, True)

        # 第一步：先初始化核心属性（避免属性不存在）
        self.log_text = None
        self.is_monitoring = False

        # 第二步：初始化自动提交/自动下载变量
        self.auto_submit = tk.BooleanVar(value=True)
        self.auto_download_video = tk.BooleanVar(value=True)

        # 第三步：加载配置和任务
        self.config = load_config()
        os.makedirs(self.config["download_dir"], exist_ok=True)

        self.api_key = tk.StringVar(value=read_api_key())
        self.api_host = tk.StringVar(value=self.config["api_host"])
        self.download_dir = tk.StringVar(value=self.config["download_dir"])
        self.aspect_ratio = tk.StringVar(value="16:9")
        self.duration = tk.StringVar(value="15")
        self.size = tk.StringVar(value="small")
        self.ref_image_path = tk.StringVar()

        self.prefix_history = self.config.get("prefix_history", [])
        self.suffix_history = self.config.get("suffix_history", [])
        self.prefix_templates = self.config.get("prefix_templates", DEFAULT_PREFIX_TEMPLATES)
        self.main_templates = self.config.get("main_templates", DEFAULT_MAIN_TEMPLATES)
        self.suffix_templates = self.config.get("suffix_templates", DEFAULT_SUFFIX_TEMPLATES)

        self.tasks = load_tasks()

        # 第四步：构建UI（创建log_text等UI组件）
        self._build_ui()

        # 第五步：加载窗口logo（此时log_text已就绪，可正常写入日志）
        self._load_window_icon()

        # 后续初始化步骤
        self._bind_events()
        self._update_task_tree()
        self._refresh_all_menus()
        self._start_monitor()

        self.log("🚀 Sora视频助手启动完成！")

    def _load_window_icon(self):
        """加载窗口logo（兼容打包/开发环境）"""
        if os.path.exists(ICON_FILE):
            try:
                self.root.iconbitmap(ICON_FILE)
                self.log(f"✅ 窗口logo加载成功：{ICON_FILE}")
            except Exception as e:
                self.log(f"⚠️  窗口logo加载失败（格式不兼容）：{str(e)}")
        else:
            self.log(f"⚠️  未找到logo文件：{ICON_FILE}，跳过logo加载")

    def _build_ui(self):
        # 主标签页
        self.notebook = ttkb.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.create_tab = ttkb.Frame(self.notebook)
        self.manage_tab = ttkb.Frame(self.notebook)
        self.notebook.add(self.create_tab, text="📝 任务创建")
        self.notebook.add(self.manage_tab, text="📊 任务管理")

        # 构建任务创建页
        self._build_create_tab()
        # 构建任务管理页
        self._build_manage_tab()

    def _build_create_tab(self):
        main_container = ttkb.Frame(self.create_tab)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # 提示词框架
        top_frame = ttkb.Frame(main_container)
        top_frame.pack(fill=X, pady=(0, 10))

        # 前缀提示词
        prefix_labelframe = ttkb.Labelframe(top_frame, text="🔧 前缀提示词（风格/画质预设）", padding=10)
        prefix_labelframe.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))
        prefix_btn = ttkb.Menubutton(prefix_labelframe, text="前缀模板", bootstyle="info")
        prefix_menu = Menu(prefix_btn, tearoff=0)
        prefix_btn["menu"] = prefix_menu
        self.prefix_menu = prefix_menu
        prefix_btn.pack(anchor=W)
        self.prefix_prompt = tk.Text(prefix_labelframe, height=4, wrap=WORD, font=("Arial", 10))
        self.prefix_prompt.pack(fill=X, pady=(5, 0))

        # 后缀提示词
        suffix_labelframe = ttkb.Labelframe(top_frame, text="✨ 后缀提示词（补充/优化）", padding=10)
        suffix_labelframe.pack(side=RIGHT, fill=BOTH, expand=True, padx=(5, 0))
        suffix_btn = ttkb.Menubutton(suffix_labelframe, text="后缀模板", bootstyle="warning")
        suffix_menu = Menu(suffix_btn, tearoff=0)
        suffix_btn["menu"] = suffix_menu
        self.suffix_menu = suffix_menu
        suffix_btn.pack(anchor=W)
        self.suffix_prompt = tk.Text(suffix_labelframe, height=4, wrap=WORD, font=("Arial", 10))
        self.suffix_prompt.pack(fill=X, pady=(5, 0))

        # 主体提示词
        main_labelframe = ttkb.Labelframe(main_container, text="🎯 主体提示词（核心描述）", padding=10)
        main_labelframe.pack(fill=BOTH, expand=True, pady=(0, 10))

        # 主体模板 + 解析MD按钮容器
        main_btn_frame = ttkb.Frame(main_labelframe)
        main_btn_frame.pack(anchor=W, pady=(0, 5), fill=X)

        main_btn = ttkb.Menubutton(main_btn_frame, text="主体模板", bootstyle="success")
        main_menu = Menu(main_btn, tearoff=0)
        main_btn["menu"] = main_menu
        self.main_menu = main_menu
        main_btn.pack(side=LEFT, padx=(0, 10))

        # 新增【解析md】按钮
        parse_md_btn = ttkb.Button(
            main_btn_frame,
            text="解析md",
            command=self.parse_main_prompt_from_md,
            bootstyle="primary-outline",
            width=10
        )
        parse_md_btn.pack(side=LEFT)

        self.main_prompt = tk.Text(main_labelframe, wrap=WORD, font=("Arial", 11), height=10)
        self.main_prompt.pack(fill=BOTH, expand=True)

        # 基础配置框架
        cfg_frame = ttkb.Labelframe(self.create_tab, text="基础配置", padding=15)
        cfg_frame.pack(fill=X, padx=10, pady=(0, 10))

        left = ttkb.Frame(cfg_frame)
        left.pack(side=LEFT, fill=X, expand=True)

        # API Key
        ttkb.Label(left, text="API Key：").pack(anchor=W)
        f_key = ttkb.Frame(left)
        f_key.pack(fill=X, pady=5)
        ttkb.Entry(f_key, textvariable=self.api_key, show="*", width=50).pack(side=LEFT, fill=X, expand=True)
        ttkb.Button(f_key, text="保存Key", command=self.save_api_key_manual, bootstyle="outline").pack(side=LEFT)

        # API 接口
        ttkb.Label(left, text="API 接口：").pack(anchor=W, pady=(10, 0))
        f_host = ttkb.Frame(left)
        f_host.pack(fill=X, pady=5)
        self.api_combo = ttkb.Combobox(f_host, textvariable=self.api_host, state="normal", width=60)
        self.api_combo.pack(fill=X)
        self.api_combo['values'] = self.config.get("api_hosts", DEFAULT_API_HOSTS)
        self.api_host.trace("w", self._on_api_host_change)

        # 右侧配置
        right = ttkb.Frame(cfg_frame)
        right.pack(side=RIGHT, padx=20)

        param_frame = ttkb.Frame(right)
        param_frame.pack(fill=X, pady=(0, 10))

        # 视频参数
        ttkb.Label(param_frame, text="视频比例：").pack(side=LEFT)
        ttkb.Combobox(param_frame, textvariable=self.aspect_ratio, values=["16:9", "9:16"], state="readonly",
                      width=8).pack(side=LEFT, padx=5)
        ttkb.Label(param_frame, text="  时长(秒)：").pack(side=LEFT)
        ttkb.Combobox(param_frame, textvariable=self.duration, values=["15", "10"], state="readonly", width=8).pack(
            side=LEFT, padx=5)
        ttkb.Label(param_frame, text="  清晰度：").pack(side=LEFT)
        ttkb.Combobox(param_frame, textvariable=self.size, values=["small", "large"], state="readonly", width=8).pack(
            side=LEFT, padx=5)

        # 参考图
        ttkb.Label(right, text="参考图：").pack(anchor=W)
        f_ref = ttkb.Frame(right)
        f_ref.pack(fill=X, pady=5)

        # 输入框占大部分空间
        ttkb.Entry(f_ref, textvariable=self.ref_image_path, width=35).pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        # 选择图片按钮
        ttkb.Button(
            f_ref,
            text="选择图片",
            command=self.select_reference_image,
            bootstyle="info",
            width=10
        ).pack(side=LEFT, padx=(0, 4))

        # 新增：小型清空按钮（灰色、紧凑）
        ttkb.Button(
            f_ref,
            text="×",
            command=lambda: self.ref_image_path.set(""),
            bootstyle="secondary-outline",
            width=2,  # 非常窄
            padding=(4, 0)  # 缩小内边距
        ).pack(side=LEFT)

        # 下载路径
        ttkb.Label(right, text="下载路径：").pack(anchor=W, pady=(10, 0))
        f_dl = ttkb.Frame(right)
        f_dl.pack(fill=X, pady=5)
        ttkb.Entry(f_dl, textvariable=self.download_dir, width=35).pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        ttkb.Button(f_dl, text="选择文件夹", command=self.select_download_dir, bootstyle="secondary").pack(side=LEFT)

        # 操作按钮
        btns = ttkb.Frame(self.create_tab)
        btns.pack(fill=X, pady=(20, 30), padx=20)
        ttkb.Checkbutton(btns, text="添加后自动提交", variable=self.auto_submit, bootstyle="round-toggle").pack(
            side=LEFT, padx=30)
        ttkb.Checkbutton(btns, text="成功后自动下载", variable=self.auto_download_video, bootstyle="round-toggle").pack(
            side=LEFT, padx=30)
        ttkb.Button(btns, text="🗑️ 清空输入", command=self.clear_input, bootstyle="danger-outline").pack(side=RIGHT,
                                                                                                         padx=20)
        ttkb.Button(btns, text="✅ 添加任务", command=self.add_single_task, bootstyle="success").pack(side=RIGHT,
                                                                                                     padx=20)

    def parse_main_prompt_from_md(self):
        """解析主体提示词中的Markdown内容为纯文本（基于markdown+bs4）"""
        # 获取主体提示词的原始内容
        original_text = self.main_prompt.get("1.0", tk.END)
        if not original_text.strip():
            messagebox.showinfo("提示", "主体提示词为空，无需解析")
            return

        # 调用基于markdown-it-py + mdit_plain的解析函数
        parsed_text = parse_markdown_text_to_plain(original_text)

        # 替换主体提示词内容
        self.main_prompt.delete("1.0", tk.END)
        self.main_prompt.insert("1.0", parsed_text)

        # 日志记录
        self.log(
            f"📝 已将主体提示词的Markdown内容解析为纯文本，原长度：{len(original_text)}，解析后长度：{len(parsed_text)}")
        messagebox.showinfo("成功", "Markdown格式解析完成，已替换为纯文本！")

    def _build_manage_tab(self):
        # 顶部操作按钮
        top = ttkb.Frame(self.manage_tab)
        top.pack(fill=X, pady=10, padx=10)
        ttkb.Button(top, text="🔄 手动刷新状态", command=self.manual_refresh_all_tasks, bootstyle="primary",
                    width=20).pack(side=LEFT, padx=10)
        ttkb.Button(top, text="🚀 提交所有待处理", command=self.submit_all_pending_tasks, bootstyle="success",
                    width=20).pack(side=LEFT, padx=10)
        ttkb.Button(top, text="🗑️ 清空已完成", command=self.clear_finished_tasks, bootstyle="danger", width=20).pack(
            side=LEFT, padx=10)

        # 任务列表
        tree_frame = ttkb.Labelframe(self.manage_tab, text="任务列表", padding=10)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # 列配置：新增API ID，缩小复用/详情/操作列
        columns = ("id", "prefix", "main", "suffix", "ref", "status", "progress", "api_id", "reuse", "detail", "action")
        self.tree = ttkb.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")
        col_cfg = {
            "id": (100, CENTER, "任务ID"),
            "prefix": (200, W, "前缀"),
            "main": (380, W, "主体"),
            "suffix": (200, W, "后缀"),
            "ref": (150, W, "参考图"),
            "status": (120, CENTER, "状态"),
            "progress": (100, CENTER, "进度"),
            "api_id": (150, W, "API ID"),
            "reuse": (60, CENTER, "复用"),
            "detail": (60, CENTER, "详情"),
            "action": (60, CENTER, "操作")
        }
        for c, (w, a, t) in col_cfg.items():
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=a)

        # 纵向滚动条
        scroll = ttkb.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scroll.pack(side=RIGHT, fill=Y)

        # 标签样式
        self.tree.tag_configure("pending", background="#ffffff")
        self.tree.tag_configure("running", background="#fffacd")
        self.tree.tag_configure("succeeded", background="#d4edda")
        self.tree.tag_configure("failed", background="#f8d7da")

        # 日志框（创建log_text组件）
        log_frame = ttkb.Labelframe(self.manage_tab, text="运行日志", padding=10)
        log_frame.pack(fill=BOTH, expand=True, padx=10)
        self.log_text = tk.Text(log_frame, height=8, state=DISABLED, wrap=WORD)
        log_scroll = ttkb.Scrollbar(log_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)
        log_scroll.pack(side=RIGHT, fill=Y)

    def _bind_events(self):
        self.tree.bind("<Button-1>", self._on_tree_click)

    def _refresh_all_menus(self):
        # 刷新前缀模板
        self.prefix_menu.delete(0, tk.END)
        for name, txt in self.prefix_templates.items():
            self.prefix_menu.add_command(
                label=name,
                command=lambda t=txt: (
                    self.prefix_prompt.delete("1.0", tk.END),
                    self.prefix_prompt.insert("1.0", t)
                )[1]
            )
        # 前缀历史记录
        if self.prefix_history:
            self.prefix_menu.add_separator()
            self.prefix_menu.add_command(label="📜 最近使用（前缀）", state="disabled")
            for text in self.prefix_history[:MAX_HISTORY_COUNT]:
                disp = text[:30] + "..." if len(text) > 30 else text
                self.prefix_menu.add_command(
                    label=disp,
                    command=lambda h=text: (
                        self.prefix_prompt.delete("1.0", tk.END),
                        self.prefix_prompt.insert("1.0", h)
                    )[1]
                )

        # 刷新主体模板
        self.main_menu.delete(0, tk.END)
        for name, txt in self.main_templates.items():
            self.main_menu.add_command(
                label=name,
                command=lambda t=txt: (
                    self.main_prompt.delete("1.0", tk.END),
                    self.main_prompt.insert("1.0", t)
                )[1]
            )

        # 刷新后缀模板
        self.suffix_menu.delete(0, tk.END)
        for name, txt in self.suffix_templates.items():
            self.suffix_menu.add_command(
                label=name,
                command=lambda t=txt: (
                    self.suffix_prompt.delete("1.0", tk.END),
                    self.suffix_prompt.insert("1.0", t)
                )[1]
            )
        # 后缀历史记录
        if self.suffix_history:
            self.suffix_menu.add_separator()
            self.suffix_menu.add_command(label="📜 最近使用（后缀）", state="disabled")
            for text in self.suffix_history[:MAX_HISTORY_COUNT]:
                disp = text[:30] + "..." if len(text) > 30 else text
                self.suffix_menu.add_command(
                    label=disp,
                    command=lambda h=text: (
                        self.suffix_prompt.delete("1.0", tk.END),
                        self.suffix_prompt.insert("1.0", h)
                    )[1]
                )

    def log(self, msg):
        """日志记录与显示（兼容log_text未初始化的场景）"""
        # 第一步：先打印到控制台（确保日志不丢失）
        log_msg = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(log_msg)

        # 第二步：仅当log_text有效时，写入UI日志框
        if hasattr(self, 'log_text') and self.log_text is not None:
            try:
                self.log_text.config(state=NORMAL)
                self.log_text.insert(tk.END, f"{log_msg}\n")
                self.log_text.see(tk.END)
                self.log_text.config(state=tk.DISABLED)
            except Exception as e:
                # 捕获UI操作异常，不影响程序运行
                print(f"[日志UI写入失败] {str(e)}")

    def _on_api_host_change(self, *args):
        """API接口变更处理"""
        cur = self.api_host.get().strip()
        if not cur:
            return
        hosts = list(self.api_combo['values'])
        if cur not in hosts:
            hosts.insert(0, cur)
            hosts = hosts[:10]
            self.api_combo['values'] = hosts
            self.config["api_hosts"] = hosts
        self.config["api_host"] = cur
        save_config(self.config)
        self.log(f"🌐 API接口已切换为：{cur}")

    def save_api_key_manual(self):
        """保存API Key"""
        if save_api_key(self.api_key.get()):
            self.log("✅ API Key保存成功")
            messagebox.showinfo("成功", "API Key已保存到api.txt")

    def select_reference_image(self):
        """选择参考图"""
        p = filedialog.askopenfilename(filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp")])
        if p:
            self.ref_image_path.set(p)
            self.log(f"📷 已选择参考图：{os.path.basename(p)}")

    def select_download_dir(self):
        """选择下载目录"""
        p = filedialog.askdirectory(initialdir=self.download_dir.get())
        if p:
            self.download_dir.set(p)
            os.makedirs(p, exist_ok=True)
            self.config["download_dir"] = p
            save_config(self.config)
            self.log(f"📁 下载路径已设置为：{p}")

    def clear_input(self):
        """清空输入框"""
        self.prefix_prompt.delete("1.0", tk.END)
        self.main_prompt.delete("1.0", tk.END)
        self.suffix_prompt.delete("1.0", tk.END)
        self.ref_image_path.set("")
        self.log("🗑️ 已清空所有输入内容")

    def add_single_task(self):
        """添加单个任务"""
        prefix = self.prefix_prompt.get("1.0", tk.END).strip()
        main = self.main_prompt.get("1.0", tk.END).strip()
        suffix = self.suffix_prompt.get("1.0", tk.END).strip()

        if not main:
            messagebox.showwarning("警告", "主体提示词不能为空！")
            return

        # 构建完整提示词
        full_prompt = f"{prefix} {main} {suffix}".strip()

        # 更新历史记录
        for text, hist in [(prefix, self.prefix_history), (suffix, self.suffix_history)]:
            if text and text not in hist:
                hist.insert(0, text)
                if len(hist) > MAX_HISTORY_COUNT:
                    hist.pop()

        # 保存配置
        self.config["prefix_history"] = self.prefix_history
        self.config["suffix_history"] = self.suffix_history
        save_config(self.config)
        self._refresh_all_menus()

        # 创建任务
        task = SoraTask(
            prefix_prompt=prefix,
            main_prompt=main,
            suffix_prompt=suffix,
            full_prompt=full_prompt,
            ref_image_path=self.ref_image_path.get(),
            ref_image_base64=image_to_base64(self.ref_image_path.get()),
            aspect_ratio=self.aspect_ratio.get(),
            duration=int(self.duration.get()),
            size=self.size.get()
        )

        self.tasks.append(task)
        self._update_task_tree()
        self.log(f"✅ 任务添加成功 | 任务ID：{task.task_id[:8]}")

        # 自动提交
        if self.auto_submit.get():
            threading.Thread(target=self.submit_task, args=(task,), daemon=True).start()

        self.clear_input()

    def _update_task_tree(self):
        """更新任务列表"""
        for i in self.tree.get_children():
            self.tree.delete(i)

        icons = {"pending": "⚪", "running": "🔵", "succeeded": "🟢", "failed": "🔴"}
        for task in self.tasks:
            action = "重试" if task.status == "failed" else "下载" if task.status == "succeeded" and task.video_url else "-"
            self.tree.insert("", "end", values=(
                task.task_id[:8],
                task.prefix_prompt[:35] + "..." if len(task.prefix_prompt) > 35 else task.prefix_prompt,
                task.main_prompt[:60] + "..." if len(task.main_prompt) > 60 else task.main_prompt,
                task.suffix_prompt[:35] + "..." if len(task.suffix_prompt) > 35 else task.suffix_prompt,
                os.path.basename(task.ref_image_path) or "无",
                f"{icons.get(task.status, '⚪')} {task.status}",
                f"{task.progress}%",
                task.api_task_id or "无",
                "复用",
                "详情",
                action
            ), tags=(task.status,))

    def _on_tree_click(self, event):
        """任务列表点击事件"""
        col = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        if not item:
            return

        col_idx = int(col[1:]) - 1
        col_name = self.tree["columns"][col_idx]
        task_short_id = self.tree.item(item, "values")[0]
        task = next((t for t in self.tasks if t.task_id.startswith(task_short_id)), None)

        if not task:
            return

        # 处理不同列点击
        if col_name == "reuse":
            self._reuse_task(task)
        elif col_name == "api_id":
            self._copy_api_id(task)
        elif col_name == "detail":
            self._show_task_detail(task)
        elif col_name == "action":
            self._handle_task_action(task)

    def _reuse_task(self, task):
        """复用任务"""
        self.notebook.select(self.create_tab)
        self.prefix_prompt.delete("1.0", tk.END)
        self.prefix_prompt.insert("1.0", task.prefix_prompt)
        self.main_prompt.delete("1.0", tk.END)
        self.main_prompt.insert("1.0", task.main_prompt)
        self.suffix_prompt.delete("1.0", tk.END)
        self.suffix_prompt.insert("1.0", task.suffix_prompt)
        self.ref_image_path.set(task.ref_image_path)
        self.aspect_ratio.set(task.aspect_ratio)
        self.duration.set(str(task.duration))
        self.size.set(task.size)
        self.log(f"🔧 已复用任务 | 任务ID：{task.task_id[:8]}")

    def _copy_api_id(self, task):
        """复制API ID"""
        if not task.api_task_id:
            messagebox.showwarning("提示", "该任务暂无有效API ID")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(task.api_task_id)
        self.root.update()
        messagebox.showinfo("复制成功", f"API ID已复制到剪贴板：\n{task.api_task_id}")
        self.log(f"📋 已复制API ID | 任务ID：{task.task_id[:8]}")

    def _show_task_detail(self, task):
        """显示任务详情"""
        detail_window = ttkb.Toplevel(self.root)
        detail_window.title(f"任务详情 - {task.task_id[:8]}")
        detail_window.geometry("1200x800")
        detail_window.resizable(True, True)
        detail_window.transient(self.root)
        detail_window.grab_set()

        # 尝试给详情窗口也加载logo（兼容打包/开发环境）
        if os.path.exists(ICON_FILE):
            try:
                detail_window.iconbitmap(ICON_FILE)
            except:
                pass

        # 标签页
        notebook = ttkb.Notebook(detail_window)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # 请求参数页
        req_frame = ttkb.Frame(notebook)
        notebook.add(req_frame, text="📤 请求参数")
        req_text = tk.Text(req_frame, wrap=tk.WORD, font=("Consolas", 10))
        req_scroll = ttkb.Scrollbar(req_frame, orient=VERTICAL, command=req_text.yview)
        req_text.configure(yscrollcommand=req_scroll.set)
        req_text.pack(side=LEFT, fill=BOTH, expand=True)
        req_scroll.pack(side=RIGHT, fill=Y)

        # 响应结果页
        resp_frame = ttkb.Frame(notebook)
        notebook.add(resp_frame, text="📥 响应结果")
        resp_text = tk.Text(resp_frame, wrap=tk.WORD, font=("Consolas", 10))
        resp_scroll = ttkb.Scrollbar(resp_frame, orient=VERTICAL, command=resp_text.yview)
        resp_text.configure(yscrollcommand=resp_scroll.set)
        resp_text.pack(side=LEFT, fill=BOTH, expand=True)
        resp_scroll.pack(side=RIGHT, fill=Y)

        # 填充内容
        req_content = "暂无请求数据"
        if task.request_json:
            try:
                req_data = json.loads(task.request_json)
                req_data_short = shorten_base64_in_data(req_data)
                req_content = json.dumps(req_data_short, ensure_ascii=False, indent=2)
            except:
                req_content = task.request_json

        resp_content = "暂无响应数据"
        if task.response_json:
            try:
                resp_data = json.loads(task.response_json)
                resp_data_short = shorten_base64_in_data(resp_data)
                resp_content = json.dumps(resp_data_short, ensure_ascii=False, indent=2)
            except:
                resp_content = task.response_json

        req_text.insert(tk.END, req_content)
        resp_text.insert(tk.END, resp_content)
        req_text.config(state=tk.DISABLED)
        resp_text.config(state=tk.DISABLED)

        # 关闭按钮
        btn_frame = ttkb.Frame(detail_window)
        btn_frame.pack(fill=X, padx=10, pady=10)
        ttkb.Button(btn_frame, text="关闭窗口", command=detail_window.destroy, bootstyle="primary").pack(side=RIGHT)

    def _handle_task_action(self, task):
        """处理任务操作（重试/下载）"""
        if task.status == "failed":
            # 重试任务
            new_task = SoraTask(
                prefix_prompt=task.prefix_prompt,
                main_prompt=task.main_prompt,
                suffix_prompt=task.suffix_prompt,
                full_prompt=task.full_prompt,
                ref_image_path=task.ref_image_path,
                ref_image_base64=task.ref_image_base64,
                aspect_ratio=task.aspect_ratio,
                duration=task.duration,
                size=task.size
            )
            self.tasks.append(new_task)
            self._update_task_tree()
            self.log(f"🔄 已创建重试任务 | 原任务ID：{task.task_id[:8]} | 新任务ID：{new_task.task_id[:8]}")
            threading.Thread(target=self.submit_task, args=(new_task,), daemon=True).start()
        elif task.status == "succeeded" and task.video_url:
            # 手动下载（仅以任务ID命名）
            save_path = filedialog.asksaveasfilename(
                defaultextension=".mp4",
                initialfile=f"{task.task_id}.mp4"
            )
            if save_path:
                self.log(f"📥 开始手动下载 | 任务ID：{task.task_id[:8]}")
                threading.Thread(target=self._download_video, args=(task.video_url, save_path, task, False),
                                 daemon=True).start()

    def submit_task(self, task):
        """提交任务"""
        host = self.api_host.get().strip()
        api_key = self.api_key.get().strip()

        if not host:
            task.status = "failed"
            task.error = "API接口为空"
            self.root.after(0, self._update_task_tree)
            self.log(f"❌ 任务提交失败 | 任务ID：{task.task_id[:8]} | 原因：API接口为空")
            return

        if not api_key:
            task.status = "failed"
            task.error = "API Key为空"
            self.root.after(0, self._update_task_tree)
            self.log(f"❌ 任务提交失败 | 任务ID：{task.task_id[:8]} | 原因：API Key为空")
            return

        # 更新任务状态
        task.status = "running"
        self.root.after(0, self._update_task_tree)
        self.log(f"🚀 开始提交任务 | 任务ID：{task.task_id[:8]}")

        # 构建请求参数
        params = {
            "model": "sora-2",
            "prompt": task.full_prompt,
            "url": task.ref_image_base64,
            "aspectRatio": task.aspect_ratio,
            "duration": task.duration,
            "size": task.size,
            "webHook": "-1",
            "shutProgress": False
        }

        # 处理Base64并保存请求参数
        try:
            params_short = shorten_base64_in_data(params.copy())
            task.request_json = json.dumps(params_short, ensure_ascii=False, indent=2)
        except:
            task.request_json = f"请求参数：{str(params)}"

        # 发送请求
        try:
            r = requests.post(
                f"{host.rstrip('/')}/v1/video/sora-video",
                json=params,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60,
                verify=False
            )
            r.raise_for_status()
            data = r.json()

            # 处理响应数据
            data_short = shorten_base64_in_data(data.copy())
            task.response_json = json.dumps(data_short, ensure_ascii=False, indent=2)

            if data.get("code") == 0 and data.get("data", {}).get("id"):
                task.api_task_id = data["data"]["id"]
                self.log(f"✅ 任务提交成功 | 任务ID：{task.task_id[:8]} | API ID：{task.api_task_id[:8]}")
            else:
                raise Exception(data.get("message", "未知错误"))
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.response_json = f"请求失败：{str(e)}"
            self.log(f"❌ 任务提交失败 | 任务ID：{task.task_id[:8]} | 原因：{str(e)}")

        self.root.after(0, self._update_task_tree)

    def query_task(self, task):
        """查询任务状态"""
        if not task.api_task_id:
            return

        host = self.api_host.get().strip()
        api_key = self.api_key.get().strip()

        try:
            r = requests.post(
                f"{host.rstrip('/')}/v1/draw/result",
                json={"id": task.api_task_id},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
                verify=False
            )
            r.raise_for_status()
            result = r.json()

            # 处理响应数据
            result_short = shorten_base64_in_data(result.copy())
            task.response_json = json.dumps(result_short, ensure_ascii=False, indent=2)

            if result.get("code") != 0:
                raise Exception(result.get("message", "查询失败"))

            data = result["data"]
            task.progress = data.get("progress", task.progress)
            old_status = task.status
            task.status = data.get("status", task.status)

            # 任务成功，获取视频链接并自动下载（仅以任务ID命名）
            if task.status == "succeeded" and data.get("results"):
                task.video_url = data["results"][0].get("url", "")
                if self.auto_download_video.get() and not task.download_path:
                    save_path = os.path.join(self.download_dir.get(), f"{task.task_id}.mp4")
                    threading.Thread(target=self._download_video, args=(task.video_url, save_path, task, True),
                                     daemon=True).start()

            if task.status != old_status:
                self.log(f"📊 任务状态更新 | 任务ID：{task.task_id[:8]} | 旧状态：{old_status} | 新状态：{task.status}")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.response_json = f"查询失败：{str(e)}"
            self.log(f"❌ 任务查询失败 | 任务ID：{task.task_id[:8]} | 原因：{str(e)}")

        self.root.after(0, self._update_task_tree)

    def _download_video(self, url, save_path, task, auto):
        """下载视频（仅以任务ID命名，避免特殊字符）"""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(
                url,
                stream=True,
                headers=headers,
                timeout=VIDEO_DOWNLOAD_TIMEOUT,
                verify=False
            )
            r.raise_for_status()

            # 保存视频
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            total_size = 0
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)

            # 验证文件大小
            if total_size < MIN_VALID_VIDEO_SIZE:
                raise Exception(f"文件过小（{total_size} 字节），可能无效")

            # 更新任务信息
            task.download_path = save_path
            task.download_failed = False
            self.log(f"✅ 视频下载完成 | 任务ID：{task.task_id[:8]} | 保存路径：{save_path}")

            if not auto:
                messagebox.showinfo("下载成功", f"视频已保存到：\n{save_path}")
        except Exception as e:
            task.download_failed = True
            self.log(f"❌ 视频下载失败 | 任务ID：{task.task_id[:8]} | 原因：{str(e)}")
            if not auto:
                messagebox.showerror("下载失败", str(e))

    def manual_refresh_all_tasks(self):
        """手动刷新所有任务"""
        refreshed_count = 0
        for task in self.tasks:
            if task.api_task_id and task.status in ("running", "pending"):
                refreshed_count += 1
                threading.Thread(target=self.query_task, args=(task,), daemon=True).start()
                time.sleep(0.2)

        if refreshed_count == 0:
            self.log("ℹ️ 暂无需要刷新的任务")
        else:
            self.log(f"🔄 已启动 {refreshed_count} 个任务的刷新流程")

    def submit_all_pending_tasks(self):
        """提交所有待处理任务"""
        pending_tasks = [t for t in self.tasks if t.status == "pending"]
        if not pending_tasks:
            messagebox.showinfo("提示", "暂无待处理任务")
            self.log("ℹ️ 暂无待处理任务")
            return

        self.log(f"🚀 开始批量提交 {len(pending_tasks)} 个任务")
        for task in pending_tasks:
            threading.Thread(target=self.submit_task, args=(task,), daemon=True).start()
            time.sleep(0.3)

    def clear_finished_tasks(self):
        """清空已完成任务"""
        finished_tasks = [t for t in self.tasks if t.status in ("succeeded", "failed")]
        if not finished_tasks:
            messagebox.showinfo("提示", "暂无已完成任务")
            self.log("ℹ️ 暂无已完成任务")
            return

        if not messagebox.askyesno("确认", f"是否删除 {len(finished_tasks)} 个已完成任务？"):
            return

        self.tasks = [t for t in self.tasks if t.status not in ("succeeded", "failed")]
        self._update_task_tree()
        save_tasks(self.tasks)
        self.log(f"🗑️ 已清空 {len(finished_tasks)} 个已完成任务")

    def _start_monitor(self):
        """启动任务监控"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.log("🔍 任务监控已启动")

        def monitor_loop():
            while self.is_monitoring:
                # 查询运行中的任务
                for task in self.tasks:
                    if task.status == "running":
                        self.query_task(task)
                        time.sleep(0.5)
                # 保存任务
                save_tasks(self.tasks)
                time.sleep(5)

        threading.Thread(target=monitor_loop, daemon=True).start()

    def stop_monitor(self):
        """停止任务监控"""
        self.is_monitoring = False
        save_tasks(self.tasks)
        self.log("🛑 任务监控已停止")


# ==================== 程序入口 ====================
if __name__ == "__main__":
    # 检查依赖
    missing_deps = []
    required_deps = [
        ("requests", "requests"),
        ("ttkbootstrap", "ttkbootstrap"),
        ("urllib3", "urllib3")
    ]

    for dep_name, import_name in required_deps:
        try:
            __import__(import_name)
        except ImportError:
            missing_deps.append(dep_name)

    if missing_deps:
        messagebox.showerror(
            "依赖缺失",
            f"缺少以下依赖库，请先安装：\n{', '.join(missing_deps)}\n\n安装命令：pip install {' '.join(missing_deps)}"
        )
        exit(1)

    # 启动程序
    root = ttkb.Window(themename="cosmo")
    # 双重保障：入口处也设置最大化
    root.state('zoomed')
    app = SoraVideoGenerator(root)
    root.protocol("WM_DELETE_WINDOW", lambda: app.stop_monitor() or root.destroy())
    root.mainloop()
