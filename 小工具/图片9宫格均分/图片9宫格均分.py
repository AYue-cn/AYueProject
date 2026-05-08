from PIL import Image
import os
import sys


def split_image_to_9grid(image_path):
    """
    处理单张图片：
    1. 在原始文件夹内创建一个与图片同名的子文件夹
    2. 子文件夹内存放 9宫格切片 + 原图备份
    """
    # 获取图片所在文件夹路径 和 文件名（不含后缀）
    img_dir = os.path.dirname(image_path)
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    # 在原始文件夹内，为每张图片创建独立子文件夹
    output_folder = os.path.join(img_dir, file_name)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    try:
        # 打开图片
        img = Image.open(image_path).convert("RGB")  # 统一转RGB防止透明图报错
        width, height = img.size

        # 计算九宫格大小
        gw = width // 3
        gh = height // 3

        print(f"\n正在处理：{image_path}")
        print(f"尺寸：{width}×{height}")

        # 备份原图到子文件夹
        backup_path = os.path.join(output_folder, f"原图_{file_name}.jpg")
        img.save(backup_path, quality=98)
        print(f"✅ 原图已备份：{backup_path}")

        # 开始切九宫格
        count = 0
        for row in range(3):
            for col in range(3):
                left = col * gw
                top = row * gh
                right = left + gw
                bottom = top + gh

                crop_img = img.crop((left, top, right, bottom))
                save_path = os.path.join(output_folder, f"{file_name}_{count + 1}.jpg")
                crop_img.save(save_path, quality=95)
                count += 1

        print(f"✅ 九宫格生成完成：{output_folder}")

    except Exception as e:
        print(f"❌ 处理失败：{str(e)}")


def process_folder(input_folder):
    """
    遍历指定文件夹，处理所有图片
    """
    if not os.path.exists(input_folder):
        print(f"❌ 文件夹不存在：{input_folder}")
        return

    # 支持的图片格式
    img_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
    img_files = [f for f in os.listdir(input_folder) if f.lower().endswith(img_exts)]

    if not img_files:
        print("❌ 文件夹内没有找到图片")
        return

    print(f"📂 共找到 {len(img_files)} 张图片，开始批量处理...")

    for img_file in img_files:
        img_path = os.path.join(input_folder, img_file)
        split_image_to_9grid(img_path)

    print("\n🎉 所有图片处理完成！")


if __name__ == "__main__":
    # ========== 在这里修改你的图片文件夹路径 ==========
    INPUT_FOLDER = r"E:\zyc\下载\拍照姿势整理\2026年5月8日"  # 把你的图片放这个文件夹
    # ==================================================

    if len(sys.argv) > 1:
        INPUT_FOLDER = sys.argv[1]

    process_folder(INPUT_FOLDER)