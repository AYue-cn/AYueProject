from PIL import Image
import os
import sys


def split_image_to_mxn_grid(image_path, cols=3, rows=3):
    """
    处理单张图片：
    1. 在原始文件夹内创建一个与图片同名的子文件夹
    2. 子文件夹内存放 M列×N行 网格切片 + 原图备份
    :param cols: 切分的列数 (宽度方向切几块)
    :param rows: 切分的行数 (高度方向切几块)
    """
    # 校验参数
    if not isinstance(cols, int) or cols < 1 or not isinstance(rows, int) or rows < 1:
        print(f"❌ 列数和行数必须是正整数，当前输入：列={cols}, 行={rows}")
        return

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

        # 计算单块大小
        gw = width // cols  # 每块宽度
        gh = height // rows # 每块高度

        print(f"\n正在处理：{image_path}")
        print(f"原图尺寸：{width}×{height} | 切分网格：{cols}列 × {rows}行")

        # 备份原图到子文件夹
        backup_path = os.path.join(output_folder, f"原图_{file_name}.jpg")
        img.save(backup_path, quality=98)
        print(f"✅ 原图已备份：{backup_path}")

        # 开始切图
        count = 0
        for r in range(rows):
            for c in range(cols):
                left = c * gw
                top = r * gh
                right = left + gw
                bottom = top + gh

                crop_img = img.crop((left, top, right, bottom))
                save_path = os.path.join(output_folder, f"{file_name}_{count + 1}.jpg")
                crop_img.save(save_path, quality=95)
                count += 1

        print(f"✅ {cols}×{rows} 网格生成完成：{output_folder}")

    except Exception as e:
        print(f"❌ 处理失败：{str(e)}")


def process_folder(input_folder, cols=3, rows=3):
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
        split_image_to_mxn_grid(img_path, cols, rows)

    print("\n🎉 所有图片处理完成！")


if __name__ == "__main__":
    # ========== 在这里修改配置 ==========
    INPUT_FOLDER = r"E:\zyc\下载\拍照姿势整理\2026年5月16日"  # 图片文件夹路径
    COLS = 2  # 切分列数（宽度切几块）
    ROWS = 3  # 切分行数（高度切几块）
    # =====================================

    # 支持命令行参数：python script.py "文件夹路径" 列数 行数
    if len(sys.argv) > 1:
        INPUT_FOLDER = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            COLS = int(sys.argv[2])
        except ValueError:
            print("⚠️ 列数参数无效，将使用默认值 3")
    if len(sys.argv) > 3:
        try:
            ROWS = int(sys.argv[3])
        except ValueError:
            print("⚠️ 行数参数无效，将使用默认值 3")

    process_folder(INPUT_FOLDER, COLS, ROWS)