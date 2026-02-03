import os
import shutil
import random
import subprocess
import threading
import time
import datetime
from pathlib import Path
from typing import List

# ===================== 核心配置 =====================
# 7-Zip 可执行文件路径
SEVEN_ZIP_PATH = r"D:\Program Files\7-Zip\7z.exe"
# 支持的压缩包格式
SUPPORTED_FORMATS = ('.zip', '.rar', '.7z', '.ZIP', '.RAR', '.7Z')
# 固定缓存目录（脚本运行目录下的cache文件夹）
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
# MP4时长读取超时（秒）
MP4_DURATION_TIMEOUT = 10
# 错误日志文件路径
ERROR_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt")


# ==================================================

def write_error_log(file_path: str, error_msg: str):
    """写入错误日志：包含时间戳、文件路径、错误信息"""
    # 日志内容格式
    log_content = (
        f"==================== {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====================\n"
        f"报错文件路径：{file_path}\n"
        f"错误信息：{error_msg}\n\n"
    )
    # 追加写入日志（UTF-8编码避免中文乱码）
    try:
        with open(ERROR_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(log_content)
        print(f"❌ 错误日志已写入：{ERROR_LOG_PATH}")
    except Exception as e:
        print(f"⚠️ 写入错误日志失败: {str(e)}")


def check_7zip_exists():
    """检查7-Zip是否存在"""
    if not os.path.exists(SEVEN_ZIP_PATH):
        raise FileNotFoundError(f"7-Zip 未找到！路径: {SEVEN_ZIP_PATH}\n请确认7-Zip安装路径是否正确")


def create_and_clear_cache():
    """创建cache目录并强制清空所有内容（确保无残留）"""
    # 创建cache目录（不存在则创建）
    Path(CACHE_DIR).mkdir(exist_ok=True)
    # 清空cache内所有文件/文件夹
    for item in os.listdir(CACHE_DIR):
        item_path = os.path.join(CACHE_DIR, item)
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            else:
                shutil.rmtree(item_path)
        except Exception as e:
            print(f"⚠️ 清理cache文件失败 {item}: {str(e)}")
    print(f"✅ 已清空缓存目录: {CACHE_DIR}")


def find_mp4_files(dir_path: str) -> List[str]:
    """递归查找指定目录下所有MP4文件，返回绝对路径列表"""
    mp4_files = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.lower().endswith(".mp4"):
                mp4_files.append(os.path.join(root, file))
    return mp4_files


def get_mp4_duration_with_timeout(mp4_path: str) -> float:
    """带超时的MP4时长读取（避免卡住）"""
    result = [0.0]
    error = [None]

    def worker():
        try:
            os.environ['PYTHONIOENCODING'] = 'gbk'
            from moviepy.editor import VideoFileClip
            with VideoFileClip(mp4_path) as clip:
                result[0] = clip.duration
        except Exception as e:
            error[0] = str(e)
            result[0] = 0.0

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=MP4_DURATION_TIMEOUT)

    if t.is_alive():
        print(f"⚠️ 读取 {os.path.basename(mp4_path)} 时长超时，按0秒计算")
        return 0.0
    if error[0] is not None:
        print(f"⚠️ 无法读取 {os.path.basename(mp4_path)} 时长: {error[0]}")
    return result[0]


def calculate_total_duration(mp4_files: List[str]) -> float:
    """计算所有MP4总时长（分钟）"""
    total_seconds = 0.0
    for mp4_file in mp4_files:
        total_seconds += get_mp4_duration_with_timeout(mp4_file)
    return round(total_seconds / 60, 2)


def create_duration_file(mp4_count: int, total_minutes: float):
    """在cache目录根目录创建时长.txt"""
    duration_file_path = os.path.join(CACHE_DIR, "时长.txt")
    with open(duration_file_path, 'w', encoding='utf-8') as f:
        f.write(f"集数：{mp4_count}\n")
        f.write(f"所有原始MP4文件总时长：{total_minutes} 分钟\n")
    print(f"📝 已创建时长.txt - 集数：{mp4_count}，总时长：{total_minutes} 分钟")


def run_7zip_command(command: list):
    """执行7-Zip命令"""
    try:
        encoding = 'gbk' if os.name == 'nt' else 'utf-8'
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding=encoding,
            errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode not in (0, 1):
            raise RuntimeError(f"7-Zip执行失败: {result.stderr.strip()}")
        return True
    except Exception as e:
        print(f"⚠️ 7-Zip命令警告: {str(e)}")
        return False


def extract_to_cache(archive_path: str):
    """将压缩包解压到cache目录"""
    command = [
        SEVEN_ZIP_PATH,
        'x', archive_path,
        f'-o{CACHE_DIR}',  # 直接解压到cache根目录
        '-y'  # 覆盖已有文件
    ]
    if run_7zip_command(command):
        print(f"✅ 解压完成: {os.path.basename(archive_path)} → {CACHE_DIR}")


def repack_from_cache(archive_path: str, archive_format: str):
    """从cache目录重建压缩包（核心修复：先删原包，再新建）"""
    format_map = {'.zip': 'zip', '.rar': 'rar', '.7z': '7z'}
    pack_format = format_map.get(archive_format.lower(), '7z')

    # 核心修复1：先删除原压缩包（确保是新建而非追加）
    if os.path.exists(archive_path):
        try:
            # 重试删除（避免文件被占用）
            for _ in range(3):
                try:
                    os.remove(archive_path)
                    break
                except:
                    time.sleep(0.5)
            if not os.path.exists(archive_path):
                print(f"✅ 已删除原压缩包: {os.path.basename(archive_path)}")
            else:
                raise RuntimeError(f"无法删除原压缩包 {archive_path}（文件被占用）")
        except Exception as e:
            raise RuntimeError(f"删除原压缩包失败: {str(e)}")

    # 核心修复2：切换到cache目录，新建压缩包（而非追加）
    original_cwd = os.getcwd()
    try:
        os.chdir(CACHE_DIR)
        command = [
            SEVEN_ZIP_PATH,
            'a', archive_path,  # 新建压缩包（原包已删除）
            f'-t{pack_format}',
            '-y',
            '.\\*'  # 仅打包cache内的文件
        ]
        if run_7zip_command(command):
            print(f"✅ 重新打包完成: {os.path.basename(archive_path)}")
    finally:
        os.chdir(original_cwd)


def delete_extra_mp4(keep_file: str, delete_files: list):
    """强制删除多余MP4，确保删除成功"""
    for del_file in delete_files:
        if os.path.exists(del_file):
            try:
                # 强制删除（即使文件被占用，尝试多次）
                for _ in range(3):  # 重试3次
                    try:
                        os.remove(del_file)
                        break
                    except:
                        time.sleep(0.5)
                # 验证删除结果
                if not os.path.exists(del_file):
                    print(f"🗑️ 成功删除: {os.path.basename(del_file)}")
                else:
                    print(f"❌ 最终删除失败: {os.path.basename(del_file)}")
            except Exception as e:
                print(f"⚠️ 删除 {os.path.basename(del_file)} 异常: {str(e)}")
        else:
            print(f"ℹ️ {os.path.basename(del_file)} 已不存在")


def process_single_archive(archive_path: str):
    """处理单个压缩包：基于固定cache目录（新增异常捕获，仅内部处理）"""
    archive_name = os.path.basename(archive_path)
    archive_ext = os.path.splitext(archive_path)[1]

    if archive_ext not in SUPPORTED_FORMATS:
        print(f"⚠️ 跳过不支持的文件: {archive_name}")
        return

    # 1. 处理前清空cache（关键：确保无残留）
    create_and_clear_cache()

    backup_path = archive_path + ".bak"
    try:
        # 2. 备份原文件（先备份，再删除原包）
        shutil.copy2(archive_path, backup_path)
        print(f"📁 原文件已备份: {os.path.basename(backup_path)}")

        # 3. 解压到cache目录
        extract_to_cache(archive_path)

        # 4. 查找所有MP4（原始数量）
        mp4_files = find_mp4_files(CACHE_DIR)
        mp4_count = len(mp4_files)

        # 5. 计算时长并创建时长.txt
        total_minutes = calculate_total_duration(mp4_files)
        create_duration_file(mp4_count, total_minutes)

        # 6. 处理MP4文件
        if mp4_count == 0:
            print(f"ℹ️ {archive_name} 内无MP4文件")
        elif mp4_count == 1:
            print(f"ℹ️ {archive_name} 内仅1个MP4文件，无需删除")
        else:
            keep_file = random.choice(mp4_files)
            delete_files = [f for f in mp4_files if f != keep_file]
            print(f"📌 保留MP4: {os.path.basename(keep_file)}")
            # 删除多余MP4
            delete_extra_mp4(keep_file, delete_files)
            # 最终验证
            remaining_mp4 = find_mp4_files(CACHE_DIR)
            print(f"✅ 验证：cache内剩余MP4数量 = {len(remaining_mp4)}")
            if len(remaining_mp4) != 1:
                raise RuntimeError(f"cache内MP4数量不符合预期（{len(remaining_mp4)}个），终止打包")

        # 7. 从cache重新打包（核心修复：先删原包，再新建）
        repack_from_cache(archive_path, archive_ext)

    except Exception as e:
        # 内部异常：仅打印+清理，不抛出（由外层统一记录日志）
        error_detail = str(e)
        print(f"❌ 处理 {archive_name} 失败: {error_detail}")
        # 恢复原文件
        if os.path.exists(backup_path):
            try:
                if os.path.exists(archive_path):
                    os.remove(archive_path)
                shutil.move(backup_path, archive_path)
                print(f"🔙 已恢复原文件: {archive_name}")
            except Exception as e2:
                error_detail += f"\n恢复原文件失败: {str(e2)}"
        # 抛出异常给外层捕获（用于记录日志）
        raise Exception(error_detail)
    finally:
        # 8. 清理备份和cache
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
                print(f"🗑️ 清理备份文件: {os.path.basename(backup_path)}")
            except Exception as e3:
                print(f"⚠️ 清理备份文件失败: {str(e3)}")
        # 处理完成后清空cache
        create_and_clear_cache()


def process_all_archives(source_dir: str):
    """批量处理所有压缩包：新增全局异常捕获+日志记录"""
    # 初始化错误日志（若不存在则创建空文件）
    if not os.path.exists(ERROR_LOG_PATH):
        with open(ERROR_LOG_PATH, 'w', encoding='utf-8') as f:
            f.write("======= 压缩包处理错误日志 =======\n\n")

    try:
        check_7zip_exists()
    except FileNotFoundError as e:
        print(f"❌ {str(e)}")
        write_error_log("全局检查", str(e))
        return

    if not os.path.exists(source_dir):
        error_msg = f"源目录不存在: {source_dir}"
        print(f"❌ {error_msg}")
        write_error_log("全局检查", error_msg)
        return

    # 初始化cache目录
    create_and_clear_cache()

    # 统计处理结果
    total_count = 0
    success_count = 0
    fail_count = 0
    fail_files = []

    # 遍历处理所有压缩包
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)
        if os.path.isfile(file_path) and os.path.splitext(file_name)[1] in SUPPORTED_FORMATS:
            total_count += 1
            print("\n" + "-" * 60)
            print(f"开始处理 [{total_count}]: {file_name}")
            try:
                # 处理单个文件（内部异常会抛出）
                process_single_archive(file_path)
                success_count += 1
                print(f"✅ 处理完成 [{total_count}]: {file_name}")
            except Exception as e:
                # 捕获所有异常，写入日志，跳过该文件
                fail_count += 1
                fail_files.append(file_name)
                error_msg = str(e)
                write_error_log(file_path, error_msg)
                print(f"❌ 处理失败 [{total_count}]，已跳过: {file_name}")
                continue

    # 最终清空cache
    create_and_clear_cache()

    # 打印处理汇总
    print("\n" + "=" * 60)
    print(f"📊 处理汇总：共 {total_count} 个压缩包 → 成功 {success_count} 个 | 失败 {fail_count} 个")
    if fail_files:
        print(f"❌ 失败文件列表：{', '.join(fail_files)}")
        print(f"📝 详细错误日志：{ERROR_LOG_PATH}")
    print("🎉 所有压缩包处理完成！cache目录已清空")


if __name__ == "__main__":
    # ===================== 配置区 =====================
    # 替换为你的压缩包文件夹路径
    SOURCE_DIRECTORY = r"D:\zyc\Desktop\视频号动漫\all - 副本"
    # ==================================================
    process_all_archives(SOURCE_DIRECTORY)