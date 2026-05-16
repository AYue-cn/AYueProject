import os
from PIL import Image
import sys


def compress_image(input_path, output_path, quality=85, max_width=None, max_height=None):
    """
    压缩单张图片

    Args:
        input_path: 原始图片路径
        output_path: 压缩后图片保存路径
        quality: 压缩质量 (1-100)，数值越高质量越好体积越大
        max_width: 最大宽度限制，超过则按比例缩小
        max_height: 最大高度限制，超过则按比例缩小
    """
    try:
        # 打开图片
        with Image.open(input_path) as img:
            # 获取原始尺寸
            original_width, original_height = img.size

            # 计算新尺寸（保持宽高比）
            new_width, new_height = original_width, original_height

            # 如果设置了最大宽度或高度，按比例调整
            if max_width and original_width > max_width:
                ratio = max_width / original_width
                new_width = max_width
                new_height = int(original_height * ratio)

            if max_height and new_height > max_height:
                ratio = max_height / new_height
                new_height = max_height
                new_width = int(new_width * ratio)

            # 调整图片大小
            if (new_width, new_height) != (original_width, original_height):
                # 使用高质量的重采样算法
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 根据文件扩展名选择保存参数
            ext = os.path.splitext(input_path)[1].lower()

            if ext in ['.jpg', '.jpeg']:
                # JPG格式压缩
                img.save(output_path, 'JPEG', quality=quality, optimize=True, progressive=True)
            elif ext == '.png':
                # PNG格式压缩
                # 对于PNG，quality参数控制压缩级别 (1-9)
                png_quality = min(9, max(1, int(quality / 11)))
                img.save(output_path, 'PNG', optimize=True, compress_level=png_quality)
            elif ext == '.gif':
                # GIF格式压缩
                img.save(output_path, 'GIF', optimize=True)
            else:
                # 其他格式尝试通用保存
                img.save(output_path, optimize=True)

            # 计算压缩率
            original_size = os.path.getsize(input_path) / 1024  # KB
            compressed_size = os.path.getsize(output_path) / 1024  # KB
            compression_rate = (1 - compressed_size / original_size) * 100

            print(f"✓ 成功压缩: {os.path.basename(input_path)}")
            print(f"  原始尺寸: {original_width}x{original_height} → {new_width}x{new_height}")
            print(f"  文件大小: {original_size:.2f} KB → {compressed_size:.2f} KB")
            print(f"  压缩率: {compression_rate:.1f}%\n")

            return True

    except Exception as e:
        print(f"✗ 压缩失败: {os.path.basename(input_path)}")
        print(f"  错误信息: {str(e)}\n")
        return False


def batch_compress_images(folder_path, quality=85, max_width=None, max_height=None, recursive=False):
    """
    批量压缩文件夹内的所有图片

    Args:
        folder_path: 文件夹路径
        quality: 压缩质量 (1-100)
        max_width: 最大宽度限制
        max_height: 最大高度限制
        recursive: 是否递归处理子文件夹
    """
    # 支持的图片格式
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']

    # 统计信息
    total_files = 0
    success_files = 0
    total_original_size = 0
    total_compressed_size = 0

    print("=" * 60)
    print("图片批量压缩工具")
    print("=" * 60)
    print(f"目标文件夹: {folder_path}")
    print(f"压缩质量: {quality}")
    if max_width or max_height:
        print(f"尺寸限制: 最大宽度={max_width}px, 最大高度={max_height}px")
    print(f"递归处理: {'是' if recursive else '否'}")
    print("=" * 60 + "\n")

    # 遍历文件夹
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            # 检查文件扩展名
            ext = os.path.splitext(filename)[1].lower()
            if ext not in image_extensions:
                continue

            # 跳过已经是new_开头的文件，避免重复压缩
            if filename.startswith('new_'):
                continue

            input_path = os.path.join(root, filename)
            output_filename = f"new_{filename}"
            output_path = os.path.join(root, output_filename)

            # 跳过已存在的输出文件
            if os.path.exists(output_path):
                print(f"⚠ 跳过已存在: {output_filename}\n")
                continue

            total_files += 1
            original_size = os.path.getsize(input_path) / 1024
            total_original_size += original_size

            # 压缩图片
            if compress_image(input_path, output_path, quality, max_width, max_height):
                success_files += 1
                compressed_size = os.path.getsize(output_path) / 1024
                total_compressed_size += compressed_size

        # 如果不递归，只处理当前文件夹
        if not recursive:
            break

    # 输出统计信息
    print("=" * 60)
    print("压缩完成！")
    print("=" * 60)
    print(f"总共处理: {total_files} 个文件")
    print(f"成功压缩: {success_files} 个文件")
    print(f"失败: {total_files - success_files} 个文件")

    if success_files > 0:
        total_compression_rate = (1 - total_compressed_size / total_original_size) * 100
        print(f"\n总体统计:")
        print(f"原始总大小: {total_original_size:.2f} KB ({total_original_size / 1024:.2f} MB)")
        print(f"压缩后总大小: {total_compressed_size:.2f} KB ({total_compressed_size / 1024:.2f} MB)")
        print(f"总体压缩率: {total_compression_rate:.1f}%")
        print(
            f"节省空间: {total_original_size - total_compressed_size:.2f} KB ({(total_original_size - total_compressed_size) / 1024:.2f} MB)")

    print("=" * 60)


if __name__ == "__main__":
    # ====================== 配置参数 ======================
    # 要压缩的文件夹路径（可以修改为你的文件夹路径）
    FOLDER_PATH = r"D:\zyc\Desktop\2026年5月15日1_导出\5"  # 默认当前目录下的images文件夹

    # 压缩质量 (1-100)
    # 推荐值: 85-90 高质量，75-80 平衡，60-70 高压缩
    QUALITY = 60

    # 最大宽度限制（像素），超过则按比例缩小，设为None表示不限制
    MAX_WIDTH = None  # 例如: 1920

    # 最大高度限制（像素），超过则按比例缩小，设为None表示不限制
    MAX_HEIGHT = None  # 例如: 1080

    # 是否递归处理子文件夹
    RECURSIVE = False
    # ======================================================

    # 检查文件夹是否存在
    if not os.path.exists(FOLDER_PATH):
        print(f"错误: 文件夹不存在 - {FOLDER_PATH}")
        print("请修改脚本中的FOLDER_PATH变量为你的图片文件夹路径")
        sys.exit(1)

    # 开始批量压缩
    batch_compress_images(FOLDER_PATH, QUALITY, MAX_WIDTH, MAX_HEIGHT, RECURSIVE)