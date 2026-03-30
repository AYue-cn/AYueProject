
import os
import shutil

def get_unique_filename(dest_folder, filename):
    """
    生成不重复的文件名，如果重名则在文件名后添加序号 (如: file.txt -> file_1.txt)
    """
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename

    # 循环检查直到找到一个不存在的文件名
    while os.path.exists(os.path.join(dest_folder, new_filename)):
        new_filename = f"{name}_{counter}{ext}"
        counter += 1

    return new_filename

def flatten_folder(source_folder):
    """
    遍历文件夹，将所有子文件夹内的文件移动到主文件夹
    """
    # 检查路径是否存在
    if not os.path.isdir(source_folder):
        print(f"错误：路径 '{source_folder}' 不存在。")
        return

    # os.walk 会递归遍历所有子目录
    # root: 当前正在遍历的文件夹路径
    # files: 当前文件夹下的文件列表
    for root, dirs, files in os.walk(source_folder):
        # 如果当前就是主文件夹，跳过（避免处理已经在主目录的文件）
        if root == source_folder:
            continue

        for file in files:
            # 1. 构建源文件的完整路径
            src_path = os.path.join(root, file)

            # 2. 生成在主文件夹中不重名的文件名
            dest_filename = get_unique_filename(source_folder, file)
            dest_path = os.path.join(source_folder, dest_filename)

            try:
                # 3. 移动文件
                shutil.move(src_path, dest_path)
                print(f"[成功] {src_path} -> {dest_filename}")
            except Exception as e:
                print(f"[失败] 无法移动 {src_path}: {e}")

    print("\n操作完成！")

# ================= 配置区域 =================
# 请将下面的路径修改为你需要操作的文件夹路径
# 注意：Windows路径建议在引号前加 r，防止转义字符报错
target_path = r"D:\zyc\下载\🍉集合🍉"
# ===========================================

if __name__ == '__main__':
    print("警告：文件移动操作不可逆！建议先备份文件夹。")
    confirm = input("输入 'yes' 确认继续操作: ")
    if confirm.lower() == 'yes':
        flatten_folder(target_path)
    else:
        print("操作已取消。")