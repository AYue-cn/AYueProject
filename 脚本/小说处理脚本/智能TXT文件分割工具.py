import os
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import threading
import webbrowser


class TxtSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("智能TXT文件分割工具")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # 存储已处理文件路径，用于快捷打开
        self.processed_files = []

        # 要添加到每个分割文件后的修改要求字符串
        self.append_text = """

为了让小说变成短视频文案，请对以上小说进行全方位修改，严格遵循以下要求：
1.视角转换：将全文所有内容统一调整为主人公第一视角（以 “我” 为叙述主体） ，确保心理活动、动作描写、场景感知均从 “我” 的视角出发，贴合主人公的身份与情感逻辑，删除所有第三人称叙述内容。 
2.纠错润色：修正文中所有错别字、标点错误及语法语病，优化语句通顺度，保持语言风格与主人公人设一致，避免生硬表达。
3.情节精简：删除与核心故事线无关的冗余情节（如无意义的环境描写、无关人物的多余互动、不推动剧情的琐碎细节），保留关键信息与必要铺垫。
4.冲突强化：聚焦小说核心情节冲突（需明确冲突核心：如人物矛盾、目标阻碍、情感纠葛等），通过增强 “我” 的心理挣扎、行动困境、对手张力等方式深化冲突，突出情节的紧张感与感染力，确保修改后核心冲突更鲜明、更有层次。
5.数字改写：所有数字改为中文，方便AI进行朗读。
6.为贴合动漫短视频的画面动态感，要在角色对话前补充符合人设的语气、动作描述（如 “大声喝道”“急声劝阻”“紧盯着屏幕报出”），让台词更有场景张力，同时保留第一视角的沉浸感。
7.修正标点符号，仅使用逗号和句号。
8.开头改写，根据整篇小说内容，写一句话的文案开头，风格可以学习如下风格：猎奇，反常识【葬礼当天，我当场从棺材里跳出来】【我爸是金龙，我妈是金龙，而我却是一条青龙】反差，反转【我身为奥特曼，却从不打怪兽，反而一门心思想要毁灭人类】【平时连蚂蚁都不敢踩的我，却在一夜之间宰了十万头牛】反问【高考满分和一千万你选哪个？】【假如给你十个老婆，你能玩出什么花活？】爽点前置【男人为了证明黑狗血可以辟邪，竟用黑狗血在身上纹满了整个地府，左肩阎罗，右键判官，前胸无常，后背马面，地藏孟婆护在腰间】强行带入【杀过人的都知道，毁尸灭迹是很重要的一环，但更重要的却是如何跑路】【睡过棺材的都知道，那里面是又黑又潮，空间还闭塞狭小】擦边【我的青梅竹马是个小色批，从小她就喜欢偷看我洗澡】【我的继姐特别坏，每晚都要搂着我睡，并且还时不时搞一些小动作】。根据小说内容，选取一种风格改写一个开头再最前面，吸引看的人停留。
9.因为后续要进行AI绘画，要避免一些词汇容易让ai误会，例如猫眼本来是门上的观察孔，却被AI画成猫的眼睛，如果有这些易混淆的词汇，请替换成不易混淆的。
请基于以上要求完成修改，保留原文核心设定与人物特质，使修改后的内容逻辑连贯、代入感强。
"""

        # 设置界面样式
        self.style = ttk.Style()
        self.style.configure("TButton", font=("微软雅黑", 10))
        self.style.configure("TLabel", font=("微软雅黑", 10))
        self.style.configure("TOpenButton.TButton", font=("微软雅黑", 9), padding=2)

        self._create_widgets()

    def _create_widgets(self):
        # 标题
        title_label = ttk.Label(
            self.root,
            text="智能TXT文件分割工具",
            font=("微软雅黑", 14, "bold")
        )
        title_label.pack(pady=10)

        # 分割字数设置区域
        settings_frame = ttk.Frame(self.root)
        settings_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(settings_frame, text="分割字数:").pack(side=tk.LEFT, padx=5)

        # 滑块控制分割字数
        self.split_count = tk.IntVar(value=5000)
        self.count_slider = ttk.Scale(
            settings_frame,
            from_=1000,
            to=10000,
            orient="horizontal",
            length=300,
            variable=self.split_count,
            command=self._update_count_label
        )
        self.count_slider.pack(side=tk.LEFT, padx=5)

        self.count_label = ttk.Label(
            settings_frame,
            text=f"{self.split_count.get()} 个汉字",
            width=15
        )
        self.count_label.pack(side=tk.LEFT, padx=5)

        # 选择文件按钮
        self.select_btn = ttk.Button(
            self.root,
            text="选择多个TXT文件",
            command=self.select_files
        )
        self.select_btn.pack(pady=10)

        # 进度条
        self.progress_bar = ttk.Progressbar(
            self.root,
            orient="horizontal",
            length=800,
            mode="determinate"
        )
        self.progress_bar.pack(pady=10)

        # 日志区域
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        ttk.Label(log_frame, text="处理日志：").pack(anchor="w")

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            width=100,
            height=15,
            font=("微软雅黑", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text.insert(tk.END, "请点击上方按钮选择要分割的TXT文件...\n")
        self.log_text.config(state=tk.DISABLED)

        # 已处理文件区域
        files_frame = ttk.Frame(self.root)
        files_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        ttk.Label(files_frame, text="已处理文件：").pack(anchor="w")

        self.files_frame = ttk.Frame(files_frame)
        self.files_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 底部说明
        footer_label = ttk.Label(
            self.root,
            text="说明：文件将按指定汉字数分割（自动尝试UTF-8/GB2312编码），结尾会附加文案修改要求，结果保存在源文件同目录下的【源文件名（已分割）】文件夹中",
            font=("微软雅黑", 8),
            foreground="#666666"
        )
        footer_label.pack(pady=10, side=tk.BOTTOM)

    def _update_count_label(self, value):
        """更新滑块显示的字数"""
        self.count_label.config(text=f"{int(float(value))} 个汉字")

    def select_files(self):
        """选择多个TXT文件并处理"""
        file_paths = filedialog.askopenfilenames(
            title="选择要分割的TXT文件",
            filetypes=[("TXT文件", "*.txt"), ("所有文件", "*.*")]
        )

        if not file_paths:
            return

        # 清空之前的日志和文件列表
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        # 清空之前的文件按钮
        for widget in self.files_frame.winfo_children():
            widget.destroy()
        self.processed_files = []

        # 禁用选择按钮防止重复操作
        self.select_btn.config(state=tk.DISABLED)
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = len(file_paths)

        # 在新线程中处理文件，避免界面卡顿
        def process_files():
            split_count = self.split_count.get()
            for i, file_path in enumerate(file_paths, 1):
                # 只处理TXT文件
                if file_path.lower().endswith('.txt'):
                    result, output_files = self.split_txt_by_chinese(
                        file_path,
                        split_count=split_count
                    )
                    # 记录处理后的文件路径，用于快捷打开
                    if output_files:
                        self.processed_files.extend(output_files)
                        self.root.after(0, self._update_file_buttons)
                else:
                    result = f"⚠️ 跳过非TXT文件：{os.path.basename(file_path)}\n\n"

                # 更新日志
                self.root.after(0, self._update_log, result)
                # 更新进度条
                self.root.after(0, lambda v=i: setattr(self.progress_bar, "value", v))

            # 处理完成后恢复按钮状态
            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
            self.root.after(0, self._update_log, "🎉 所有文件处理完毕！\n")

        # 启动处理线程
        threading.Thread(target=process_files, daemon=True).start()

    def _update_log(self, text):
        """更新日志区域"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _update_file_buttons(self):
        """更新已处理文件的快捷打开按钮"""
        # 先清空现有按钮
        for widget in self.files_frame.winfo_children():
            widget.destroy()

        # 创建滚动条和框架
        canvas = tk.Canvas(self.files_frame)
        scrollbar = ttk.Scrollbar(
            self.files_frame,
            orient="vertical",
            command=canvas.yview
        )
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # 添加按钮
        for i, file_path in enumerate(self.processed_files):
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, pady=2, padx=2)

            file_name = os.path.basename(file_path)
            ttk.Label(
                frame,
                text=file_name,
                width=60,
                anchor="w"
            ).pack(side=tk.LEFT)

            ttk.Button(
                frame,
                text="打开文件",
                style="TOpenButton.TButton",
                command=lambda path=file_path: self.open_file(path)
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                frame,
                text="打开文件夹",
                style="TOpenButton.TButton",
                command=lambda path=os.path.dirname(file_path): self.open_folder(path)
            ).pack(side=tk.LEFT)

        # 放置滚动条和画布
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def open_file(self, file_path):
        """打开指定文件"""
        try:
            if os.name == 'nt':  # Windows系统
                os.startfile(file_path)
            else:  # macOS或Linux
                webbrowser.open(file_path)
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开文件：{str(e)}")

    def open_folder(self, folder_path):
        """打开文件所在文件夹"""
        try:
            if os.name == 'nt':  # Windows系统
                os.startfile(folder_path)
            elif os.name == 'posix':  # macOS或Linux
                webbrowser.open(f"file://{folder_path}")
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开文件夹：{str(e)}")

    @staticmethod
    def is_chinese(char):
        """判断一个字符是否为汉字"""
        return '\u4e00' <= char <= '\u9fff'

    def split_txt_by_chinese(self, source_path, split_count=5000):
        """
        按指定汉字数分割txt文件，自动尝试UTF-8和GB2312编码，确保以句号结尾，
        并在每个分割文件末尾添加文案修改要求
        """
        try:
            # 解析源文件路径和名称
            dir_name = os.path.dirname(source_path)
            file_name = os.path.basename(source_path)
            name_without_ext, ext = os.path.splitext(file_name)

            # 创建保存分割文件的文件夹
            output_dir = os.path.join(dir_name, f"{name_without_ext}（已分割）")
            os.makedirs(output_dir, exist_ok=True)

            # 读取源文件内容（自动尝试编码）
            content = None
            used_encoding = None
            encodings_to_try = ['utf-8', 'gb2312']

            for encoding in encodings_to_try:
                try:
                    with open(source_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    return f"❌ 错误：读取{file_name}时发生异常 - {str(e)}\n", []

            if content is None:
                return (f"❌ 错误：{file_name} 无法用以下编码读取：{', '.join(encodings_to_try)}\n"
                        f"       请检查文件编码格式是否正确\n", [])

            total_length = len(content)
            if total_length == 0:
                return f"⚠️ 警告：{file_name} 内容为空，无需分割（使用编码：{used_encoding}）\n", []

            start = 0
            chinese_count = 0
            part = 1
            result_msg = [f"✅ 开始处理：{file_name}（总长度：{total_length}字符，使用编码：{used_encoding}）"]
            output_files = []

            for i, char in enumerate(content):
                if self.is_chinese(char):
                    chinese_count += 1

                if chinese_count >= split_count:
                    # 寻找最近的句号作为分割点
                    split_pos = i
                    for j in range(i, max(start, i - 100), -1):
                        if content[j] in ('。', '.'):
                            split_pos = j
                            break

                    # 截取内容并添加修改要求
                    part_content = content[start:split_pos + 1] + self.append_text
                    new_file_name = f"{name_without_ext}（已分割）_{part}{ext}"
                    new_file_path = os.path.join(output_dir, new_file_name)

                    with open(new_file_path, 'w', encoding=used_encoding) as f:
                        f.write(part_content)

                    actual_chinese = sum(1 for c in content[start:split_pos + 1] if self.is_chinese(c))
                    result_msg.append(f"  生成：{new_file_name}（汉字数：{actual_chinese}）")
                    output_files.append(new_file_path)

                    start = split_pos + 1
                    chinese_count = 0
                    part += 1

            # 处理剩余内容并添加修改要求
            if start < total_length:
                part_content = content[start:] + self.append_text
                new_file_name = f"{name_without_ext}（已分割）_{part}{ext}"
                new_file_path = os.path.join(output_dir, new_file_name)

                with open(new_file_path, 'w', encoding=used_encoding) as f:
                    f.write(part_content)

                actual_chinese = sum(1 for c in content[start:] if self.is_chinese(c))
                result_msg.append(f"  生成：{new_file_name}（汉字数：{actual_chinese}）")
                output_files.append(new_file_path)

            result_msg.append(f"  处理完成，共生成 {part} 个文件，保存至：\n  {output_dir}\n")
            return '\n'.join(result_msg) + '\n', output_files

        except Exception as e:
            return f"❌ 处理{os.path.basename(source_path)}时发生错误：{str(e)}\n", []


if __name__ == "__main__":
    root = tk.Tk()
    app = TxtSplitterApp(root)
    root.mainloop()