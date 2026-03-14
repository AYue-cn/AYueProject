import os
import shutil


def flatten_folder(folder_x):
    """
    将 folder_x 下所有子文件夹内的文件移动到 folder_x 根目录下。
    如果遇到同名文件，自动添加序号重命名 (例如: file.txt -> file_1.txt)。
    """

    # 检查目标文件夹是否存在
    if not os.path.isdir(folder_x):
        print(f"错误: 路径 '{folder_x}' 不存在或不是文件夹。")
        return

    # 遍历目录树
    # os.walk 会递归进入每一个子文件夹
    for root, dirs, files in os.walk(folder_x):

        # 如果当前遍历的目录就是根目录 X，跳过（不需要移动根目录已有的文件）
        if root == folder_x:
            continue

        # 遍历当前子文件夹内的所有文件
        for filename in files:
            # 1. 构建源文件的完整路径
            src_path = os.path.join(root, filename)

            # 2. 构建目标路径 (X 文件夹下)
            dst_path = os.path.join(folder_x, filename)

            # --- 智能处理文件名冲突 ---
            # 如果 X 里已经有同名文件了，就在文件名后加序号 (如 image_1.jpg)
            counter = 1
            while os.path.exists(dst_path):
                # 分离文件名和后缀
                name, ext = os.path.splitext(filename)
                # 重组新名字
                new_filename = f"{name}_{counter}{ext}"
                dst_path = os.path.join(folder_x, new_filename)
                counter += 1

            # --- 执行移动 ---
            try:
                shutil.move(src_path, dst_path)
                print(f"[成功] {src_path} -> {dst_path}")
            except Exception as e:
                print(f"[失败] 无法移动 {src_path}: {e}")

    print("\n所有文件处理完毕。")


# ================= 配置区域 =================
# 在这里修改你的文件夹 X 的路径
# 注意：Windows 路径建议在引号前加 r，防止转义字符报错
# 例如：r"D:\Work\Project\FolderX"
# ================= 配置区域 =================

if __name__ == "__main__":
    # 请将下面的路径修改为你实际的文件夹路径
    target_folder = r"D:\PythonProjects\Moviepy混剪\家庭素材"

    flatten_folder(target_folder)