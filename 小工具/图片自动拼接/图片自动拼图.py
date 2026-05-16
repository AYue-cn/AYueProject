import os
from PIL import Image
import sys
import math


def calculate_best_grid(image_count, orientation='portrait'):
    """
    自动计算最佳行列数，采用"竖屏+最接近正方形"双重优先逻辑
    - portrait: 竖屏优先（行数≥列数），且行列差值最小
    - landscape: 横屏优先（列数≥行数），且行列差值最小
    - square: 最接近正方形，不限制横竖
    """
    if image_count == 0:
        return 0, 0

    if image_count == 1:
        return 1, 1

    best_rows, best_cols = 1, image_count
    min_difference = float('inf')

    # 遍历所有可能的列数，找到最优组合
    max_possible_cols = int(math.ceil(math.sqrt(image_count))) + 1

    for cols in range(1, max_possible_cols + 1):
        rows = (image_count + cols - 1) // cols  # 向上取整计算所需行数

        # 根据方向筛选
        if orientation == 'portrait' and rows < cols:
            continue  # 竖屏模式跳过行数<列数的组合
        if orientation == 'landscape' and cols < rows:
            continue  # 横屏模式跳过列数<行数的组合

        difference = abs(rows - cols)

        # 如果差值更小，更新最佳组合
        if difference < min_difference:
            min_difference = difference
            best_rows, best_cols = rows, cols
        # 如果差值相同，选择列数更多的（更接近正方形）
        elif difference == min_difference and cols > best_cols:
            best_rows, best_cols = rows, cols

    return best_rows, best_cols


def resize_and_pad_image(img, target_width, target_height, background_color=(255, 255, 255)):
    """
    调整图片大小并居中填充，保持原始宽高比，不拉伸变形
    """
    original_width, original_height = img.size
    ratio = min(target_width / original_width, target_height / original_height)

    new_width = int(original_width * ratio)
    new_height = int(original_height * ratio)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    new_img = Image.new('RGB', (target_width, target_height), background_color)

    x_offset = (target_width - new_width) // 2
    y_offset = (target_height - new_height) // 2

    new_img.paste(img, (x_offset, y_offset))

    return new_img


def batch_concatenate_images(folder_path, cell_width=None, cell_height=None,
                             background_color=(255, 255, 255), output_format='jpg',
                             orientation='portrait'):
    """
    批量拼接文件夹内的所有图片

    Args:
        folder_path: 图片文件夹路径
        cell_width: 单个格子的宽度（像素），None则自动计算
        cell_height: 单个格子的高度（像素），None则自动计算
        background_color: 背景填充颜色，默认白色
        output_format: 输出图片格式，支持jpg、png
        orientation: 拼接方向 'portrait'(竖屏)/'landscape'(横屏)/'square'(正方形)
    """
    # 支持的图片格式
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']

    # 获取所有图片文件（按文件名自然排序）
    image_paths = []
    for filename in sorted(os.listdir(folder_path)):
        ext = os.path.splitext(filename)[1].lower()
        if ext in image_extensions and not filename.startswith('new_'):
            image_paths.append(os.path.join(folder_path, filename))

    image_count = len(image_paths)

    if image_count == 0:
        print("错误: 文件夹中没有找到可拼接的图片")
        return

    # 计算最佳行列数
    rows, cols = calculate_best_grid(image_count, orientation)

    print("=" * 60)
    print("智能图片批量拼接工具（竖屏优先修正版）")
    print("=" * 60)
    print(f"目标文件夹: {folder_path}")
    print(f"找到图片: {image_count} 张")
    print(
        f"拼接方向: {'竖屏优先' if orientation == 'portrait' else '横屏优先' if orientation == 'landscape' else '正方形优先'}")
    print(f"拼接方式: {rows}行 × {cols}列")
    print(f"空位数量: {rows * cols - image_count} 个")
    print("=" * 60 + "\n")

    # 自动计算格子尺寸（使用所有图片的平均尺寸）
    if cell_width is None or cell_height is None:
        print("正在自动计算最佳格子尺寸...")
        total_width = 0
        total_height = 0

        for path in image_paths:
            with Image.open(path) as img:
                w, h = img.size
                total_width += w
                total_height += h

        avg_width = int(total_width / image_count)
        avg_height = int(total_height / image_count)

        cell_width = cell_width or avg_width
        cell_height = cell_height or avg_height

        print(f"自动计算格子尺寸: {cell_width}px × {cell_height}px\n")

    # 创建拼接后的大图
    total_width = cols * cell_width
    total_height = rows * cell_height
    result_image = Image.new('RGB', (total_width, total_height), background_color)

    # 逐张拼接图片（从上到下，从左到右）
    for index, image_path in enumerate(image_paths):
        try:
            with Image.open(image_path) as img:
                processed_img = resize_and_pad_image(img, cell_width, cell_height, background_color)

                # 计算在大图中的位置
                row = index // cols
                col = index % cols
                x = col * cell_width
                y = row * cell_height

                result_image.paste(processed_img, (x, y))

                print(f"✓ 已拼接: {os.path.basename(image_path)} ({index + 1}/{image_count})")

        except Exception as e:
            print(f"✗ 处理失败: {os.path.basename(image_path)}")
            print(f"  错误信息: {str(e)}")
            continue

    # 保存结果
    output_filename = f"new_竖屏拼接_{rows}x{cols}.{output_format}"
    output_path = os.path.join(folder_path, output_filename)

    # 处理文件名重复的情况
    counter = 1
    while os.path.exists(output_path):
        output_filename = f"new_竖屏拼接_{rows}x{cols}_{counter}.{output_format}"
        output_path = os.path.join(folder_path, output_filename)
        counter += 1

    # 保存图片
    if output_format.lower() in ['jpg', 'jpeg']:
        result_image.save(output_path, 'JPEG', quality=95, optimize=True)
    else:
        result_image.save(output_path, 'PNG', optimize=True)

    # 输出结果信息
    print("\n" + "=" * 60)
    print("拼接完成！")
    print("=" * 60)
    print(f"输出文件: {output_filename}")
    print(f"图片尺寸: {total_width}px × {total_height}px")
    print(f"文件大小: {os.path.getsize(output_path) / 1024:.2f} KB")
    print("=" * 60)


if __name__ == "__main__":
    # ====================== 配置参数 ======================
    # 要拼接的文件夹路径（可以修改为你的文件夹路径）
    FOLDER_PATH = r"E:\zyc\下载\拍照姿势整理\2026年5月16日\新建文件夹"  # 默认当前目录下的images文件夹

    # 单个格子的尺寸（像素），设为None则自动计算所有图片的平均尺寸
    CELL_WIDTH = None  # 例如: 360
    CELL_HEIGHT = None  # 例如: 480（竖屏建议高度大于宽度）

    # 背景填充颜色（RGB值）
    # 白色: (255,255,255) 黑色: (0,0,0) 灰色: (128,128,128)
    BACKGROUND_COLOR = (255, 255, 255)

    # 输出图片格式，支持'jpg'和'png'
    OUTPUT_FORMAT = 'jpg'

    # 拼接方向
    # 'portrait': 竖屏优先（默认），行数≥列数且最接近正方形
    # 'landscape': 横屏优先，列数≥行数且最接近正方形
    # 'square': 最接近正方形，不限制横竖
    ORIENTATION = 'portrait'
    # ======================================================

    # 检查文件夹是否存在
    if not os.path.exists(FOLDER_PATH):
        print(f"错误: 文件夹不存在 - {FOLDER_PATH}")
        print("请修改脚本中的FOLDER_PATH变量为你的图片文件夹路径")
        sys.exit(1)

    # 开始批量拼接
    batch_concatenate_images(FOLDER_PATH, CELL_WIDTH, CELL_HEIGHT, BACKGROUND_COLOR, OUTPUT_FORMAT, ORIENTATION)