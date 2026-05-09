import os
import shutil


def collect_and_rename_images(root_dir, output_dir="总图片集合"):
    """
    收集子文件夹中的图片并按规则重命名
    :param root_dir: 根文件夹A的路径
    :param output_dir: 存放所有图片的新文件夹名称
    """
    # 1. 创建输出文件夹
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"✅ 已创建输出文件夹：{output_dir}")

    # 2. 支持的图片格式
    img_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")

    # 统计变量
    total_count = 0
    skip_count = 0

    # 3. 遍历根目录
    print(f"\n📂 正在扫描根目录：{root_dir} ...")

    # 获取根目录下的所有子文件夹 (A1, A2...)
    subfolders = [f for f in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, f))]

    if not subfolders:
        print("❌ 根目录下没有找到子文件夹")
        return

    for folder_name in subfolders:
        folder_path = os.path.join(root_dir, folder_name)

        # 遍历该子文件夹内的所有文件
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(img_exts):
                # 构建新文件名：文件夹名_原文件名
                # 使用 rsplit 分离文件名和后缀，防止文件名中有多个点
                name_part, ext_part = os.path.splitext(filename)
                new_filename = f"{folder_name}_{name_part}{ext_part}"

                src_path = os.path.join(folder_path, filename)
                dst_path = os.path.join(output_dir, new_filename)

                # 检查目标路径是否已存在文件，防止覆盖
                if os.path.exists(dst_path):
                    print(f"⚠️ 跳过 (文件已存在): {new_filename}")
                    skip_count += 1
                    continue

                # 复制文件
                try:
                    shutil.copy2(src_path, dst_path)  # copy2 保留文件元数据
                    print(f"✅ 已处理: {new_filename}")
                    total_count += 1
                except Exception as e:
                    print(f"❌ 复制失败 {filename}: {e}")

    print(f"\n🎉 处理完成！共复制 {total_count} 张图片，跳过 {skip_count} 张。")
    print(f"📍 图片保存在：{os.path.abspath(output_dir)}")


if __name__ == "__main__":
    # ========== 在这里修改你的根文件夹路径 ==========
    # 请将下面的路径改为你实际的 文件夹A 的路径
    ROOT_FOLDER = r"E:\zyc\下载\[fuliba2025.net]sally合集\5"
    # ==================================================

    if os.path.exists(ROOT_FOLDER):
        collect_and_rename_images(ROOT_FOLDER)
    else:
        print(f"❌ 路径不存在，请检查：{ROOT_FOLDER}")