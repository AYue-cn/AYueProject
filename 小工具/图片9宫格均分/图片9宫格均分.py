from PIL import Image
import os
import sys


def split_image_to_9grid(image_path, output_dir="九宫格输出"):
    """
    将一张图片平均切割成3×3的九宫格

    Args:
        image_path: 输入图片的路径
        output_dir: 输出图片的文件夹名称
    """
    try:
        # 打开图片
        img = Image.open(image_path)
        width, height = img.size

        # 计算每个格子的尺寸（取整数，保证均分）
        grid_width = width // 3
        grid_height = height // 3

        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 获取文件名（不含扩展名）
        filename = os.path.splitext(os.path.basename(image_path))[0]

        print(f"正在切割图片: {image_path}")
        print(f"原始尺寸: {width}×{height}")
        print(f"每个格子尺寸: {grid_width}×{grid_height}")

        # 切割图片（3行3列）
        count = 0
        for row in range(3):
            for col in range(3):
                # 计算每个格子的坐标
                left = col * grid_width
                top = row * grid_height
                right = left + grid_width
                bottom = top + grid_height

                # 裁剪图片
                grid_img = img.crop((left, top, right, bottom))

                # 保存图片
                output_path = os.path.join(output_dir, f"{filename}_{count + 1}.jpg")
                grid_img.save(output_path, quality=95)

                count += 1
                print(f"✅ 已生成: {output_path}")

        print(f"\n🎉 切割完成！共生成 {count} 张图片")
        print(f"输出目录: {os.path.abspath(output_dir)}")

    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {image_path}")
    except Exception as e:
        print(f"❌ 处理出错: {str(e)}")


if __name__ == "__main__":
    # 使用方法1: 直接修改这里的图片路径
    IMAGE_PATH = "jimeng-2026-04-24-2582.png"  # 替换成你的图片路径

    # 使用方法2: 命令行传参（python 九宫格.py 你的图片.jpg）
    if len(sys.argv) > 1:
        IMAGE_PATH = sys.argv[1]

    if not os.path.exists(IMAGE_PATH):
        print("❌ 请先将脚本中的'你的图片.jpg'替换为实际的图片路径")
        print("或者使用命令行: python 九宫格.py 你的图片路径")
        sys.exit(1)

    split_image_to_9grid(IMAGE_PATH)