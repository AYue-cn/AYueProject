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
from typing import List, Dict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------- 配置 ----------------
CONFIG_FILE = "config.json"
STORAGE_FILE = os.path.join("cache", "sora_characters.json")
BACKUP_FILE = os.path.join("cache", "sora_characters_backup.json")
TEMP_VIDEO_PATH = "temp_static_video.mp4"

DEFAULT_CONFIG = {
    "api_key": "",
    "host": "https://grsai.dakka.com.cn",
    "poll_interval": 10,
    "poll_max_attempts": 30
}

UPLOAD_ENDPOINT = "/v1/video/sora-upload-character"
RESULT_ENDPOINT = "/v1/draw/result"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
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
        self.geometry("1080x650")
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

            thumb_label = ctk.CTkLabel(row_frame, text="无", width=100, height=80)
            thumb_label.grid(row=0, column=0, padx=8, pady=4, sticky="n")
            thumb_path = values[0]
            if thumb_path and os.path.exists(thumb_path):
                try:
                    pil_img = Image.open(thumb_path)
                    pil_img.thumbnail((100, 80))
                    ctk_img = ctk.CTkImage(light_image=pil_img, size=(100, 80))
                    thumb_label.configure(image=ctk_img, text="")
                    thumb_label.image = ctk_img
                except:
                    thumb_label.configure(text="加载失败")

            for i, val in enumerate(values[1:], start=1):
                lbl = ctk.CTkLabel(row_frame, text=val, font=("Consolas", 12),
                                   width=[160, 260, 280][i - 1], anchor="w", wraplength=250)
                lbl.grid(row=0, column=i, padx=8, pady=4, sticky="w")

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
        self.title("阿岳Sora2角色上传工具v4.0")
        self.geometry("900x800")
        self.resizable(False, False)

        self.cache_dir = "cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        self.config = load_config()
        self.api_key = self.config.get("api_key", "")
        self.host = self.config.get("host", DEFAULT_CONFIG["host"])
        self.poll_interval = int(self.config.get("poll_interval", DEFAULT_CONFIG["poll_interval"]))
        self.poll_max_attempts = int(self.config.get("poll_max_attempts", DEFAULT_CONFIG["poll_max_attempts"]))

        self.file_path = ""
        self.task_running = False
        self.characters = self.load_characters()

        if not os.path.exists(STORAGE_FILE):
            self.save_characters()

        # Gitee 配置
        self.repo_owner = "zycisaman"
        self.repo_name = "sora2-character-repository"
        self.branch = "master"
        self.remote_folder = "cache"
        self.local_save_path = "./"
        self.gitee_token = "797cf3462f79998833ce60eb7f775fa3"
        self.downloader = GiteeFolderDownloader(
            repo_owner=self.repo_owner,
            repo_name=self.repo_name,
            branch=self.branch,
            token=self.gitee_token,
            app=self
        )

        self.create_widgets()

        if not self.api_key:
            self.log("请在下方输入 API Key 并保存配置", error=True)
        else:
            self.log("程序启动完成。支持 .mp4 / .jpg / .png / .jpeg")

    def load_characters(self):
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
                    else:
                        self.log("角色文件格式错误，已重置为空列表", error=True)
                        return []
            except Exception as e:
                self.log(f"读取角色文件失败: {e}，已重置为空列表", error=True)
                return []
        return []

    def save_characters(self):
        try:
            os.makedirs(os.path.dirname(STORAGE_FILE), exist_ok=True)
            with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.characters, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"保存角色文件失败: {e}", error=True)

    def _backup_local_characters(self) -> bool:
        try:
            if os.path.exists(STORAGE_FILE):
                with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                    local_data = json.load(f)
                with open(BACKUP_FILE, "w", encoding="utf-8") as f:
                    json.dump(local_data, f, ensure_ascii=False, indent=2)
                self.log(f"已备份本地角色文件到：{BACKUP_FILE}")
                return True
            else:
                self.log("本地角色文件不存在，无需备份")
                return False
        except Exception as e:
            self.log(f"备份本地角色文件失败：{str(e)}", error=True)
            return False

    def _merge_characters(self) -> List[Dict]:
        local_backup = []
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                    local_backup = json.load(f)
                if not isinstance(local_backup, list):
                    local_backup = []
                self.log(f"读取本地备份角色数：{len(local_backup)}")
            except Exception as e:
                self.log(f"读取本地备份失败：{str(e)}", error=True)
                local_backup = []

        cloud_data = []
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                    cloud_data = json.load(f)
                if not isinstance(cloud_data, list):
                    cloud_data = []
                self.log(f"读取云端下载角色数：{len(cloud_data)}")
            except Exception as e:
                self.log(f"读取云端角色失败：{str(e)}", error=True)
                cloud_data = []

        merged = {}
        for item in cloud_data:
            cid = item.get("character_id")
            if cid:
                merged[cid] = item

        for item in local_backup:
            cid = item.get("character_id")
            if cid:
                merged[cid] = item
            else:
                key = str(hash(json.dumps(item, sort_keys=True)))
                merged[key] = item

        merged_list = list(merged.values())
        merged_list.sort(key=lambda x: x.get("timestamp", "") or "")

        self.log(
            f"合并完成：总角色数 {len(merged_list)}（云端 {len(cloud_data)} + 本地 {len(local_backup)} - 重复 {len(cloud_data) + len(local_backup) - len(merged_list)}）")
        return merged_list

    def get_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def create_widgets(self):
        config_frame = ctk.CTkFrame(self)
        config_frame.pack(padx=20, pady=(15, 5), fill="x")

        ctk.CTkLabel(config_frame, text="API Key:", font=("Segoe UI", 14)).pack(side="left", padx=(10, 5))
        self.api_key_entry = ctk.CTkEntry(config_frame, width=380, show="*")
        self.api_key_entry.insert(0, self.api_key)
        self.api_key_entry.pack(side="left", padx=5, fill="x", expand=True)

        ctk.CTkButton(config_frame, text="保存配置", width=120,
                      command=self.save_api_config).pack(side="right", padx=10)

        host_frame = ctk.CTkFrame(self)
        host_frame.pack(padx=20, pady=(0, 5), fill="x")

        ctk.CTkLabel(host_frame, text="API Host:", font=("Segoe UI", 14)).pack(side="left", padx=(10, 5))
        self.host_entry = ctk.CTkEntry(host_frame, width=380)
        self.host_entry.insert(0, self.host)
        self.host_entry.pack(side="left", padx=5, fill="x", expand=True)

        poll_frame = ctk.CTkFrame(self)
        poll_frame.pack(padx=20, pady=5, fill="x")

        ctk.CTkLabel(poll_frame, text="轮询间隔（秒）：", font=("Segoe UI", 14)).pack(side="left", padx=(10, 5))
        self.poll_interval_entry = ctk.CTkEntry(poll_frame, width=100)
        self.poll_interval_entry.insert(0, str(self.poll_interval))
        self.poll_interval_entry.pack(side="left", padx=5)

        ctk.CTkLabel(poll_frame, text="最大轮询次数：", font=("Segoe UI", 14)).pack(side="left", padx=(20, 5))
        self.poll_attempts_entry = ctk.CTkEntry(poll_frame, width=100)
        self.poll_attempts_entry.insert(0, str(self.poll_max_attempts))
        self.poll_attempts_entry.pack(side="left", padx=5)

        ctk.CTkLabel(poll_frame, text="(建议间隔3-10秒，次数30-120)", text_color="gray").pack(side="left", padx=10)

        file_frame = ctk.CTkFrame(self)
        file_frame.pack(padx=20, pady=10, fill="x")

        ctk.CTkLabel(file_frame, text="选择文件（视频或图片）：", font=("Segoe UI", 14)).pack(side="left", padx=10)
        self.file_label = ctk.CTkLabel(file_frame, text="未选择文件", text_color="gray")
        self.file_label.pack(side="left", padx=10, fill="x", expand=True)

        ctk.CTkButton(file_frame, text="浏览...", width=100, command=self.select_file).pack(side="right", padx=10)

        time_frame = ctk.CTkFrame(self)
        time_frame.pack(padx=20, pady=5, fill="x")

        ctk.CTkLabel(time_frame, text="截取时间范围（秒）：", font=("Segoe UI", 14)).pack(side="left", padx=(10, 5))
        self.timestamps_entry = ctk.CTkEntry(time_frame, placeholder_text="例如: 0,3", width=180)
        self.timestamps_entry.insert(0, "0,3")
        self.timestamps_entry.pack(side="left", padx=5)

        ctk.CTkLabel(time_frame, text="(最多3秒，图片自动转为4秒30fps+空白音轨)", text_color="gray").pack(side="left",
                                                                                                         padx=5)

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

        self.download_btn = ctk.CTkButton(
            btn_frame, text="下载云端角色（合并）", width=220, height=40,
            command=self.start_download_thread
        )
        self.download_btn.pack(side="left", padx=10)

        self.upload_cloud_btn = ctk.CTkButton(
            btn_frame, text="推送本地到云端", width=220, height=40,
            command=self.start_upload_cloud_thread
        )
        self.upload_cloud_btn.pack(side="left", padx=10)

        log_frame = ctk.CTkFrame(self)
        log_frame.pack(padx=20, pady=(10, 20), fill="both", expand=True)

        self.log_text = ctk.CTkTextbox(log_frame, wrap="word", state="disabled", font=("Consolas", 13))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.status_label = ctk.CTkLabel(self, text="就绪", text_color="gray")
        self.status_label.pack(pady=(0, 10))

    def save_api_config(self):
        new_key = self.api_key_entry.get().strip()
        new_host = self.host_entry.get().strip()
        interval_str = self.poll_interval_entry.get().strip()
        attempts_str = self.poll_attempts_entry.get().strip()

        if not new_key:
            messagebox.showwarning("提示", "API Key 不能为空")
            return

        try:
            new_interval = int(interval_str) if interval_str else DEFAULT_CONFIG["poll_interval"]
            new_interval = max(1, new_interval)
        except:
            new_interval = DEFAULT_CONFIG["poll_interval"]

        try:
            new_attempts = int(attempts_str) if attempts_str else DEFAULT_CONFIG["poll_max_attempts"]
            new_attempts = max(1, new_attempts)
        except:
            new_attempts = DEFAULT_CONFIG["poll_max_attempts"]

        self.api_key = new_key
        self.host = new_host or DEFAULT_CONFIG["host"]
        self.poll_interval = new_interval
        self.poll_max_attempts = new_attempts

        self.config.update({
            "api_key": new_key,
            "host": self.host,
            "poll_interval": new_interval,
            "poll_max_attempts": new_attempts
        })
        save_config(self.config)

        self.log(f"配置已保存 | 轮询：{new_interval}秒 × {new_attempts}次")
        messagebox.showinfo("成功", "配置已更新")

    def log(self, message, error=False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_tag = "error" if error else "success" if any(
            word in message for word in ["成功", "完成", "已生成", "保存", "合并", "同步"]) else "info"
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

        threading.Thread(target=self.process_and_upload, args=(self.file_path, timestamps), daemon=True).start()

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
            # else: 失败情况已在 poll_for_result 内部处理弹窗和日志

        except Exception as e:
            self.log(f"发生错误：{str(e)}", error=True)
            messagebox.showerror("处理失败", str(e))

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
        interval = self.poll_interval
        max_attempts = self.poll_max_attempts

        total_sec = interval * max_attempts
        min_part = total_sec // 60
        sec_part = total_sec % 60
        timeout_str = f"{min_part}分{sec_part}秒" if min_part > 0 else f"{sec_part}秒"

        for i in range(max_attempts):
            try:
                resp = requests.post(f"{self.host}{RESULT_ENDPOINT}", headers=self.get_headers(), json=payload,
                                     timeout=20)
                resp.raise_for_status()
                data = resp.json()

                if data.get("code") != 0:
                    if data.get("code") == -22:
                        self.log("任务不存在（可能已超时或被清理）", error=True)
                        return None
                    raise Exception(data.get("msg") or f"API错误 code: {data.get('code')}")

                result_data = data.get("data", {})
                status = result_data.get("status", "unknown")
                progress = result_data.get("progress", "?")

                self.log(f"[{i + 1:02d}/{max_attempts:02d}] 状态：{status}  进度：{progress}%")

                if status == "succeeded":
                    results = result_data.get("results", [])
                    if results and isinstance(results, list) and "character_id" in results[0]:
                        cid = results[0]["character_id"]
                        self.log(f"角色提取成功！Character ID: {cid}")
                        return cid
                    else:
                        self.log("状态为 succeeded 但未找到 character_id", error=True)
                        return None

                elif status == "failed":
                    error_text = result_data.get("error", "").strip()
                    reason = result_data.get("failure_reason", "").strip().lower()

                    if reason == "error" and error_text:
                        error_msg = f"上传失败 - {error_text}"
                        self.log(error_msg, error=True)
                        self.after(0, lambda msg=error_text: messagebox.showerror("上传失败", msg))
                        return None  # 立即终止轮询

                    # 其他 failed 情况
                    display = error_text or reason or "未知失败原因"
                    full_msg = f"生成失败 - {display}"
                    self.log(full_msg, error=True)
                    self.after(0, lambda msg=full_msg: messagebox.showerror("生成失败", msg))
                    return None  # 同样终止

                time.sleep(interval)

            except Exception as e:
                self.log(f"轮询异常（第{i + 1}次）：{str(e)}", error=True)
                time.sleep(interval)

        # 超时
        timeout_msg = f"任务超时（超过{timeout_str}未完成） - Task ID: {task_id}"
        self.log(timeout_msg, error=True)
        self.after(0, lambda: messagebox.showerror("任务超时", timeout_msg))
        return None

    def open_view_window(self):
        ViewCharactersWindow(self)

    def start_download_thread(self):
        if self.task_running:
            messagebox.showwarning("提示", "已有任务正在进行，请等待完成")
            return

        self.task_running = True
        self.download_btn.configure(state="disabled", text="同步中...")
        self.status_label.configure(text="正在从云端合并同步角色...", text_color="yellow")

        threading.Thread(target=self.sync_from_cloud, daemon=True).start()

    def sync_from_cloud(self):
        try:
            self.log("=== 开始云端同步（合并模式） ===")

            self._backup_local_characters()

            self.log("正在下载云端最新角色数据和缩略图...")
            self.downloader.download_folder(self.remote_folder, self.local_save_path)

            self.log("正在合并本地备份与云端数据...")
            merged = self._merge_characters()

            with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)

            self.characters = merged

            self.log(f"云端同步合并完成！当前总角色数量：{len(self.characters)}")
            messagebox.showinfo("同步成功", f"已合并角色数据\n当前本地总记录：{len(self.characters)} 条")

        except Exception as e:
            self.log(f"同步过程中发生错误：{str(e)}", error=True)
            messagebox.showerror("同步失败", str(e))

        finally:
            self.task_running = False
            self.after(0, lambda: self.download_btn.configure(state="normal", text="下载云端角色（合并）"))
            self.after(0, lambda: self.status_label.configure(text="就绪", text_color="gray"))

    def start_upload_cloud_thread(self):
        if self.task_running:
            messagebox.showwarning("提示", "已有任务正在进行，请等待完成")
            return

        self.task_running = True
        self.upload_cloud_btn.configure(state="disabled", text="处理中...")
        self.status_label.configure(text="先备份本地内容...", text_color="yellow")

        threading.Thread(target=self.upload_to_cloud, daemon=True).start()

    def upload_to_cloud(self):
        try:
            self.log("=== 上传前置步骤1：备份本地角色文件 ===")
            self._backup_local_characters()

            self.log("=== 上传前置步骤2：下载云端最新内容 ===")
            self.downloader.download_folder(self.remote_folder, self.local_save_path)

            self.log("正在合并本地备份与云端数据...")
            merged = self._merge_characters()

            with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)

            self.characters = merged
            self.log(f"合并后的角色已保存到本地，当前总角色数：{len(self.characters)}")

            self.log("=== 开始上传合并后的 cache 文件夹到 Gitee ===")
            self.downloader.upload_folder(self.cache_dir, self.remote_folder)

            self.log("=== 上传合并完成！本地+云端角色已同步 ===")

            if os.path.exists(BACKUP_FILE):
                os.remove(BACKUP_FILE)
                self.log("已清理临时备份文件")

        except Exception as e:
            self.log(f"上传到 Gitee 发生错误：{str(e)}", error=True)

        finally:
            self.task_running = False
            self.after(0, lambda: self.upload_cloud_btn.configure(state="normal", text="推送本地到云端"))
            self.after(0, lambda: self.status_label.configure(text="就绪", text_color="gray"))


class GiteeFolderDownloader:
    def __init__(self, repo_owner: str, repo_name: str, branch: str, token: str = None,
                 cache_file: str = "./download_cache.json", app=None):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.token = token
        self.cache_file = cache_file
        self.app = app

        self.base_api = f"https://gitee.com/api/v5/repos/{repo_owner}/{repo_name}/contents"
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }
        self.put_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Authorization": f"token {self.token}" if self.token else ""
        }

        self.session = self._init_retry_session()

    def log(self, message, error=False):
        if self.app:
            self.app.log(message, error=error)
        else:
            print(message)

    def _init_retry_session(self):
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT"]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        return session

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                self.log(f"缓存文件 {self.cache_file} 损坏，已删除", error=True)
                os.remove(self.cache_file)
        return {}

    def _save_cache(self, cache_data: dict):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            self.log(f"缓存已更新至：{self.cache_file}")
        except Exception as e:
            self.log(f"保存缓存失败: {e}", error=True)

    def _get_file_update_time(self, item: dict) -> str:
        try:
            return item["commit"]["author"]["date"]
        except KeyError:
            try:
                return item["commit"]["committer"]["date"]
            except KeyError:
                fallback = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.log(f"文件 [{item.get('path', '未知')}] 未获取到更新时间，使用兜底时间", error=True)
                return fallback

    def _list_files_recursive(self, folder_path: str = "") -> List[dict]:
        files = []
        url = f"{self.base_api}/{folder_path}" if folder_path else self.base_api
        params = {"ref": self.branch}

        while url:
            try:
                resp = self.session.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                self.log(f"获取文件列表失败：{e}", error=True)
                return []

            for item in data:
                if item["type"] == "file":
                    files.append({
                        "remote_path": item["path"],
                        "download_url": item["download_url"],
                        "updated_at": self._get_file_update_time(item),
                        "sha": item.get("sha")
                    })
                elif item["type"] == "dir":
                    files.extend(self._list_files_recursive(item["path"]))

            url = resp.links.get("next", {}).get("url")
            params = {}

        return files

    def download_folder(self, remote_folder: str, local_save_path: str):
        self.log(
            f"正在获取 Gitee 仓库 {self.repo_owner}/{self.repo_name} 分支 {self.branch} 的文件夹 {remote_folder}...")

        all_files = self._list_files_recursive(remote_folder)
        if not all_files:
            self.log("未找到任何文件（路径/分支错误或权限不足）", error=True)
            return

        target_files = [f for f in all_files if
                        f["remote_path"].startswith(remote_folder + "/") or f["remote_path"] == remote_folder.rstrip(
                            "/")]
        cache = self._load_cache()

        self.log(f"共找到 {len(target_files)} 个文件，开始检查更新...")

        to_download = []
        unchanged = []
        for file in target_files:
            path = file["remote_path"]
            if cache.get(path) != file["updated_at"]:
                to_download.append(file)
            else:
                unchanged.append(path)

        if unchanged:
            self.log(f"{len(unchanged)} 个文件未变更，跳过下载")

        if not to_download:
            self.log("所有文件均为最新，无需下载！")
            return

        self.log(f"开始下载 {len(to_download)} 个新增/更新文件...")
        for file in to_download:
            local_path = os.path.join(local_save_path, file["remote_path"])
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            try:
                resp = self.session.get(file["download_url"], stream=True)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                cache[file["remote_path"]] = file["updated_at"]
                self.log(f"下载成功：{file['remote_path']}")
            except Exception as e:
                self.log(f"下载失败 {file['remote_path']}：{e}", error=True)

        self._save_cache(cache)
        self.log(f"下载完成！本地路径：{os.path.abspath(local_save_path)}")

    def _get_remote_file_info(self, remote_path: str) -> dict:
        url = f"{self.base_api}/{remote_path}"
        params = {"ref": self.branch}
        try:
            resp = self.session.get(url, params=params, headers=self.headers)

            if resp.status_code == 404:
                return {"exists": False, "sha": "", "content": b""}

            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, dict) or data.get("type") != "file":
                return {"exists": False, "sha": "", "content": b""}

            content = base64.b64decode(data.get("content", "")) if data.get("content") else b""

            return {
                "exists": True,
                "sha": data.get("sha", ""),
                "content": content
            }
        except Exception as e:
            self.log(f"获取远程文件信息失败 {remote_path} - {str(e)}", error=True)
            return None

    def _upload_image_post(self, local_path: str, remote_path: str) -> bool:
        try:
            local_content = self._read_local_file(local_path)
            content_b64 = base64.b64encode(local_content).decode("utf-8")

            form_data = {
                "access_token": self.token,
                "content": content_b64,
                "message": f"上传缩略图: {os.path.basename(remote_path)} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
                "branch": self.branch
            }

            upload_url = f"{self.base_api}/{remote_path}"
            resp = self.session.post(
                url=upload_url,
                data=form_data,
                headers=self.headers,
                timeout=30
            )

            resp.raise_for_status()
            response_data = resp.json()

            if "content" in response_data and "sha" in response_data.get("content", {}):
                self.log(f"[POST成功] 缩略图：{os.path.basename(remote_path)}")
                return True
            else:
                raise Exception("响应缺少content/sha字段")

        except Exception as e:
            self.log(f"[POST失败] 缩略图：{os.path.basename(remote_path)} - {str(e)}", error=True)
            return False

    def _upload_json_put(self, local_path: str, remote_path: str) -> bool:
        try:
            remote_info = self._get_remote_file_info(remote_path)
            if remote_info is None:
                self.log(f"[PUT失败] JSON文件：{os.path.basename(remote_path)} - 获取远程信息异常", error=True)
                return False

            local_content = self._read_local_file(local_path)
            content_b64 = base64.b64encode(local_content).decode("utf-8")

            payload = {
                "branch": self.branch,
                "content": content_b64,
                "message": f"更新JSON文件: {os.path.basename(remote_path)} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
            }

            if remote_info["exists"]:
                payload["sha"] = remote_info["sha"]

            upload_url = f"{self.base_api}/{remote_path}"
            resp = self.session.put(
                url=upload_url,
                json=payload,
                headers=self.put_headers,
                timeout=30
            )

            resp.raise_for_status()
            response_data = resp.json()

            if "content" in response_data and "sha" in response_data.get("content", {}):
                self.log(f"[PUT成功] JSON文件：{os.path.basename(remote_path)}")
                return True
            else:
                raise Exception("响应缺少content/sha字段")

        except Exception as e:
            self.log(f"[PUT失败] JSON文件：{os.path.basename(remote_path)} - {str(e)}", error=True)
            return False

    def upload_folder(self, local_folder: str, remote_folder: str):
        self.log(f"开始分类型上传本地文件夹 {local_folder} 到 Gitee {remote_folder}...")

        local_files = []
        image_ext = [".jpg", ".png", ".jpeg", ".gif", ".bmp"]
        json_ext = [".json"]

        for root, _, files in os.walk(local_folder):
            for file in files:
                local_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                rel_path = os.path.relpath(local_path, local_folder).replace("\\", "/")
                remote_path = f"{remote_folder}/{rel_path}".rstrip("/")

                file_type = "image" if file_ext in image_ext else "json" if file_ext in json_ext else "other"

                local_files.append({
                    "local_path": local_path,
                    "remote_path": remote_path,
                    "file_type": file_type,
                    "filename": file
                })

        if not local_files:
            self.log("本地文件夹为空，无需上传")
            return

        success = fail = skip = 0

        for item in local_files:
            if item["file_type"] == "image":
                if self._upload_image_post(item["local_path"], item["remote_path"]):
                    success += 1
                else:
                    fail += 1
            elif item["file_type"] == "json":
                if self._upload_json_put(item["local_path"], item["remote_path"]):
                    success += 1
                else:
                    fail += 1
            else:
                skip += 1
                self.log(f"[跳过] 不支持的文件类型：{item['filename']}")

        self.log(f"\n上传结果：成功 {success}，失败 {fail}，跳过 {skip}")
        if fail > 0:
            self.log(f"⚠️ 有 {fail} 个文件上传失败，请检查日志", error=True)

    def _read_local_file(self, path: str) -> bytes:
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as e:
            self.log(f"读取本地文件失败 {path} - {str(e)}", error=True)
            return b""


if __name__ == "__main__":
    app = SoraCharacterUploader()
    app.mainloop()
