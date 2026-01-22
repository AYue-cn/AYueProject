import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import base64
import json
import time
import threading
import os
from datetime import datetime
import cv2
import numpy as np
import subprocess
from PIL import Image
import hashlib
from typing import List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- 配置 ----------------
CONFIG_FILE = "config.json"
STORAGE_FILE = "sora_characters.json"
TEMP_VIDEO_PATH = "temp_static_video.mp4"

# 默认配置（首次运行时使用）
DEFAULT_CONFIG = {
    "api_key": "",
    "host": "https://grsai.dakka.com.cn"
}

UPLOAD_ENDPOINT = "/v1/video/sora-upload-character"
RESULT_ENDPOINT = "/v1/draw/result"          # ← poll_for_result 里也在用这个

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # 补全缺失字段
                for k, v in DEFAULT_CONFIG.items():
                    if k not in config:
                        config[k] = v
                return config
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存配置失败: {e}")


class ViewCharactersWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("已保存的角色列表")
        self.geometry("1200x650")
        self.transient(parent)
        self.grab_set()

        self.parent = parent
        self.create_widgets()
        self.load_and_display()

    def create_widgets(self):
        ctk.CTkLabel(self, text="已保存角色", font=("Segoe UI", 18, "bold")).pack(pady=(20, 10))

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(padx=20, pady=10, fill="both", expand=True)

        header_frame = ctk.CTkFrame(self.scroll_frame)
        header_frame.pack(fill="x", pady=(0, 8))

        headers = ["缩略图", "时间", "原文件名", "Character ID", "操作"]
        widths = [100, 160, 260, 280, 80]
        for i, (text, w) in enumerate(zip(headers, widths)):
            lbl = ctk.CTkLabel(header_frame, text=text, font=("Segoe UI", 13, "bold"),
                               width=w, anchor="center" if i == 0 else "w")
            lbl.grid(row=0, column=i, padx=8, sticky="ew")

        ctk.CTkFrame(self.scroll_frame, height=2, fg_color="gray").pack(fill="x", pady=4)

    def load_and_display(self):
        characters = self.parent.characters

        if not characters:
            ctk.CTkLabel(self.scroll_frame, text="暂无保存的角色", text_color="gray").pack(pady=40)
            return

        for item in characters:
            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=8, padx=5)

            values = [
                item.get("thumbnail"),
                item.get("timestamp", "—"),
                item.get("original_filename", "未知文件"),
                item.get("character_id", "—")
            ]

            # 缩略图
            thumb_label = ctk.CTkLabel(row_frame, text="无", width=100, height=80)
            thumb_label.grid(row=0, column=0, padx=8, pady=4, sticky="n")
            thumb_path = values[0]
            if thumb_path and os.path.exists(thumb_path):
                try:
                    pil_img = Image.open(thumb_path)
                    pil_img.thumbnail((100, 80))

                    ctk_img = ctk.CTkImage(
                        light_image=pil_img,
                        size=(100, 80)
                    )

                    thumb_label.configure(image=ctk_img, text="")
                    thumb_label.image = ctk_img
                except:
                    thumb_label.configure(text="加载失败")

            # 其他列
            for i, val in enumerate(values[1:], start=1):
                lbl = ctk.CTkLabel(row_frame, text=val, font=("Consolas", 12),
                                   width=[160, 260, 280][i - 1], anchor="w", wraplength=250)
                lbl.grid(row=0, column=i, padx=8, pady=4, sticky="w")

            # 复制按钮
            copy_btn = ctk.CTkButton(
                row_frame, text="复制 @ID", width=80, height=28,
                command=lambda cid=item.get("character_id", ""): self.copy_to_clipboard(cid)
            )
            copy_btn.grid(row=0, column=4, padx=8, pady=4, sticky="e")

    def copy_to_clipboard(self, character_id):
        if not character_id:
            return
        format_text = f"@{character_id} "
        self.clipboard_clear()
        self.clipboard_append(format_text)
        messagebox.showinfo("已复制", f"已复制到剪贴板：\n{format_text}")


class SoraCharacterUploader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("阿岳Sora2角色上传工具v1.0")
        self.geometry("900x750")
        self.resizable(False, False)

        self.cache_dir = "cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        # 加载配置
        self.config = load_config()
        self.api_key = self.config.get("api_key", "")
        self.host = self.config.get("host", DEFAULT_CONFIG["host"])

        self.file_path = ""
        self.task_running = False
        self.characters = self.load_characters()

        self.create_widgets()

        # 如果 API Key 为空，提示设置
        if not self.api_key:
            self.log("请在下方输入 API Key 并保存配置", error=True)
        else:
            self.log("程序启动完成。支持 .mp4 / .jpg / .png / .jpeg")

    def load_characters(self):
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"读取角色文件失败: {e}", error=True)
                return []
        return []

    def save_characters(self):
        try:
            with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.characters, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存角色文件失败: {e}", error=True)

    def get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def create_widgets(self):
        # ==================== 配置区域 ====================
        config_frame = ctk.CTkFrame(self)
        config_frame.pack(padx=20, pady=(15, 5), fill="x")

        ctk.CTkLabel(config_frame, text="API Key:", font=("Segoe UI", 14)).pack(side="left", padx=(10, 5))

        self.api_key_entry = ctk.CTkEntry(config_frame, width=380, show="*")
        self.api_key_entry.insert(0, self.api_key)
        self.api_key_entry.pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkButton(config_frame, text="保存配置", width=120,
                      command=self.save_api_config).pack(side="right", padx=10)

        # Host（可选修改）
        host_frame = ctk.CTkFrame(self)
        host_frame.pack(padx=20, pady=(0, 10), fill="x")

        ctk.CTkLabel(host_frame, text="API Host:", font=("Segoe UI", 14)).pack(side="left", padx=(10, 5))
        self.host_entry = ctk.CTkEntry(host_frame, width=380)
        self.host_entry.insert(0, self.host)
        self.host_entry.pack(side="left", padx=5, fill="x", expand=True)

        # ==================== 文件选择 & 时间范围 ====================
        file_frame = ctk.CTkFrame(self)
        file_frame.pack(padx=20, pady=10, fill="x")

        ctk.CTkLabel(file_frame, text="选择文件（视频或图片）：", font=("Segoe UI", 14)).pack(side="left", padx=10)
        self.file_label = ctk.CTkLabel(file_frame, text="未选择文件", text_color="gray")
        self.file_label.pack(side="left", padx=10, fill="x", expand=True)

        ctk.CTkButton(file_frame, text="浏览...", width=100, command=self.select_file).pack(side="right", padx=10)

        time_frame = ctk.CTkFrame(self)
        time_frame.pack(padx=20, pady=10, fill="x")

        ctk.CTkLabel(time_frame, text="截取时间范围（秒）：", font=("Segoe UI", 14)).pack(side="left", padx=(10, 5))
        self.timestamps_entry = ctk.CTkEntry(time_frame, placeholder_text="例如: 0,3", width=180)
        self.timestamps_entry.insert(0, "0,3")
        self.timestamps_entry.pack(side="left", padx=5)

        ctk.CTkLabel(time_frame, text="(最多3秒，图片自动转为4秒30fps+空白音轨)", text_color="gray").pack(side="left", padx=5)

        # ==================== 操作按钮 ====================
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(padx=20, pady=15, fill="x")

        self.upload_btn = ctk.CTkButton(
            btn_frame, text="开始上传并提取角色", width=220, height=40,
            font=("Segoe UI", 15, "bold"), command=self.start_upload_thread
        )
        self.upload_btn.pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame, text="查看已保存角色", width=220, height=40,
            command=self.open_view_window
        ).pack(side="left", padx=10)

        # ==================== 日志区域 ====================
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(padx=20, pady=(10, 20), fill="both", expand=True)

        self.log_text = ctk.CTkTextbox(log_frame, wrap="word", state="disabled", font=("Consolas", 13))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.status_label = ctk.CTkLabel(self, text="就绪", text_color="gray")
        self.status_label.pack(pady=(0, 10))

    def save_api_config(self):
        new_key = self.api_key_entry.get().strip()
        new_host = self.host_entry.get().strip()

        if not new_key:
            messagebox.showwarning("提示", "API Key 不能为空")
            return

        if not new_host:
            new_host = DEFAULT_CONFIG["host"]

        self.api_key = new_key
        self.host = new_host
        self.config["api_key"] = new_key
        self.config["host"] = new_host
        save_config(self.config)

        self.log("API 配置已保存", error=False)
        messagebox.showinfo("成功", "API Key 和 Host 已更新")

    def log(self, message, error=False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_tag = "error" if error else "success" if any(word in message for word in ["成功", "完成", "已生成", "保存"]) else "info"
        line = f"[{timestamp}] {message}\n"

        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.tag_add(color_tag, "end-1l", "end")
        self.log_text.tag_config("error", foreground="salmon")
        self.log_text.tag_config("success", foreground="#00ff9d")
        self.log_text.tag_config("info", foreground="white")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def select_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("支持的文件", "*.mp4 *.jpg *.jpeg *.png")]
        )
        if path:
            self.file_path = path
            filename = os.path.basename(path)
            ext = os.path.splitext(filename)[1].lower()
            color = "lightgreen" if ext in [".mp4"] else "#ffcc00"
            self.file_label.configure(text=filename, text_color=color)
            self.log(f"已选择：{filename} ({'视频' if ext in ['.mp4'] else '图片'})")

    def start_upload_thread(self):
        if not self.api_key:
            messagebox.showerror("错误", "请先设置 API Key 并保存配置")
            return

        if self.task_running:
            messagebox.showwarning("提示", "已有任务正在进行，请等待完成")
            return

        if not self.file_path:
            messagebox.showerror("错误", "请先选择文件")
            return

        timestamps = self.timestamps_entry.get().strip()
        if not timestamps or "," not in timestamps:
            messagebox.showerror("错误", "请输入正确的时间范围格式，例如：0,3")
            return

        self.task_running = True
        self.upload_btn.configure(state="disabled", text="处理中...")
        self.status_label.configure(text="任务进行中...", text_color="yellow")

        threading.Thread(
            target=self.process_and_upload,
            args=(self.file_path, timestamps),
            daemon=True
        ).start()

    def process_and_upload(self, input_path, timestamps):
        original_filename = os.path.basename(input_path)

        try:
            ext = os.path.splitext(input_path)[1].lower().lstrip(".")

            upload_file_path = input_path

            if ext in ["jpg", "jpeg", "png"]:
                self.log("检测到图片，正在转换为4秒30fps视频 + 空白音轨...")
                success = self.image_to_static_video(input_path, TEMP_VIDEO_PATH)
                if not success:
                    raise Exception("图片转视频失败")
                upload_file_path = TEMP_VIDEO_PATH
                self.log(f"转换完成：{TEMP_VIDEO_PATH}")

            self.log("正在读取并编码文件...")
            base64_data = self.file_to_base64(upload_file_path)

            payload = {
                "url": base64_data,
                "timestamps": timestamps,
                "webHook": "-1",
                "shutProgress": True
            }

            self.log("提交角色提取请求...")
            resp = requests.post(f"{self.host}{UPLOAD_ENDPOINT}", headers=self.get_headers(), json=payload, timeout=60)

            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code} - {resp.text[:200]}...")

            data = resp.json()
            if data.get("code") != 0:
                raise Exception(f"API错误：{data.get('msg')}")

            task_id = data["data"]["id"]
            self.log(f"任务提交成功，Task ID: {task_id}")

            character_id = self.poll_for_result(task_id)

            if character_id:
                thumb_path = self.generate_thumbnail(input_path, original_filename)

                self.characters.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "original_filename": original_filename,
                    "character_id": character_id,
                    "thumbnail": thumb_path if thumb_path else None
                })
                self.save_characters()

                display_str = f"{original_filename} @ {character_id}"
                self.log(f"角色提取成功！{display_str}")
                messagebox.showinfo("完成",
                                    f"角色已追加保存：\n{display_str}\n缩略图：{thumb_path or '无'}\n总记录数：{len(self.characters)}")

        except Exception as e:
            self.log(f"发生错误：{str(e)}", error=True)
            messagebox.showerror("失败", str(e))

        finally:
            self.task_running = False
            self.after(0, lambda: self.upload_btn.configure(state="normal", text="开始上传并提取角色"))
            self.after(0, lambda: self.status_label.configure(text="就绪", text_color="gray"))

    def generate_thumbnail(self, input_path, original_filename):
        try:
            ext = os.path.splitext(input_path)[1].lower()
            thumb_filename = f"thumb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(original_filename.encode()).hexdigest()[:8]}.jpg"
            thumb_fullpath = os.path.join(self.cache_dir, thumb_filename)

            if ext in [".jpg", ".jpeg", ".png"]:
                img = Image.open(input_path)
                img.thumbnail((160, 160))
                img.convert("RGB").save(thumb_fullpath, "JPEG", quality=85)
                return thumb_fullpath

            elif ext == ".mp4":
                cap = cv2.VideoCapture(input_path)
                if not cap.isOpened():
                    return None
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return None

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img.thumbnail((160, 160))
                img.save(thumb_fullpath, "JPEG", quality=85)
                return thumb_fullpath

            return None
        except Exception as e:
            self.log(f"生成缩略图失败：{str(e)}", error=True)
            return None

    def image_to_static_video(self, image_path, output_path):
        try:
            with open(image_path, "rb") as f:
                img_data = f.read()
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                raise Exception("无法解码图片")

            height, width, _ = img.shape
            fps = 30.0
            duration_sec = 4.0
            total_frames = int(fps * duration_sec)

            temp_nosound = "temp_nosound.mp4"
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(temp_nosound, fourcc, fps, (width, height))

            for _ in range(total_frames):
                writer.write(img)
            writer.release()

            if not os.path.exists(temp_nosound):
                raise Exception("无声音视频生成失败")

            self.log("正在添加4秒空白音轨...")
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", temp_nosound,
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                "-t", str(duration_sec),
                output_path
            ]

            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

            if os.path.exists(temp_nosound):
                os.remove(temp_nosound)

            if result.returncode != 0:
                raise Exception(f"ffmpeg 添加音轨失败：{result.stderr.strip() or '未知错误'}")

            if not os.path.exists(output_path):
                raise Exception("带音轨视频未生成")

            self.log("带空白音轨视频生成成功")
            return True

        except Exception as e:
            self.log(f"图片处理失败：{str(e)}", error=True)
            for tmp in ["temp_nosound.mp4", output_path]:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except:
                        pass
            return False

    def file_to_base64(self, filepath):
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def poll_for_result(self, task_id):
        payload = {"id": task_id}
        max_attempts = 120

        for i in range(max_attempts):
            try:
                resp = requests.post(f"{self.host}{RESULT_ENDPOINT}", headers=self.get_headers(), json=payload, timeout=20)
                data = resp.json()

                if data.get("code") != 0:
                    if data.get("code") == -22:
                        raise Exception("任务不存在（可能已超时）")
                    raise Exception(data.get("msg", "未知API错误"))

                result_data = data["data"]
                status = result_data.get("status", "unknown")

                self.log(f"[{i + 1}] 状态：{status}  进度：{result_data.get('progress', '?')}%")

                if status == "succeeded":
                    results = result_data.get("results", [])
                    if results and "character_id" in results[0]:
                        return results[0]["character_id"]
                    else:
                        raise Exception("成功但未找到 character_id")

                elif status == "failed":
                    reason = result_data.get("failure_reason", "未知")
                    err = result_data.get("error", "")
                    raise Exception(f"生成失败 - {reason} {err}")

                time.sleep(5)

            except Exception as e:
                self.log(f"轮询异常（第{i + 1}次）：{str(e)}", error=True)
                time.sleep(5)

        raise Exception("任务超时（10分钟未完成）")


    def open_view_window(self):
        ViewCharactersWindow(self)


class GiteeFolderDownloader:
    def __init__(self, repo_owner: str, repo_name: str, branch: str, token: str = None, cache_file: str = "./download_cache.json"):
        """
        初始化 Gitee 文件夹下载器（含缓存+重试优化，修复更新时间字段问题）
        :param repo_owner: Gitee 仓库所有者（用户名/组织名）
        :param repo_name: 仓库名
        :param branch: 分支名/标签名
        :param token: 个人访问令牌（私有仓库必填）
        :param cache_file: 缓存文件路径（默认 ./download_cache.json）
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.token = token
        self.cache_file = cache_file

        # Gitee API 基础地址
        self.contents_api = f"https://gitee.com/api/v5/repos/{repo_owner}/{repo_name}/contents"
        self.raw_base_url = f"https://gitee.com/{repo_owner}/{repo_name}/raw/{branch}"

        # 请求头（鉴权+防反爬）
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

        # 初始化带重试机制的 Session
        self.session = self._init_retry_session()

    def _init_retry_session(self) -> requests.Session:
        """初始化带重试机制的请求 Session"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.headers.update(self.headers)
        return session

    def _load_cache(self) -> dict:
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️  缓存文件 {self.cache_file} 损坏，将重新创建")
                os.remove(self.cache_file)
        return {}

    def _save_cache(self, cache_data: dict):
        """保存缓存"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

    def _get_file_update_time(self, item: dict) -> str:
        """
        兼容获取 Gitee 文件的更新时间（核心修复点）
        :param item: Gitee API 返回的文件信息
        :return: 标准化的更新时间字符串
        """
        # 优先级：commit.author.date > commit.committer.date > 当前时间（兜底）
        try:
            # 从 commit 中取作者提交时间（Gitee 稳定返回）
            return item["commit"]["author"]["date"]
        except KeyError:
            try:
                return item["commit"]["committer"]["date"]
            except KeyError:
                # 极端情况：用当前时间兜底，避免程序崩溃
                fallback_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                print(f"⚠️  文件 [{item.get('path', '未知文件')}] 未获取到更新时间，使用兜底时间：{fallback_time}")
                return fallback_time

    def _list_files_recursive(self, folder_path: str = "") -> List[dict]:
        """递归获取目标文件夹下所有文件（修复更新时间字段）"""
        files = []
        url = f"{self.contents_api}/{folder_path}" if folder_path else self.contents_api
        params = {"ref": self.branch}

        while url:
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                print(f"❌ 获取文件列表失败：{str(e)}")
                if "403" in str(e) and self.token:
                    print("可能是 Token 无效或权限不足，请检查！")
                return []

            for item in data:
                if item["type"] == "file":
                    # 核心修复：用 _get_file_update_time 获取更新时间
                    files.append({
                        "remote_path": item["path"],
                        "download_url": item["download_url"],
                        "updated_at": self._get_file_update_time(item)
                    })
                elif item["type"] == "dir":
                    # 递归处理子目录
                    sub_files = self._list_files_recursive(item["path"])
                    files.extend(sub_files)

            # 处理分页
            url = response.links.get("next", {}).get("url")
            params = {}

        return files

    def download_folder(self, remote_folder: str, local_save_path: str):
        """下载指定文件夹（含缓存优化）"""
        print(
            f"🔍 正在获取 Gitee 仓库 [{self.repo_owner}/{self.repo_name}] 分支 [{self.branch}] 的文件夹 [{remote_folder}]...")

        # 1. 获取文件列表
        all_files = self._list_files_recursive(remote_folder)
        if not all_files:
            print("⚠️  未找到任何文件（路径/分支错误或权限不足）")
            return

        # 过滤目标文件夹下的文件
        target_files = [f for f in all_files if f["remote_path"].startswith(remote_folder)]
        cache = self._load_cache()
        print(f"✅ 共找到 {len(target_files)} 个文件，开始检查更新...")

        # 2. 分类文件：需下载/未变更
        to_download = []
        unchanged = []
        for file in target_files:
            remote_path = file["remote_path"]
            remote_update_time = file["updated_at"]
            local_update_time = cache.get(remote_path, "")

            if remote_update_time != local_update_time:
                to_download.append(file)
            else:
                unchanged.append(remote_path)

        # 输出未变更文件提示
        if unchanged:
            print(f"ℹ️  {len(unchanged)} 个文件未变更，跳过下载：")
            for path in unchanged[:5]:
                print(f"  - {path}")
            if len(unchanged) > 5:
                print(f"  - 还有 {len(unchanged)-5} 个文件未变更...")

        if not to_download:
            print("\n🎉 所有文件均为最新，无需下载！")
            return

        # 3. 下载新增/更新的文件
        print(f"\n📥 开始下载 {len(to_download)} 个新增/更新文件...")
        for file_info in to_download:
            remote_path = file_info["remote_path"]
            download_url = file_info["download_url"]
            remote_update_time = file_info["updated_at"]

            # 构建本地路径
            local_file_path = os.path.join(local_save_path, remote_path)
            local_dir = os.path.dirname(local_file_path)
            os.makedirs(local_dir, exist_ok=True)

            # 下载文件
            try:
                response = self.session.get(download_url, stream=True)
                response.raise_for_status()
                with open(local_file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ 下载成功：{remote_path}")
                # 更新缓存
                cache[remote_path] = remote_update_time
            except requests.exceptions.RequestException as e:
                print(f"❌ 下载失败：{remote_path} → 错误：{str(e)}")

        # 4. 保存缓存
        self._save_cache(cache)
        print(f"\n🎉 下载完成！本地路径：{os.path.abspath(local_save_path)}")
        print(f"ℹ️  缓存已更新至：{self.cache_file}")


def load_json_file(file_path):
    """
    读取JSON文件，处理文件不存在、格式错误等异常，返回解析后的列表（默认空列表）
    """
    try:
        if not os.path.exists(file_path):
            print(f"提示：文件 {file_path} 不存在，将使用空列表替代")
            return []

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 确保读取的数据是列表格式
        if not isinstance(data, list):
            print(f"警告：{file_path} 内容不是列表格式，将使用空列表替代")
            return []

        return data
    except json.JSONDecodeError as e:
        print(f"错误：{file_path} JSON格式错误 - {e}，将使用空列表替代")
        return []
    except Exception as e:
        print(f"错误：读取 {file_path} 时发生未知错误 - {e}，将使用空列表替代")
        return []


def save_json_file(file_path, data):
    """
    将数据写入JSON文件，保证格式缩进（和示例一致），覆盖原有内容
    """
    try:
        # 确保目标目录存在（比如cache文件夹不存在时自动创建）
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            # indent=2 保证和示例格式一致，ensure_ascii=False 支持中文
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"成功写入文件：{file_path}")
        return True
    except Exception as e:
        print(f"错误：写入 {file_path} 时发生错误 - {e}")
        return False


def merge_and_deduplicate_json():
    """
    核心逻辑：读取两个文件 → 合并 → 去重 → 覆盖写入
    """
    # 定义两个文件的路径
    current_file = "sora_characters.json"
    cache_file = os.path.join("cache", "sora_characters.json")

    # 1. 读取两个文件的内容
    current_data = load_json_file(current_file)
    cache_data = load_json_file(cache_file)

    # 2. 合并并去重（以character_id为唯一标识）
    # 用字典存储：key=character_id，value=完整数据（自动去重）
    deduplicated_dict = {}

    # 先添加当前目录的数据
    for item in current_data:
        char_id = item.get("character_id")
        if char_id:  # 跳过无character_id的无效数据
            deduplicated_dict[char_id] = item

    # 再添加cache目录的数据（重复的会被覆盖，保留cache的最新数据，可根据需求调整顺序）
    for item in cache_data:
        char_id = item.get("character_id")
        if char_id:
            deduplicated_dict[char_id] = item

    # 转换回列表格式
    merged_data = list(deduplicated_dict.values())

    # 3. 覆盖写入两个文件
    save_json_file(current_file, merged_data)
    save_json_file(cache_file, merged_data)

    print(f"\n合并完成！共处理 {len(current_data) + len(cache_data)} 条原始数据，去重后剩余 {len(merged_data)} 条数据")


# ------------------- 你的配置（无需修改） -------------------
if __name__ == "__main__":
    print("开始从Gitee下载文件...")
    REPO_OWNER = "zycisaman"
    REPO_NAME = "sora2-character-repository"
    BRANCH = "master"
    REMOTE_FOLDER = "cache"
    LOCAL_SAVE_PATH = "./"
    GITEE_TOKEN = "797cf3462f79998833ce60eb7f775fa3"

    # 启动下载
    downloader = GiteeFolderDownloader(
        repo_owner=REPO_OWNER,
        repo_name=REPO_NAME,
        branch=BRANCH,
        token=GITEE_TOKEN
    )
    downloader.download_folder(
        remote_folder=REMOTE_FOLDER,
        local_save_path=LOCAL_SAVE_PATH
    )

    print("\n开始本地文件比对替换...")
    merge_and_deduplicate_json()

    print("\n启动程序GUI...")
    # 依赖：pip install customtkinter requests opencv-python numpy pillow
    # 需安装 ffmpeg 并加入 PATH
    app = SoraCharacterUploader()
    app.mainloop()