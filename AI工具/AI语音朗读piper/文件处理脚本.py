# -*- coding: utf-8 -*-
"""
Excel → Sentence JSON 一步式工具（短句向后合并）
GUI: ttkbootstrap
"""

import os
import json
import re
import threading
from pathlib import Path

import pandas as pd
import nltk
from nltk.tokenize import sent_tokenize

import tkinter as tk
from tkinter import filedialog
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *


# NLTK 初始化
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=False)


def excel_col_letter_to_index(letter: str) -> int:
    letter = letter.upper()
    index = 0
    for c in letter:
        index = index * 26 + (ord(c) - ord("A") + 1)
    return index - 1


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str, min_len: int) -> list[str]:
    """分句 + 短句向后连续合并，直到 >= min_len 或无更多句子"""
    if not text:
        return []

    raw_sentences = sent_tokenize(text)
    result = []
    i = 0

    while i < len(raw_sentences):
        current = raw_sentences[i].strip()
        if len(current) >= min_len:
            result.append(current)
            i += 1
            continue

        merged = current
        j = i + 1
        while j < len(raw_sentences) and len(merged) < min_len:
            next_sent = raw_sentences[j].strip()
            if not next_sent:
                j += 1
                continue
            merged += " " + next_sent
            j += 1

        result.append(merged.strip())
        i = j

    return [s for s in result if s.strip()]


class ExcelToJsonApp:
    def __init__(self, root):
        self.root = root
        self.root.title("阿岳 Excel → JSON 分句工具")
        self.root.geometry("600x420")

        self.build_ui()

    def build_ui(self):
        frame = ttkb.Frame(self.root, padding=15)
        frame.pack(fill="both", expand=True)

        ttkb.Label(frame, text="Excel 输入文件夹").pack(anchor="w")
        path_frame = ttkb.Frame(frame)
        path_frame.pack(fill="x", pady=5)

        self.input_dir = tk.StringVar()
        ttkb.Entry(path_frame, textvariable=self.input_dir).pack(side="left", fill="x", expand=True)
        ttkb.Button(path_frame, text="选择", command=self.choose_input_dir).pack(side="left", padx=5)

        param = ttkb.Labelframe(frame, text="参数设置", padding=10)
        param.pack(fill="x", pady=10)

        row = 0

        ttkb.Label(param, text="提取列（如 J）").grid(row=row, column=0, sticky="w")
        self.col_letter = tk.StringVar(value="J")
        ttkb.Entry(param, textvariable=self.col_letter, width=10).grid(row=row, column=1, sticky="w")

        ttkb.Label(param, text="起始行（Excel 行号）").grid(row=row, column=2, sticky="w", padx=10)
        self.start_row = tk.IntVar(value=2)
        ttkb.Entry(param, textvariable=self.start_row, width=10).grid(row=row, column=3, sticky="w")

        row += 1

        ttkb.Label(param, text="最小句子长度（字符数）").grid(row=row, column=0, sticky="w")
        self.min_sentence_len = tk.IntVar(value=50)
        ttkb.Entry(param, textvariable=self.min_sentence_len, width=10).grid(row=row, column=1, sticky="w")

        ttkb.Label(param, text="输出 JSON 文件名").grid(row=row, column=2, sticky="w", padx=10)
        self.output_name = tk.StringVar(value="剧本.json")
        ttkb.Entry(param, textvariable=self.output_name).grid(row=row, column=3, sticky="w")

        ttkb.Button(
            frame,
            text="开始处理（Excel → JSON）",
            bootstyle=SUCCESS,
            command=self.start_thread
        ).pack(pady=10)

        ttkb.Label(frame, text="运行日志").pack(anchor="w")
        self.log = tk.Text(frame, height=18)
        self.log.pack(fill="both", expand=True)

    def log_print(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.root.update_idletasks()

    def choose_input_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.input_dir.set(path)

    def start_thread(self):
        t = threading.Thread(target=self.run)
        t.daemon = True
        t.start()

    def run(self):
        self.log.delete("1.0", "end")

        input_dir = Path(self.input_dir.get())
        if not input_dir.is_dir():
            self.log_print("❌ 输入文件夹不存在")
            return

        try:
            col_idx = excel_col_letter_to_index(self.col_letter.get())
        except Exception:
            self.log_print("❌ 列字母不合法")
            return

        start_row = max(self.start_row.get() - 1, 0)
        min_len = self.min_sentence_len.get()
        output_path = input_dir / self.output_name.get()

        all_segments = []
        total_files = 0
        global_index = 0

        self.log_print("开始处理 Excel 文件...\n")

        for file in sorted(input_dir.glob("*.xls*")):
            total_files += 1
            self.log_print(f"读取：{file.name}")

            try:
                df = pd.read_excel(file, engine="openpyxl")

                if len(df.columns) <= col_idx:
                    self.log_print("  → 列数不足，跳过")
                    continue

                series = df.iloc[start_row:, col_idx]

                for cell in series:
                    if pd.isna(cell):
                        continue

                    text = clean_text(str(cell))
                    if not text:
                        continue

                    sentences = split_sentences(text, min_len)

                    for s in sentences:
                        global_index += 1
                        all_segments.append({
                            "source_file": file.name,
                            "index": global_index,
                            "text": s
                        })

                self.log_print(f"  → 累计句子数：{global_index}")

            except Exception as e:
                self.log_print(f"  ❌ 出错：{e}")

        if not all_segments:
            self.log_print("\n⚠️ 没有生成任何句子")
            return

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_segments, f, ensure_ascii=False, indent=2)

        self.log_print("\n✅ 处理完成")
        self.log_print(f"Excel 文件数：{total_files}")
        self.log_print(f"总句子数：{len(all_segments)}")
        self.log_print(f"输出文件：{output_path}")


if __name__ == "__main__":
    app = ttkb.Window(themename="flatly")
    ExcelToJsonApp(app)
    app.mainloop()