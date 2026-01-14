import os
import subprocess
import shutil
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

# ==================== 默认配置 ====================
default_seven_zip_path = r'D:\Program Files\7-Zip\7z.exe'  # 默认路径，可修改

# 默认支持的所有格式
ALL_EXTENSIONS = {
    '.zip': True,
    '.7z': True,
    '.rar': True,
    '.tar': True,
    '.gz': True,
    '.bz2': True,
    '.xz': True
}

# 外观设置
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class PDFExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("批量解压压缩包 → 汇总所有 PDF")
        self.geometry("900x760")
        self.minsize(900, 760)

        # 变量
        self.seven_zip_path_var = ctk.StringVar(value=default_seven_zip_path)
        self.source_folder = ctk.StringVar()
        self.output_folder = ctk.StringVar()
        self.extension_vars = {ext: ctk.BooleanVar(value=True) for ext in ALL_EXTENSIONS}
        self.is_running = False
        self.thread = None

        self.create_widgets()

    def create_widgets(self):
        main_frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # 标题
        title = ctk.CTkLabel(main_frame, text="PDF 批量提取工具", font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=(10, 40))

        # 7-Zip 路径设置
        zip_path_frame = ctk.CTkFrame(main_frame)
        zip_path_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(zip_path_frame, text="7-Zip 可执行文件路径（7z.exe）：", font=ctk.CTkFont(size=14)).pack(anchor="w",
                                                                                                           padx=20,
                                                                                                           pady=(15, 5))
        ctk.CTkEntry(zip_path_frame, textvariable=self.seven_zip_path_var, height=40,
                     placeholder_text="请选择7z.exe所在路径").pack(side="left", fill="x", expand=True, padx=(20, 10),
                                                                   pady=(0, 15))
        ctk.CTkButton(zip_path_frame, text="浏览", width=120, command=self.choose_7zip_path).pack(side="right", padx=20,
                                                                                                  pady=(0, 15))

        # 支持的压缩格式勾选
        ext_frame = ctk.CTkFrame(main_frame)
        ext_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(ext_frame, text="支持解压的压缩包格式：", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20,
                                                                                              pady=(15, 5))

        checkboxes_inner = ctk.CTkFrame(ext_frame)
        checkboxes_inner.pack(fill="x", padx=20, pady=(0, 15))

        row_frame = None
        for i, (ext, var) in enumerate(self.extension_vars.items()):
            if i % 4 == 0:
                row_frame = ctk.CTkFrame(checkboxes_inner)
                row_frame.pack(fill="x", pady=4)
            ctk.CTkCheckBox(row_frame, text=ext.upper(), variable=var, font=ctk.CTkFont(size=13)).pack(side="left",
                                                                                                       padx=30)

        # 全选 / 全不选 按钮
        select_all_frame = ctk.CTkFrame(ext_frame)
        select_all_frame.pack(pady=(0, 10))
        ctk.CTkButton(select_all_frame, text="全选", width=100, command=self.select_all_extensions).pack(side="left",
                                                                                                         padx=10)
        ctk.CTkButton(select_all_frame, text="全不选", width=100, command=self.deselect_all_extensions).pack(
            side="left", padx=10)

        # 源文件夹
        src_frame = ctk.CTkFrame(main_frame)
        src_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(src_frame, text="压缩包所在文件夹：", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20,
                                                                                          pady=(15, 5))
        ctk.CTkEntry(src_frame, textvariable=self.source_folder, height=40,
                     placeholder_text="请选择包含各种压缩包的文件夹（支持子文件夹）").pack(side="left", fill="x",
                                                                                         expand=True, padx=(20, 10),
                                                                                         pady=(0, 15))
        ctk.CTkButton(src_frame, text="浏览", width=120, command=self.choose_source).pack(side="right", padx=20,
                                                                                          pady=(0, 15))

        # 输出文件夹
        out_frame = ctk.CTkFrame(main_frame)
        out_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(out_frame, text="PDF 保存文件夹：", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20,
                                                                                        pady=(15, 5))
        ctk.CTkEntry(out_frame, textvariable=self.output_folder, height=40,
                     placeholder_text="所有提取出的 PDF 将汇总到这里").pack(side="left", fill="x", expand=True,
                                                                            padx=(20, 10), pady=(0, 15))
        ctk.CTkButton(out_frame, text="浏览", width=120, command=self.choose_output).pack(side="right", padx=20,
                                                                                          pady=(0, 15))

        # 操作按钮
        btn_frame = ctk.CTkFrame(main_frame)
        btn_frame.pack(pady=25)
        self.start_btn = ctk.CTkButton(btn_frame, text="开始处理", height=50, font=ctk.CTkFont(size=18, weight="bold"),
                                       command=self.start_processing)
        self.start_btn.pack(side="left", padx=25)
        self.stop_btn = ctk.CTkButton(btn_frame, text="停止处理", height=50, font=ctk.CTkFont(size=16),
                                      command=self.stop_processing, state="disabled", fg_color="gray30")
        self.stop_btn.pack(side="left", padx=25)

        # 进度条
        self.progress = ctk.CTkProgressBar(main_frame)
        self.progress.pack(fill="x", padx=40, pady=(10, 20))
        self.progress.set(0)

        # 日志区
        ctk.CTkLabel(main_frame, text="处理日志：", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=20)
        self.log_box = ctk.CTkTextbox(main_frame, height=200, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        self.log_box.insert("end", "就绪：请配置路径和格式后，选择文件夹并点击“开始处理”\n\n")
        self.log_box.configure(state="disabled")

    def log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def choose_7zip_path(self):
        file = filedialog.askopenfilename(
            title="选择 7z.exe 文件",
            filetypes=[("7-Zip Executable", "7z.exe"), ("All Files", "*.*")],
            initialdir=os.path.dirname(self.seven_zip_path_var.get()) if os.path.exists(
                self.seven_zip_path_var.get()) else None
        )
        if file:
            self.seven_zip_path_var.set(file)

    def choose_source(self):
        folder = filedialog.askdirectory(title="选择压缩包所在文件夹")
        if folder:
            self.source_folder.set(folder)

    def choose_output(self):
        folder = filedialog.askdirectory(title="选择PDF保存文件夹")
        if folder:
            self.output_folder.set(folder)

    def select_all_extensions(self):
        for var in self.extension_vars.values():
            var.set(True)

    def deselect_all_extensions(self):
        for var in self.extension_vars.values():
            var.set(False)

    def get_selected_extensions(self):
        """返回当前用户勾选的格式元组"""
        return tuple(ext for ext, var in self.extension_vars.items() if var.get())

    def start_processing(self):
        src = self.source_folder.get().strip()
        out = self.output_folder.get().strip()
        seven_zip = self.seven_zip_path_var.get().strip()

        if not src or not out:
            messagebox.showwarning("提示", "请先选择压缩包文件夹和PDF保存文件夹！")
            return

        if not os.path.exists(seven_zip):
            messagebox.showerror("错误", f"未找到7-Zip程序！\n路径：{seven_zip}\n请重新选择正确的7z.exe文件")
            return

        selected_ext = self.get_selected_extensions()
        if not selected_ext:
            messagebox.showwarning("提示", "请至少选择一种压缩包格式！")
            return

        # 更新全局变量
        global seven_zip_path
        seven_zip_path = seven_zip

        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color="#D35B58")
        self.progress.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.log(f"使用7-Zip路径：{seven_zip}\n")
        self.log(f"支持格式：{' '.join(selected_ext).upper()}\n")
        self.log("开始扫描压缩包...\n")

        self.thread = threading.Thread(target=self.process_task, args=(selected_ext,), daemon=True)
        self.thread.start()

    def stop_processing(self):
        self.is_running = False
        self.log("\n用户已请求停止，正在等待当前任务完成...\n")

    def process_task(self, selected_extensions):
        src_folder = self.source_folder.get()
        out_folder = self.output_folder.get()
        temp_dir = os.path.join(out_folder, "temp_extract")

        try:
            os.makedirs(out_folder, exist_ok=True)
            os.makedirs(temp_dir, exist_ok=True)

            archives = []
            for root, _, files in os.walk(src_folder):
                for file in files:
                    if file.lower().endswith(selected_extensions):
                        archives.append(os.path.join(root, file))

            total = len(archives)
            if total == 0:
                self.log("未找到任何匹配的压缩包文件（根据当前勾选格式）。")
                self.finish()
                return

            self.log(f"共发现 {total} 个压缩包，开始提取PDF...\n")

            processed = 0
            moved_count = 0

            for archive_path in archives:
                if not self.is_running:
                    self.log("处理已停止。")
                    break

                filename = os.path.basename(archive_path)
                self.log(f"[{processed + 1}/{total}] 正在处理：{filename}")

                if self.extract_pdfs(archive_path, temp_dir):
                    processed += 1

                self.progress.set((processed + 1) / total)

            self.log("\n正在汇总所有PDF文件...")
            moved_count = self.move_pdfs(temp_dir, out_folder)

            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

            self.log(f"\n=== 处理完成 ===")
            self.log(f"成功处理 {processed}/{total} 个压缩包")
            self.log(f"共提取并汇总 {moved_count} 个PDF文件")
            self.log(f"保存位置：{out_folder}")

        except Exception as e:
            self.log(f"\n发生未知错误：{str(e)}")

        self.finish()
        messagebox.showinfo("完成", f"全部完成！\n成功提取 {moved_count} 个PDF文件\n保存至：{out_folder}")

    def extract_pdfs(self, archive_path, temp_dir):
        try:
            cmd = [
                seven_zip_path, 'x', archive_path,
                '*.pdf', '-r', f'-o{temp_dir}', '-y'
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='gbk',
                errors='replace',
                timeout=600
            )
            if result.returncode in (0, 1):
                self.log("   → 提取PDF完成")
                return True
            else:
                error_msg = result.stderr.strip().replace('\n', ' ')[:200]
                self.log(f"   → 提取失败：{error_msg}")
                return False
        except subprocess.TimeoutExpired:
            self.log("   → 超时，已跳过此文件")
            return False
        except Exception as e:
            self.log(f"   → 异常：{str(e)}")
            return False

    def move_pdfs(self, temp_dir, out_dir):
        count = 0
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith('.pdf'):
                    src = os.path.join(root, file)
                    dst = os.path.join(out_dir, file)

                    if os.path.exists(dst):
                        base, ext = os.path.splitext(dst)
                        i = 1
                        while os.path.exists(f"{base}({i}){ext}"):
                            i += 1
                        dst = f"{base}({i}){ext}"
                        self.log(f"   → {file} → {os.path.basename(dst)}（重名自动重命名）")
                    else:
                        self.log(f"   → {file}")

                    try:
                        shutil.move(src, dst)
                        count += 1
                    except Exception as e:
                        self.log(f"   → 移动失败 {file}: {e}")
        return count

    def finish(self):
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color="gray30")
        if self.progress.get() < 1:
            self.progress.set(1)


# ==================== 启动程序 ====================
if __name__ == "__main__":
    # 首次运行请执行：pip install customtkinter
    seven_zip_path = default_seven_zip_path  # 全局变量，运行时会被用户选择覆盖
    app = PDFExtractorApp()
    app.mainloop()