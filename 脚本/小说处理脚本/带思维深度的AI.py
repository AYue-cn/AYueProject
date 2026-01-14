import os
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
import threading
import webbrowser
from volcenginesdkarkruntime import Ark


class TxtSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("智能TXT文件分割与AI处理工具")
        self.root.geometry("1200x900")
        self.root.resizable(True, True)

        # 存储已处理文件路径
        self.processed_files = []

        # AI客户端初始化为None
        self.ai_client = None

        # API密钥变量（用户输入）
        self.api_key_var = tk.StringVar()

        # 管理员密码和对应的API密钥
        self.admin_password = "123456"
        self.admin_api_key = "d93cef80-19e9-4643-888d-05d4da4ec2c1"

        # 思考深度选项
        self.reasoning_levels = ["minimal", "low", "medium", "high"]
        self.selected_reasoning = tk.StringVar(value="medium")

        # 默认AI指令
        self.default_ai_instructions = """为了让小说变成短视频文案，请对以上小说进行全方位修改，严格遵循以下要求：
0.处理后的小说字数不可以低于原文字数的80%。
1.视角转换：将全文所有内容统一调整为主人公第一视角（以 “我” 为叙述主体） ，确保心理活动、动作描写、场景感知均从 “我” 的视角出发，贴合主人公的身份与情感逻辑，删除所有第三人称叙述内容。 
2.纠错润色：修正文中所有错别字、标点错误及语法语病，优化语句通顺度，保持语言风格与主人公人设一致，避免生硬表达。
3.冲突强化：聚焦小说核心情节冲突（需明确冲突核心：如人物矛盾、目标阻碍、情感纠葛等），通过增强 “我” 的心理挣扎、行动困境、对手张力等方式深化冲突，突出情节的紧张感与感染力，确保修改后核心冲突更鲜明、更有层次。
4.数字改写：所有数字改为中文，方便AI进行朗读。
5.为贴合动漫短视频的画面动态感，要在角色对话前补充符合人设的语气、动作描述（如 “大声喝道”“急声劝阻”“紧盯着屏幕报出”），让台词更有场景张力，同时保留第一视角的沉浸感。
6.修正标点符号，仅使用逗号和句号。
7.开头改写，根据整篇小说内容，写一句话的文案开头，风格可以学习如下风格：猎奇，反常识【葬礼当天，我当场从棺材里跳出来】【我爸是金龙，我妈是金龙，而我却是一条青龙】反差，反转【我身为奥特曼，却从不打怪兽，反而一门心思想要毁灭人类】【平时连蚂蚁都不敢踩的我，却在一夜之间宰了十万头牛】反问【高考满分和一千万你选哪个？】【假如给你十个老婆，你能玩出什么花活？】爽点前置【男人为了证明黑狗血可以辟邪，竟用黑狗血在身上纹满了整个地府，左肩阎罗，右键判官，前胸无常，后背马面，地藏孟婆护在腰间】强行带入【杀过人的都知道，毁尸灭迹是很重要的一环，但更重要的却是如何跑路】【睡过棺材的都知道，那里面是又黑又潮，空间还闭塞狭小】擦边【我的青梅竹马是个小色批，从小她就喜欢偷看我洗澡】【我的继姐特别坏，每晚都要搂着我睡，并且还时不时搞一些小动作】。根据小说内容，选取一种风格改写一个开头再最前面，吸引看的人停留。
8.因为后续要进行AI绘画，要避免一些词汇容易让ai误会，例如猫眼本来是门上的观察孔，却被AI画成猫的眼睛，如果有这些易混淆的词汇，请替换成不易混淆的。
请基于以上要求完成修改，保留原文核心设定与人物特质，使修改后的内容逻辑连贯、代入感强。
"""
        # 当前使用的AI指令
        self.current_ai_instructions = self.default_ai_instructions

        # AI指令开关
        self.use_ai_instructions = tk.BooleanVar(value=True)

        # 分割字数变量
        self.split_count = tk.StringVar(value="5000")

        # 界面样式设置
        self.style = ttk.Style()
        self.style.configure("TButton", font=("微软雅黑", 10))
        self.style.configure("TLabel", font=("微软雅黑", 10))
        self.style.configure("TActionButton.TButton", font=("微软雅黑", 9), padding=2)

        self._create_widgets()

    def _get_effective_api_key(self):
        """获取实际使用的API密钥（处理管理员密码逻辑）"""
        user_input = self.api_key_var.get().strip()
        # 如果输入的是管理员密码，则使用管理员API密钥
        if user_input == self.admin_password:
            return self.admin_api_key
        # 否则使用用户输入的密钥
        return user_input

    def _init_ai_client(self):
        """初始化AI客户端（包含管理员密钥逻辑）"""
        effective_key = self._get_effective_api_key()
        if not effective_key:
            self._update_log("⚠️ 请先输入有效的API密钥\n")
            return None

        try:
            return Ark(
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                api_key=effective_key
            )
        except Exception as e:
            self._update_log(f"⚠️ AI客户端初始化失败：{str(e)}\n")
            return None

    def _create_widgets(self):
        # 标题
        title_label = ttk.Label(
            self.root,
            text="智能TXT文件分割与AI处理工具",
            font=("微软雅黑", 14, "bold")
        )
        title_label.pack(pady=10)

        # 配置区域
        config_frame = ttk.LabelFrame(self.root, text="处理配置")
        config_frame.pack(fill=tk.X, padx=20, pady=5, ipady=5)

        # 第一行：API密钥输入
        ttk.Label(config_frame, text="API密钥：").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.api_key_entry = ttk.Entry(
            config_frame,
            textvariable=self.api_key_var,
            width=50,
            show="*"  # 密码模式显示
        )
        self.api_key_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(config_frame, text="（输入API Key或特定授权码）", font=("微软雅黑", 8)).grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )

        # 第二行：分割字数设置
        ttk.Label(config_frame, text="分割字数:").grid(row=1, column=0, padx=10, pady=5, sticky="w")

        # 字数输入框（修改验证逻辑，允许完整输入后再校验范围）
        vcmd = (self.root.register(self._validate_number), '%P')
        self.split_entry = ttk.Entry(
            config_frame,
            textvariable=self.split_count,
            width=10,
            validate="key",
            validatecommand=vcmd
        )
        self.split_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(config_frame, text="个汉字（1000-10000）").grid(row=1, column=2, padx=0, pady=5, sticky="w")

        # 第三行：AI思考深度选择
        ttk.Label(config_frame, text="AI思考深度:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.reasoning_combobox = ttk.Combobox(
            config_frame,
            textvariable=self.selected_reasoning,
            values=self.reasoning_levels,
            state="readonly",
            width=10
        )
        self.reasoning_combobox.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(
            config_frame,
            text="minimal(不思考) | low(低) | medium(中) | high(高)",
            font=("微软雅黑", 8)
        ).grid(row=2, column=2, padx=5, pady=5, sticky="w")

        # 第三行：AI指令开关和编辑按钮
        ttk.Checkbutton(
            config_frame,
            text="启用AI处理指令",
            variable=self.use_ai_instructions
        ).grid(row=2, column=3, padx=20, pady=5, sticky="w")

        self.edit_ai_btn = ttk.Button(
            config_frame,
            text="编辑AI指令",
            command=self.open_ai_instructions_editor
        ).grid(row=2, column=4, padx=10, pady=5, sticky="w")

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
            length=900,
            mode="determinate"
        )
        self.progress_bar.pack(pady=10)

        # 日志区域
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        ttk.Label(log_frame, text="处理日志（含AI处理过程）：").pack(anchor="w")

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            width=110,
            height=10,
            font=("微软雅黑", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log_text.insert(tk.END, "请先输入API密钥，选择AI思考深度，再选择要分割的TXT文件...\n")
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
            text="说明：输入API密钥或授权码以使用AI功能，可通过思考深度控制处理精细度",
            font=("微软雅黑", 8),
            foreground="#666666"
        )
        footer_label.pack(pady=10, side=tk.BOTTOM)

    def open_ai_instructions_editor(self):
        """打开AI指令编辑二级页面"""
        editor_window = tk.Toplevel(self.root)
        editor_window.title("编辑AI处理指令")
        editor_window.geometry("800x800")
        editor_window.resizable(True, True)
        editor_window.transient(self.root)
        editor_window.grab_set()

        ttk.Label(
            editor_window,
            text="AI处理指令编辑（将附加到分割后的文本中）",
            font=("微软雅黑", 12, "bold")
        ).pack(pady=10, padx=20, anchor="w")

        ttk.Label(editor_window, text="指令内容：", font=("微软雅黑", 10)).pack(padx=20, anchor="w")
        self.ai_instructions_text = scrolledtext.ScrolledText(
            editor_window,
            wrap=tk.WORD,
            width=90,
            height=25,
            font=("微软雅黑", 10)
        )
        self.ai_instructions_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.ai_instructions_text.insert(tk.END, self.current_ai_instructions)

        btn_frame = ttk.Frame(editor_window)
        btn_frame.pack(fill=tk.X, padx=20, pady=15)

        ttk.Button(
            btn_frame,
            text="恢复默认指令",
            command=self._restore_default_instructions
        ).pack(side=tk.LEFT, padx=10)

        ttk.Button(
            btn_frame,
            text="取消",
            command=editor_window.destroy
        ).pack(side=tk.RIGHT, padx=10)

        ttk.Button(
            btn_frame,
            text="保存指令",
            command=lambda: self._save_ai_instructions(editor_window)
        ).pack(side=tk.RIGHT, padx=10)

    def _restore_default_instructions(self):
        """恢复默认AI指令"""
        self.ai_instructions_text.delete(1.0, tk.END)
        self.ai_instructions_text.insert(tk.END, self.default_ai_instructions)

    def _save_ai_instructions(self, editor_window):
        """保存修改后的AI指令"""
        new_instructions = self.ai_instructions_text.get(1.0, tk.END).rstrip("\n")
        if not new_instructions.strip():
            messagebox.showwarning("警告", "AI指令不能为空！")
            return

        self.current_ai_instructions = new_instructions
        self._update_log(f"📝 AI指令已更新（{len(new_instructions)}字符）\n")
        editor_window.destroy()

    def _validate_number(self, value):
        """修改验证逻辑：只检查是否为数字或空，不实时限制范围（范围检查在处理时进行）"""
        if not value:  # 允许为空
            return True
        return value.isdigit()  # 只允许输入数字

    def select_files(self):
        """选择多个TXT文件并处理"""
        # 验证API密钥
        effective_key = self._get_effective_api_key()
        if not effective_key:
            messagebox.showwarning("缺少API密钥", "请先输入有效的API密钥或授权码")
            return

        # 初始化AI客户端
        self.ai_client = self._init_ai_client()
        if not self.ai_client:
            messagebox.showerror("AI客户端初始化失败", "无法使用提供的密钥初始化AI客户端")
            return

        file_paths = filedialog.askopenfilenames(
            title="选择要分割的TXT文件",
            filetypes=[("TXT文件", "*.txt"), ("所有文件", "*.*")]
        )

        if not file_paths:
            return

        # 验证分割字数（这里进行范围检查）
        try:
            split_count = int(self.split_count.get())
            if not (1000 <= split_count <= 10000):
                raise ValueError("超出范围")
        except ValueError:
            messagebox.showwarning("输入无效", "分割字数必须是1000-10000之间的整数，将使用默认值5000")
            split_count = 5000
            self.split_count.set("5000")

        # 清空日志和文件列表
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        for widget in self.files_frame.winfo_children():
            widget.destroy()
        self.processed_files = []

        # 禁用按钮防止重复操作
        self.select_btn.config(state=tk.DISABLED)
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = len(file_paths)

        # 处理文件线程
        def process_files():
            for i, file_path in enumerate(file_paths, 1):
                if file_path.lower().endswith('.txt'):
                    result, output_files = self.split_txt_by_chinese(
                        file_path,
                        split_count=split_count
                    )
                    if output_files:
                        self.processed_files.extend(output_files)
                        self.root.after(0, self._update_file_buttons)
                else:
                    result = f"⚠️ 跳过非TXT文件：{os.path.basename(file_path)}\n\n"

                self.root.after(0, self._update_log, result)
                self.root.after(0, lambda v=i: setattr(self.progress_bar, "value", v))

            self.root.after(0, lambda: self.select_btn.config(state=tk.NORMAL))
            self.root.after(0, self._update_log, "🎉 所有文件处理完毕！\n")

        threading.Thread(target=process_files, daemon=True).start()

    def _update_log(self, text):
        """更新日志区域"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _update_file_buttons(self):
        """更新文件列表"""
        for widget in self.files_frame.winfo_children():
            widget.destroy()

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

        # 遍历文件添加操作按钮
        for file_path in self.processed_files:
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
                style="TActionButton.TButton",
                command=lambda path=file_path: self.open_file(path)
            ).pack(side=tk.LEFT, padx=2)

            ttk.Button(
                frame,
                text="打开文件夹",
                style="TActionButton.TButton",
                command=lambda path=os.path.dirname(file_path): self.open_folder(path)
            ).pack(side=tk.LEFT, padx=2)

            if "_AI处理结果" not in file_name:
                ttk.Button(
                    frame,
                    text="AI处理",
                    style="TActionButton.TButton",
                    command=lambda path=file_path: self.process_with_ai(path)
                ).pack(side=tk.LEFT, padx=2)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def open_file(self, file_path):
        """打开文件"""
        try:
            if os.name == 'nt':
                os.startfile(file_path)
            else:
                webbrowser.open(file_path)
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开文件：{str(e)}")

    def open_folder(self, folder_path):
        """打开文件夹"""
        try:
            if os.name == 'nt':
                os.startfile(folder_path)
            elif os.name == 'posix':
                webbrowser.open(f"file://{folder_path}")
        except Exception as e:
            messagebox.showerror("打开失败", f"无法打开文件夹：{str(e)}")

    def process_with_ai(self, file_path):
        """AI处理核心逻辑"""
        # 验证API密钥和客户端
        effective_key = self._get_effective_api_key()
        if not effective_key:
            messagebox.showwarning("缺少API密钥", "请先输入有效的API密钥或授权码")
            return

        if not self.ai_client:
            self.ai_client = self._init_ai_client()
            if not self.ai_client:
                messagebox.showerror("AI客户端错误", "无法初始化AI客户端，请检查密钥")
                return

        # 获取当前选择的思考深度
        reasoning_level = self.selected_reasoning.get()
        if reasoning_level not in self.reasoning_levels:
            reasoning_level = "medium"
            self.selected_reasoning.set("medium")

        # 禁用AI按钮防止重复提交
        for widget in self.files_frame.winfo_children():
            if isinstance(widget, tk.Canvas):
                for child in widget.find_all():
                    item = widget.itemcget(child, "window")
                    if isinstance(item, ttk.Frame):
                        for btn in item.winfo_children():
                            if isinstance(btn, ttk.Button) and btn["text"] == "AI处理":
                                btn.config(state=tk.DISABLED)

        file_name = os.path.basename(file_path)
        self._update_log(f"📤 正在向豆包AI提交文件：{file_name}（思考深度：{reasoning_level}）...\n")

        # AI处理线程
        def ai_process_thread():
            try:
                # 读取文件内容
                content = None
                encodings_to_try = ['utf-8', 'gb2312']
                for encoding in encodings_to_try:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue

                if content is None:
                    self._update_log(f"❌ 无法读取文件 {file_name}，编码不支持\n")
                    return

                self._update_log(f"🤖 豆包AI正在处理（{reasoning_level}模式），请稍候...\n")

                # 调用AI模型（传入思考深度参数）
                completion = self.ai_client.chat.completions.create(
                    model="doubao-seed-1-6-lite-251015",
                    messages=[
                        {"role": "user", "content": content}
                    ],
                    reasoning_effort=reasoning_level,
                    stream=False
                )

                # 提取结果
                ai_result = completion.choices[0].message.content

                # 生成保存路径
                dir_name = os.path.dirname(file_path)
                name_without_ext = os.path.splitext(file_name)[0]
                ai_result_path = os.path.join(dir_name, f"{name_without_ext}_AI处理结果.txt")

                # 保存结果
                with open(ai_result_path, 'w', encoding='utf-8') as f:
                    f.write(ai_result)

                self._update_log(
                    f"✅ AI处理完成（{reasoning_level}模式），结果已保存至：{os.path.basename(ai_result_path)}（UTF-8编码）\n")

                # 更新文件列表
                self.processed_files.append(ai_result_path)
                self.root.after(0, self._update_file_buttons)

            except Exception as e:
                error_msg = f"❌ 豆包AI接口错误：{str(e)}\n"
                if "API key" in str(e):
                    error_msg += "请检查您的API Key或授权码是否有效\n"
                self._update_log(error_msg)
            except Exception as e:
                self._update_log(f"❌ AI处理失败：{str(e)}\n")
            finally:
                # 恢复按钮状态
                self.root.after(0, self._update_file_buttons)

        threading.Thread(target=ai_process_thread, daemon=True).start()

    @staticmethod
    def is_chinese(char):
        """判断是否为汉字"""
        return '\u4e00' <= char <= '\u9fff'

    def split_txt_by_chinese(self, source_path, split_count=5000):
        """文件分割核心逻辑"""
        try:
            dir_name = os.path.dirname(source_path)
            file_name = os.path.basename(source_path)
            name_without_ext, ext = os.path.splitext(file_name)

            output_dir = os.path.join(dir_name, f"{name_without_ext}（已分割）")
            os.makedirs(output_dir, exist_ok=True)

            # 读取源文件
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
                return f"⚠️ 警告：{file_name} 内容为空，无需分割（读取编码：{used_encoding}）\n", []

            start = 0
            chinese_count = 0
            part = 1
            ai_status = "启用" if self.use_ai_instructions.get() else "禁用"
            result_msg = [
                f"✅ 开始处理：{file_name}（总长度：{total_length}字符，读取编码：{used_encoding}，保存编码：UTF-8，AI指令：{ai_status}）"]
            output_files = []

            # 按汉字数分割逻辑
            for i, char in enumerate(content):
                if self.is_chinese(char):
                    chinese_count += 1

                if chinese_count >= split_count:
                    # 寻找最近的句号分割
                    split_pos = i
                    for j in range(i, max(start, i - 100), -1):
                        if content[j] in ('。', '.'):
                            split_pos = j
                            break

                    # 添加AI指令（如果启用）
                    part_content = content[start:split_pos + 1]
                    if self.use_ai_instructions.get():
                        part_content += "\n\n" + self.current_ai_instructions

                    new_file_name = f"{name_without_ext}（已分割）_{part}{ext}"
                    new_file_path = os.path.join(output_dir, new_file_name)

                    # 保存文件
                    with open(new_file_path, 'w', encoding='utf-8') as f:
                        f.write(part_content)

                    actual_chinese = sum(1 for c in content[start:split_pos + 1] if self.is_chinese(c))
                    result_msg.append(f"  生成：{new_file_name}（汉字数：{actual_chinese}）")
                    output_files.append(new_file_path)

                    start = split_pos + 1
                    chinese_count = 0
                    part += 1

            # 处理剩余内容
            if start < total_length:
                part_content = content[start:]
                if self.use_ai_instructions.get():
                    part_content += "\n\n" + self.current_ai_instructions

                new_file_name = f"{name_without_ext}（已分割）_{part}{ext}"
                new_file_path = os.path.join(output_dir, new_file_name)

                with open(new_file_path, 'w', encoding='utf-8') as f:
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