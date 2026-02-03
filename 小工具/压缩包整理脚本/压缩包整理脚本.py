import os
import shutil
import zipfile
import rarfile
import py7zr
from pathlib import Path


def check_archive_content(archive_path):
    """
    检查压缩包内是否同时包含mp4文件和doc/docx文件
    返回值：tuple (has_mp4, has_doc)
    """
    has_mp4 = False
    has_doc = False

    # 统一转换为小写，方便后缀匹配
    archive_path_lower = archive_path.lower()

    try:
        # 处理 zip 格式
        if archive_path_lower.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                file_list = zf.namelist()

        # 处理 rar 格式
        elif archive_path_lower.endswith('.rar'):
            # 设置 rarfile 的解压工具路径（Windows 需确保安装了 unrar）
            rarfile.UNRAR_TOOL = "unrar"  # Linux/Mac 若已安装可直接用；Windows 需指定绝对路径如 "C:\\Program Files\\WinRAR\\UnRAR.exe"
            with rarfile.RarFile(archive_path, 'r') as rf:
                file_list = rf.namelist()

        # 处理 7z 格式
        elif archive_path_lower.endswith('.7z'):
            with py7zr.SevenZipFile(archive_path, 'r') as sf:
                file_list = [f.filename for f in sf.list()]

        else:
            # 不支持的压缩格式
            return (False, False)

        # 检查文件列表
        for file_name in file_list:
            file_name_lower = file_name.lower()
            if not has_mp4 and file_name_lower.endswith('.mp4'):
                has_mp4 = True
            if not has_doc and (file_name_lower.endswith('.doc') or file_name_lower.endswith('.docx')):
                has_doc = True
            # 提前终止检查，提升效率
            if has_mp4 and has_doc:
                break

    except Exception as e:
        print(f"⚠️ 处理压缩包 {archive_path} 时出错: {str(e)}")
        # 出错的压缩包归为"其他"类
        return (False, False)

    return (has_mp4, has_doc)


def organize_archives(source_dir):
    """
    整理指定文件夹中的压缩包
    """
    # 定义分类文件夹名称
    target_dir_1 = os.path.join(source_dir, "包含MP4和文档")
    target_dir_2 = os.path.join(source_dir, "其他压缩包")

    # 创建分类文件夹（不存在则创建）
    Path(target_dir_1).mkdir(exist_ok=True)
    Path(target_dir_2).mkdir(exist_ok=True)

    # 支持的压缩包格式
    archive_extensions = ('.zip', '.rar', '.7z', '.ZIP', '.RAR', '.7Z')

    # 遍历源文件夹中的所有文件
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)

        # 只处理文件（排除文件夹）且是压缩包
        if os.path.isfile(file_path) and file_name.endswith(archive_extensions):
            print(f"正在检查: {file_name}")

            # 检查压缩包内容
            has_mp4, has_doc = check_archive_content(file_path)

            # 确定目标文件夹
            if has_mp4 and has_doc:
                dest_dir = target_dir_1
                print(f"✅ {file_name} 包含MP4和文档，移动到 {dest_dir}")
            else:
                dest_dir = target_dir_2
                print(f"❌ {file_name} 不满足条件，移动到 {dest_dir}")

            # 移动文件（如果目标已存在同名文件，自动重命名避免覆盖）
            dest_path = os.path.join(dest_dir, file_name)
            counter = 1
            while os.path.exists(dest_path):
                name, ext = os.path.splitext(file_name)
                dest_path = os.path.join(dest_dir, f"{name}_{counter}{ext}")
                counter += 1

            shutil.move(file_path, dest_path)

    print("\n🎉 压缩包整理完成！")
    print(f"📁 包含MP4和文档的压缩包: {target_dir_1}")
    print(f"📁 其他压缩包: {target_dir_2}")


if __name__ == "__main__":
    # ===================== 配置区 =====================
    # 替换为你要整理的文件夹路径
    # Windows示例: r"C:\Users\你的名字\Desktop\压缩包文件夹"
    # Mac/Linux示例: "/Users/你的名字/Desktop/压缩包文件夹"
    SOURCE_DIRECTORY = r"D:\zyc\Desktop\视频号动漫\all - 副本"
    # ==================================================

    # 检查源文件夹是否存在
    if not os.path.exists(SOURCE_DIRECTORY):
        print(f"❌ 错误：文件夹 {SOURCE_DIRECTORY} 不存在！")
    else:
        organize_archives(SOURCE_DIRECTORY)