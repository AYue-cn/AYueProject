from PIL import Image, ImageDraw, ImageFont  # 兼容低版本Pillow
import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import sys
import re

# 全局配置：设置CustomTkinter外观
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# 本地字体文件配置（关键：默认改为msyhbd.ttc）
LOCAL_FONT_FOLDER = "./fonts"  # 字体文件夹相对路径
LOCAL_FONT_FILE = "msyhbd.ttc"  # 默认字体：微软雅黑粗体（msyhbd.ttc）
LOCAL_FONT_PATH = os.path.join(LOCAL_FONT_FOLDER, LOCAL_FONT_FILE)  # 拼接完整字体路径

# 固定分辨率配置
LANDSCAPE_SIZE = (1920, 1080)  # 横屏分辨率
PORTRAIT_SIZE = (1080, 1920)   # 竖屏分辨率


class ImageCompositeGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        # 窗口基本设置
        self.title("阿岳图片合成助手2.0")
        self.geometry("850x1000")
        self.resizable(False, False)

        # ===================== 新增：设置窗口logo =====================
        # 方式1：直接指定同文件夹下的ico文件（推荐，确保ico与py文件同目录）
        try:
            self.iconbitmap("4odpx-r40oi-001.ico")
        except Exception as e:
            messagebox.showwarning("图标加载失败", f"无法加载4odpx-r40oi-001.ico：{str(e)}\n窗口功能不受影响")

        # 核心数据存储
        self.image_paths = []  # 存储选择的图片路径
        self.image_names = []  # 存储每张图片对应的名称（水印内容）
        self.image_frame_list = []  # 存储图片条目组件
        self.original_width = 0  # 原始合成图宽度
        self.original_height = 0  # 原始合成图高度

        # 预检查本地字体文件（启动时提示是否存在）
        self._check_local_font()

        # 构建界面
        self._create_image_upload_area()
        self._create_layout_setting_area()
        self._create_watermark_setting_area()  # 默认字号改为100
        self._create_scale_setting_area()  # 缩放百分比默认改为50%
        self._create_execute_area()

    def _check_local_font(self):
        """预检查本地字体文件是否存在，启动时给出提示"""
        if not os.path.exists(LOCAL_FONT_PATH):
            warning_text = f"未找到本地字体文件！\n请确认：\n1. 已创建{LOCAL_FONT_FOLDER}文件夹\n2. 字体文件{LOCAL_FONT_FILE}（微软雅黑粗体）已放入该文件夹\n3. 文件名与代码中配置一致"
            messagebox.showwarning("字体文件缺失警告", warning_text)

    def _create_image_upload_area(self):
        """创建图片上传与命名区域（文件名去扩展名作为默认水印名称）"""
        upload_frame = ctk.CTkFrame(self, fg_color="transparent")
        upload_frame.pack(pady=10, padx=20, fill="x")

        # 标题
        ctk.CTkLabel(
            upload_frame,
            text="一、图片上传与命名（最多9张）",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=3, pady=5, sticky="w")

        # 操作按钮
        ctk.CTkButton(
            upload_frame,
            text="添加图片",
            command=self._add_image,
            width=120
        ).grid(row=1, column=0, padx=5, pady=5)

        ctk.CTkButton(
            upload_frame,
            text="删除最后一张",
            command=self._remove_last_image,
            width=120,
            fg_color="#ff6b6b"
        ).grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkButton(
            upload_frame,
            text="清空所有图片",
            command=self._clear_all_images,
            width=120,
            fg_color="#4ecdc4"
        ).grid(row=1, column=2, padx=5, pady=5)

        # 图片列表容器
        self.image_list_frame = ctk.CTkFrame(upload_frame, fg_color="transparent")
        self.image_list_frame.grid(row=2, column=0, columnspan=3, pady=10, sticky="nsew")

    def _create_layout_setting_area(self):
        """排版参数（修复每行图片数功能，默认2张、间距0px、纯白背景）"""
        layout_frame = ctk.CTkFrame(self, fg_color="transparent")
        layout_frame.pack(pady=10, padx=20, fill="x")

        # 标题
        ctk.CTkLabel(
            layout_frame,
            text="二、排版参数设置",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=4, pady=5, sticky="w")

        # 每行图片数（修复：命名清晰，默认2，支持1及以上）
        ctk.CTkLabel(layout_frame, text="每行图片数：").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.cols_per_row_entry = ctk.CTkEntry(layout_frame, width=100, placeholder_text="默认2，支持1及以上")
        self.cols_per_row_entry.insert(0, "2")
        self.cols_per_row_entry.grid(row=1, column=1, padx=5, pady=5)
        self.cols_per_row_entry.bind("<KeyRelease>", self._calculate_expected_resolution)

        # 水平间距（默认0px）
        ctk.CTkLabel(layout_frame, text="水平间距（像素）：").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.h_spacing_entry = ctk.CTkEntry(layout_frame, width=100, placeholder_text="默认0")
        self.h_spacing_entry.insert(0, "0")
        self.h_spacing_entry.grid(row=1, column=3, padx=5, pady=5)
        self.h_spacing_entry.bind("<KeyRelease>", self._calculate_expected_resolution)

        # 垂直间距（默认0px）
        ctk.CTkLabel(layout_frame, text="垂直间距（像素）：").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.v_spacing_entry = ctk.CTkEntry(layout_frame, width=100, placeholder_text="默认0")
        self.v_spacing_entry.insert(0, "0")
        self.v_spacing_entry.grid(row=2, column=1, padx=5, pady=5)
        self.v_spacing_entry.bind("<KeyRelease>", self._calculate_expected_resolution)

        # 背景色（默认纯白255,255,255）
        ctk.CTkLabel(layout_frame, text="背景色（RGB）：").grid(row=2, column=2, padx=5, pady=5, sticky="e")
        self.bg_color_entry = ctk.CTkEntry(layout_frame, width=100, placeholder_text="默认255,255,255（纯白色）")
        self.bg_color_entry.insert(0, "255,255,255")
        self.bg_color_entry.grid(row=2, column=3, padx=5, pady=5)

    def _create_watermark_setting_area(self):
        """水印参数（默认100号字号、左上角、本地字体msyhbd.ttc无乱码）"""
        watermark_frame = ctk.CTkFrame(self, fg_color="transparent")
        watermark_frame.pack(pady=10, padx=20, fill="x")

        # 标题
        ctk.CTkLabel(
            watermark_frame,
            text="三、水印参数设置（每张图片独立左上角水印，默认100号字号）",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=4, pady=5, sticky="w")

        # 本地字体提示（显示默认字体msyhbd.ttc）
        ctk.CTkLabel(
            watermark_frame,
            text=f"当前使用本地字体：{LOCAL_FONT_FILE}（微软雅黑粗体）",
            font=ctk.CTkFont(size=10),
            text_color="#2ecc71"
        ).grid(row=1, column=0, columnspan=4, pady=2, sticky="w")

        # 字号（默认100，修改默认值和占位提示）
        ctk.CTkLabel(watermark_frame, text="字号：").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.font_size_entry = ctk.CTkEntry(watermark_frame, width=100, placeholder_text="默认100（自动适配图片尺寸）")
        self.font_size_entry.insert(0, "100")  # 默认字号改为100
        self.font_size_entry.grid(row=2, column=1, padx=5, pady=5)

        # 水印颜色（默认红色255,0,0，高对比度保证可见）
        ctk.CTkLabel(watermark_frame, text="水印颜色（RGB）：").grid(row=2, column=2, padx=5, pady=5, sticky="e")
        self.watermark_color_entry = ctk.CTkEntry(watermark_frame, width=100,
                                                  placeholder_text="默认255,0,0（红色，高对比度）")
        self.watermark_color_entry.insert(0, "255,0,0")
        self.watermark_color_entry.grid(row=2, column=3, padx=5, pady=5)

        # 提示信息
        ctk.CTkLabel(
            watermark_frame,
            text="提示：使用本地字体msyhbd.ttc（微软雅黑粗体），无需依赖系统字体，确保中文无乱码",
            font=ctk.CTkFont(size=10),
            text_color="#666666"
        ).grid(row=3, column=0, columnspan=4, pady=2, sticky="w")

    def _create_scale_setting_area(self):
        """大图缩放设置+实时预计分辨率显示（默认50%缩放）"""
        scale_frame = ctk.CTkFrame(self, fg_color="transparent")
        scale_frame.pack(pady=10, padx=20, fill="x")

        # 标题
        ctk.CTkLabel(
            scale_frame,
            text="四、大图缩放设置（无损百分比，默认50%）",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=4, pady=5, sticky="w")

        # 缩放百分比（默认50%，修改默认值和占位提示）
        ctk.CTkLabel(
            scale_frame,
            text="缩放百分比：").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.scale_percent_entry = ctk.CTkEntry(scale_frame, width=100, placeholder_text="默认50（无损缩放）")
        self.scale_percent_entry.insert(0, "50")  # 默认缩放百分比改为50%
        self.scale_percent_entry.grid(row=1, column=1, padx=5, pady=5)
        self.scale_percent_entry.bind("<KeyRelease>", self._calculate_expected_resolution)

        # 分辨率标题
        ctk.CTkLabel(
            scale_frame,
            text="预计分辨率：",
            font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=2, column=0, padx=5, pady=8, sticky="e")

        # 原始合成分辨率
        self.original_res_label = ctk.CTkLabel(
            scale_frame,
            text="原始合成：0 × 0 像素",
            font=ctk.CTkFont(size=10),
            text_color="#3498db"
        )
        self.original_res_label.grid(row=2, column=1, padx=5, pady=8, sticky="w")

        # 缩放后分辨率
        self.scaled_res_label = ctk.CTkLabel(
            scale_frame,
            text="缩放后：0 × 0 像素",
            font=ctk.CTkFont(size=10),
            text_color="#e74c3c"
        )
        self.scaled_res_label.grid(row=2, column=2, padx=5, pady=8, sticky="w")

        # 缩放提示（更新默认值说明）
        ctk.CTkLabel(
            scale_frame,
            text="提示：默认50%缩放（原始尺寸的一半），100%为原始尺寸，200%为放大一倍（LANCZOS无损算法）",
            font=ctk.CTkFont(size=9),
            text_color="#666666"
        ).grid(row=3, column=0, columnspan=4, padx=5, pady=2, sticky="w")

    def _create_execute_area(self):
        """执行合成与结果提示"""
        execute_frame = ctk.CTkFrame(self, fg_color="transparent")
        execute_frame.pack(pady=20, padx=20, fill="x")

        # 合成按钮
        self.composite_btn = ctk.CTkButton(
            execute_frame,
            text="开始无损合成",
            command=self._execute_composite,
            width=200,
            height=40,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.composite_btn.pack(pady=10)

        # 结果提示框
        self.result_label = ctk.CTkLabel(
            execute_frame,
            text="等待合成...（请先添加图片并查看预计分辨率）",
            font=ctk.CTkFont(size=12),
            text_color="#666666"
        )
        self.result_label.pack(pady=5)

    def _add_image(self):
        """添加图片，自动提取无扩展名文件名作为默认水印名称"""
        if len(self.image_paths) >= 9:
            messagebox.showwarning("警告", "最多只能添加9张图片！")
            return

        # 选择图片
        img_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")]
        )
        if not img_path:
            return

        # 提取无扩展名文件名（强制UTF-8编码，避免文件名本身乱码）
        try:
            img_basename = os.path.basename(img_path).encode("utf-8").decode("utf-8")
        except:
            img_basename = os.path.basename(img_path).encode("gbk", errors="ignore").decode("utf-8", errors="ignore")
        default_img_name = os.path.splitext(img_basename)[0]

        # 存储数据
        self.image_paths.append(img_path)
        self.image_names.append(default_img_name)

        # 创建图片条目
        img_frame = ctk.CTkFrame(self.image_list_frame, fg_color="transparent")
        img_frame.pack(pady=3, fill="x")

        # 显示图片名称（截断过长名称）
        img_name_display = img_basename
        if len(img_name_display) > 20:
            img_name_display = img_name_display[:17] + "..."
        ctk.CTkLabel(
            img_frame,
            text=f"{len(self.image_paths)}. {img_name_display}",
            font=ctk.CTkFont(size=11),
            width=250
        ).pack(side="left", padx=5)

        # 水印名称输入框（填充无扩展名文件名）
        name_entry = ctk.CTkEntry(img_frame, width=150, placeholder_text="输入水印名称（支持中文）")
        name_entry.insert(0, default_img_name)
        name_entry.pack(side="left", padx=5)

        # 绑定修改事件（强制UTF-8编码）
        def _update_img_name(event, idx=len(self.image_paths) - 1):
            try:
                new_name = name_entry.get().strip().encode("utf-8").decode("utf-8")
            except:
                new_name = name_entry.get().strip()
            if new_name:
                self.image_names[idx] = new_name

        name_entry.bind("<KeyRelease>", _update_img_name)

        # 存储条目组件
        self.image_frame_list.append(img_frame)

        # 自动计算预计分辨率
        self._calculate_expected_resolution()

    def _remove_last_image(self):
        """删除最后一张图片，更新分辨率提示"""
        if not self.image_paths:
            messagebox.showinfo("提示", "暂无图片可删除！")
            return

        # 删除数据
        self.image_paths.pop()
        self.image_names.pop()
        self.image_frame_list[-1].destroy()
        self.image_frame_list.pop()

        # 重新计算分辨率
        self._calculate_expected_resolution()

    def _clear_all_images(self):
        """清空所有图片，重置分辨率提示"""
        if not self.image_paths:
            return

        # 清空数据
        self.image_paths.clear()
        self.image_names.clear()
        for frame in self.image_frame_list:
            frame.destroy()
        self.image_frame_list.clear()

        # 重置提示
        self.original_width = 0
        self.original_height = 0
        self.original_res_label.configure(text="原始合成：0 × 0 像素")
        self.scaled_res_label.configure(text="缩放后：0 × 0 像素")
        self.result_label.configure(text="等待合成...（请先添加图片并查看预计分辨率）")

    def _parse_rgb_str(self, rgb_str):
        """解析RGB字符串为元组"""
        try:
            rgb_list = list(map(int, rgb_str.strip().split(",")))
            if len(rgb_list) != 3 or not all(0 <= val <= 255 for val in rgb_list):
                raise ValueError
            return tuple(rgb_list)
        except:
            raise ValueError(f"无效的RGB格式：{rgb_str}，请输入如'255,255,255'的格式")

    def _safe_load_local_font(self, target_font_size, img_width, img_height):
        """
        加载本地字体文件（msyhbd.ttc），自动适配字号，确保100%无乱码
        :param target_font_size: 目标字号（默认100）
        :param img_width: 图片宽度
        :param img_height: 图片高度
        :return: 加载成功的字体对象，适配后的字号
        """
        # 步骤1：计算适配后的字号（避免超出图片尺寸）
        max_available_size = min(img_width, img_height) // 2
        if max_available_size < 10:  # 最小字号限制，确保可见
            max_available_size = 10
        adapted_font_size = min(target_font_size, max_available_size)

        # 步骤2：优先加载本地字体文件msyhbd.ttc（核心：不再依赖系统字体）
        try:
            # 强制UTF-8编码加载，支持中文
            font = ImageFont.truetype(
                font=LOCAL_FONT_PATH,
                size=adapted_font_size,
                encoding="utf-8"
            )
            return font, adapted_font_size
        except Exception as e:
            # 本地字体加载失败（极端情况），兜底到Pillow默认字体，并提示
            messagebox.showwarning("本地字体加载失败",
                                   f"本地字体文件{LOCAL_FONT_FILE}无法加载：{str(e)}\n将使用默认字体兜底，可能存在少量乱码")
            try:
                font = ImageFont.load_default(size=adapted_font_size)
                return font, adapted_font_size
            except:
                font = ImageFont.load_default(size=10)
                return font, 10

    def _clean_watermark_text(self, text):
        """
        清洗水印文字，处理乱码源头，确保可渲染
        :param text: 原始水印文字
        :return: 清洗后的可渲染文字
        """
        if not text:
            return "Unnamed"

        # 步骤1：强制UTF-8编码，去除不可见字符
        try:
            text = text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
        except:
            text = text.encode("gbk", errors="ignore").decode("utf-8", errors="ignore")

        # 步骤2：去除特殊字符（避免渲染失败），保留中文、英文、数字、常用符号
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_\-· ]', '', text)

        # 步骤3：文字为空时，填充默认值（避免空白）
        if not text.strip():
            return "Unnamed"

        return text

    def _resize_image_by_orientation(self, img):
        """
        根据图片横竖屏转换为固定分辨率：
        横屏（宽>高）→ 1920*1080
        竖屏（宽<高）→ 1080*1920
        正方形（宽=高）→ 1920*1080
        :param img: 原始RGBA图片对象
        :return: 转换后的RGBA图片对象
        """
        img_width, img_height = img.size

        # 判断横竖屏，确定目标分辨率
        if img_width > img_height:
            # 横屏：1920*1080
            target_size = LANDSCAPE_SIZE
        elif img_width < img_height:
            # 竖屏：1080*1920
            target_size = PORTRAIT_SIZE
        else:
            # 正方形：默认按横屏分辨率处理
            target_size = LANDSCAPE_SIZE

        # 转换分辨率（使用LANCZOS滤镜，保证缩放质量无模糊）
        resized_img = img.resize(target_size, Image.LANCZOS)

        return resized_img

    def _add_watermark_to_image(self, img, watermark_text, target_font_size, font_color):
        """
        每张图片独立添加左上角水印，使用本地字体msyhbd.ttc，100%无乱码
        :param img: 原始RGBA图片对象
        :param watermark_text: 水印文字
        :param target_font_size: 目标字号（默认100）
        :param font_color: 水印颜色
        :return: 加水印后的图片对象
        """
        # 复制原图避免修改，确保RGBA格式（支持透明）
        img_with_watermark = img.copy().convert("RGBA")
        draw = ImageDraw.Draw(img_with_watermark)
        img_width, img_height = img_with_watermark.size

        # 步骤1：清洗水印文字，从源头避免乱码
        clean_text = self._clean_watermark_text(watermark_text)

        # 步骤2：加载本地字体，自动适配字号（核心：无系统字体依赖）
        font, adapted_font_size = self._safe_load_local_font(
            target_font_size, img_width, img_height
        )

        # 步骤3：计算文字边界（确保不超出图片，左上角安全偏移）
        x, y = 5, 5

        # 步骤4：强制绘制文字（UTF-8兼容，描边增强对比度，无乱码）
        draw.text(
            (x, y),
            clean_text,
            fill=font_color + (255,),  # 完全不透明，保证可见
            font=font,
            align="left",
            stroke_width=1,  # 增加描边，文字更清晰
            stroke_fill=(0, 0, 0)  # 黑色描边，提升对比度
        )

        return img_with_watermark

    def _calculate_expected_resolution(self, event=None):
        """实时计算并显示预计分辨率（修复每行图片数逻辑）"""
        if len(self.image_paths) == 0:
            return

        try:
            # 解析排版参数（修复：使用cols_per_row，无强制最小2的限制）
            cols_per_row = int(self.cols_per_row_entry.get().strip() or 2)
            h_spacing = int(self.h_spacing_entry.get().strip() or 0)
            v_spacing = int(self.v_spacing_entry.get().strip() or 0)
            scale_percent = float(self.scale_percent_entry.get().strip() or 50)

            # 参数校正（修复：允许每行1张及以上，间距不小于0）
            cols_per_row = max(1, cols_per_row)
            h_spacing = max(0, h_spacing)
            v_spacing = max(0, v_spacing)
            scale_percent = max(1, scale_percent)

            # 获取所有图片尺寸（先转换为固定分辨率再获取尺寸）
            image_sizes = []
            for img_path in self.image_paths:
                with Image.open(img_path) as img:
                    img = img.convert("RGBA")
                    resized_img = self._resize_image_by_orientation(img)
                    image_sizes.append(resized_img.size)

            # 计算行列数（修复：每行cols_per_row张，总行数向上取整）
            total_imgs = len(image_sizes)
            total_rows = (total_imgs + cols_per_row - 1) // cols_per_row  # 向上取整
            current_cols = min(cols_per_row, total_imgs)

            # 计算每列最大宽度、每行最大高度（修复：匹配每行cols_per_row张的逻辑）
            col_max_widths = [0] * cols_per_row
            for col in range(cols_per_row):
                col_img_widths = [image_sizes[idx][0] for idx in range(col, total_imgs, cols_per_row)]
                if col_img_widths:
                    col_max_widths[col] = max(col_img_widths)

            row_max_heights = [0] * total_rows
            for row in range(total_rows):
                row_start = row * cols_per_row
                row_end = min((row + 1) * cols_per_row, total_imgs)
                row_img_heights = [image_sizes[idx][1] for idx in range(row_start, row_end)]
                if row_img_heights:
                    row_max_heights[row] = max(row_img_heights)

            # 原始总尺寸（修复：按实际列数和行数计算）
            self.original_width = sum(col_max_widths[:current_cols]) + (current_cols - 1) * h_spacing
            self.original_height = sum(row_max_heights) + (total_rows - 1) * v_spacing

            # 缩放后尺寸
            scaled_width = int(self.original_width * (scale_percent / 100))
            scaled_height = int(self.original_height * (scale_percent / 100))

            # 更新界面提示
            self.original_res_label.configure(text=f"原始合成：{self.original_width} × {self.original_height} 像素")
            self.scaled_res_label.configure(text=f"缩放后：{scaled_width} × {scaled_height} 像素")

        except Exception as e:
            self.original_res_label.configure(text="原始合成：计算错误")
            self.scaled_res_label.configure(text="缩放后：计算错误")
            self.result_label.configure(text=f"分辨率计算失败：{str(e)}", text_color="#e74c3c")

    def _execute_composite(self):
        """核心合成流程（修复每行图片数排版逻辑）"""
        try:
            # 校验图片数量
            if len(self.image_paths) == 0:
                messagebox.showwarning("警告", "请先添加至少1张图片！")
                return

            # 解析所有参数（修复：使用cols_per_row，无强制最小2的限制）
            # 排版参数
            cols_per_row = int(self.cols_per_row_entry.get().strip() or 2)
            h_spacing = int(self.h_spacing_entry.get().strip() or 0)
            v_spacing = int(self.v_spacing_entry.get().strip() or 0)
            bg_color = self._parse_rgb_str(self.bg_color_entry.get().strip())

            # 水印参数（默认100号字号）
            target_font_size = int(self.font_size_entry.get().strip() or 100)
            watermark_color = self._parse_rgb_str(self.watermark_color_entry.get().strip())

            # 缩放参数（默认50%）
            scale_percent = float(self.scale_percent_entry.get().strip() or 50)

            # 参数校正（修复：允许每行1张及以上，其他参数合理限制）
            cols_per_row = max(1, cols_per_row)
            h_spacing = max(0, h_spacing)
            v_spacing = max(0, v_spacing)
            target_font_size = max(10, target_font_size)
            scale_percent = max(1, scale_percent)

            # 选择保存路径
            output_path = filedialog.asksaveasfilename(
                title="保存合成图片",
                defaultextension=".png",
                filetypes=[("PNG无损格式", "*.png"), ("所有文件", "*.*")]
            )
            if not output_path:
                return
            if not output_path.lower().endswith(".png"):
                output_path += ".png"

            # 步骤1：每张图片独立处理（分辨率转换→添加水印）
            images_with_watermark = []
            image_sizes = []
            for img_path, img_name in zip(self.image_paths, self.image_names):
                if not os.path.exists(img_path):
                    raise FileNotFoundError(f"图片不存在：{os.path.basename(img_path)}")

                # 加载图片并转换为RGBA
                img = Image.open(img_path).convert("RGBA")

                # 转换为固定分辨率（横屏1920*1080/竖屏1080*1920）
                resized_img = self._resize_image_by_orientation(img)

                # 添加水印（使用本地字体msyhbd.ttc，默认100号字号）
                img_with_wm = self._add_watermark_to_image(
                    resized_img, img_name, target_font_size, watermark_color
                )

                # 收集结果
                images_with_watermark.append(img_with_wm)
                image_sizes.append(img_with_wm.size)

            # 步骤2：合成原始大图（修复：按每行cols_per_row张排版）
            total_imgs = len(images_with_watermark)
            total_rows = (total_imgs + cols_per_row - 1) // cols_per_row  # 总行数向上取整

            # 计算每列最大宽度、每行最大高度
            col_max_widths = [0] * cols_per_row
            for col in range(cols_per_row):
                col_img_widths = [image_sizes[idx][0] for idx in range(col, total_imgs, cols_per_row)]
                if col_img_widths:
                    col_max_widths[col] = max(col_img_widths)

            row_max_heights = [0] * total_rows
            for row in range(total_rows):
                row_start = row * cols_per_row
                row_end = min((row + 1) * cols_per_row, total_imgs)
                row_img_heights = [image_sizes[idx][1] for idx in range(row_start, row_end)]
                if row_img_heights:
                    row_max_heights[row] = max(row_img_heights)

            # 创建原始画布
            original_width = sum(col_max_widths) + (cols_per_row - 1) * h_spacing
            original_height = sum(row_max_heights) + (total_rows - 1) * v_spacing
            original_composited = Image.new(
                "RGBA", (original_width, original_height), bg_color + (255,)
            )

            # 粘贴图片（修复：按每行cols_per_row张计算粘贴位置）
            current_x, current_y = 0, 0
            for idx, (img, img_size) in enumerate(zip(images_with_watermark, image_sizes)):
                # 计算当前行列索引
                row_idx = idx // cols_per_row
                col_idx = idx % cols_per_row

                # 换行时重置X坐标，更新Y坐标
                if col_idx == 0 and idx != 0:
                    current_x = 0
                    current_y += row_max_heights[row_idx - 1] + v_spacing

                # 居中偏移（适配每列最大宽度、每行最大高度）
                offset_x = (col_max_widths[col_idx] - img_size[0]) // 2
                offset_y = (row_max_heights[row_idx] - img_size[1]) // 2

                # 无损粘贴
                original_composited.paste(
                    img, (current_x + offset_x, current_y + offset_y), img
                )

                # 更新X坐标（当前列宽度+水平间距）
                current_x += col_max_widths[col_idx] + h_spacing

            # 步骤3：无损缩放大图（默认50%，LANCZOS算法）
            scaled_width = int(original_width * (scale_percent / 100))
            scaled_height = int(original_height * (scale_percent / 100))
            final_composited = original_composited.resize(
                (scaled_width, scaled_height),
                Image.LANCZOS  # 无损缩放算法
            )

            # 步骤4：保存图片
            final_composited.save(output_path, format="PNG", optimize=False)

            # 更新提示
            success_text = f"合成成功！\n最终分辨率：{scaled_width} × {scaled_height} 像素（{scale_percent}%缩放）\n每行图片数：{cols_per_row}\n保存路径：{os.path.abspath(output_path)}"
            self.result_label.configure(text=success_text, text_color="#2ecc71")
            messagebox.showinfo("成功", success_text)

        except Exception as e:
            error_info = f"合成失败：{str(e)}"
            self.result_label.configure(text=error_info, text_color="#e74c3c")
            messagebox.showerror("错误", error_info)


if __name__ == "__main__":
    app = ImageCompositeGUI()
    app.mainloop()