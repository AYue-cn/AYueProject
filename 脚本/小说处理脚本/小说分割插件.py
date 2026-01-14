import re
import os

def clean_filename(filename):
    """清理文件名中的非法字符（Windows 系统禁止的字符）"""
    illegal_chars = r'[\\/:*?"<>|]'
    cleaned = re.sub(illegal_chars, '_', filename)
    return cleaned

def split_novel_by_chapter_count(input_file, output_dir="split_chapters", chapters_per_file=5):
    """
    将小说按固定的章节数量分割成多个文件，每个文件添加指定开头。
    支持两种章节标题格式：第一章/第100章、001章/002章/123章

    参数:
    input_file: 输入的txt小说文件路径。
    output_dir: 输出目录，默认是 "split_chapters"。
    chapters_per_file: 每个输出文件包含的章节数，默认是 5。
    """

    # 处理路径转义问题
    input_file = os.path.abspath(input_file)
    output_dir = os.path.abspath(output_dir)

    # 递归创建输出目录（支持多级目录）
    os.makedirs(output_dir, exist_ok=True)
    print(f"输出目录：{output_dir}")

    # 读取小说内容（兼容utf-8和gbk编码）
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(input_file, 'r', encoding='gbk') as f:
            content = f.read()
    print(f"成功读取输入文件：{input_file}")

    # 核心修改：正则表达式匹配两种章节格式
    # 格式1：第[中文数字/阿拉伯数字]章（如第一章、第100章、第两百章）
    # 格式2：纯数字+章（含前导零，如001章、002章、123章）
    chapter_pattern = re.compile(
        r'^(第[零一二三四五六七八九十百千万\d]+章)|^(\d+章)',  # 匹配两种格式
        re.MULTILINE  # 多行匹配（确保每行开头的章节标题都能被识别）
    )

    # 分割内容（保留章节标题）
    parts = chapter_pattern.split(content)

    # 重新组织章节列表（过滤空值，合并两种格式的匹配结果）
    chapters = []
    # 先处理前言（如果有）
    if parts and not chapter_pattern.match(parts[0]):
        if parts[0].strip():
            chapters.append(("前言_序章", parts[0]))
        parts = parts[1:]

    # 遍历分割结果，提取章节标题和内容（两种格式统一处理）
    i = 0
    while i < len(parts):
        # 匹配格式1（第X章）或格式2（数字章）
        title1 = parts[i].strip() if parts[i] else ""
        title2 = parts[i+1].strip() if (i+1 < len(parts) and parts[i+1]) else ""
        title = title1 if title1 else title2

        if title and (title.endswith("章") or title.startswith("第")):
            # 提取章节内容（下一个分割点之前的内容）
            content_segment = parts[i+2].strip() if (i+2 < len(parts)) else ""
            full_chapter_content = f"{title}\n\n{content_segment}"
            chapters.append((title, full_chapter_content))
            i += 3  # 跳过已处理的标题和内容
        else:
            i += 1

    # 过滤空章节
    chapters = [(title, content) for title, content in chapters if content.strip()]

    if not chapters:
        print("❌ 未识别到任何章节！")
        print("支持的章节格式：")
        print("  1. 第X章（如：第一章、第100章、第两百三十章）")
        print("  2. 纯数字章（如：001章、002章、123章）")
        print("请检查小说章节标题是否符合上述格式，且章节标题单独一行。")
        return

    print(f"✅ 共识别到 {len(chapters)} 个章节/部分")

    # 计算目标字数
    target_word_count = chapters_per_file * 1500
    # 开头固定文本
    header_text = f"""我是一名漫画小说的短视频博主，要把一篇小说改成适合小说推文的文案，因为输入字数有上限，现在把小说分段给你，并且有如下要求：
1.改成第一人称视角，主体情节不变，但是要完全改写。
2.以原来的开头开始，以原来的结尾结束，不要添加剧情，不要续写剧情。方便后续和其他章节进行衔接。
3.开头要有爆点，要有钩子、能吸引用户看小说。
4.生成字数在9000字左右。
5.避免出现涉黄，恐怖血腥的文案，新文案绝对原创，不能被抖音识别抄袭和搬运。
6.开头和结尾修改后要保持原意，
文本如下："""

    # 计算需要生成的文件数
    total_files = (len(chapters) + chapters_per_file - 1) // chapters_per_file
    print(f"📊 预计生成 {total_files} 个文件（每文件{chapters_per_file}章）")

    # 生成文件
    for file_idx in range(total_files):
        start_idx = file_idx * chapters_per_file
        end_idx = min(start_idx + chapters_per_file, len(chapters))

        # 提取并清理章节标题（用于文件名）
        start_chapter_title = clean_filename(chapters[start_idx][0])
        end_chapter_title = clean_filename(chapters[end_idx - 1][0])

        # 拼接章节内容
        current_file_content_parts = [header_text]
        for i in range(start_idx, end_idx):
            current_file_content_parts.append(chapters[i][1])
        final_content = '\n\n'.join(current_file_content_parts)

        # 生成文件名
        filename = f"小说分段_{start_chapter_title}_到_{end_chapter_title}.txt"
        filename = clean_filename(filename)  # 双重清理非法字符
        output_path = os.path.join(output_dir, filename)

        # 写入文件
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            print(f"✅ 已生成：{filename}（包含第{start_idx+1}-{end_idx}部分）")
        except Exception as e:
            print(f"❌ 生成失败：{filename} - 错误：{str(e)}")

    print(f"\n📁 所有文件已生成到：{output_dir}")
    print(f"📊 最终生成 {total_files} 个文件")

# --- 使用示例 ---
if __name__ == "__main__":
    # 输入输出路径（用原始字符串 r"" 避免转义）
    input_novel_file = r"D:\zyc\Desktop\小说\dj0011反派就应该无敌\反派就应该无敌.txt"
    output_dir = r"D:\zyc\Desktop\小说\dj0011反派就应该无敌\split_chapters"
    chapters_per_file = 6  # 每文件7章

    # 执行分割
    if os.path.exists(input_novel_file):
        split_novel_by_chapter_count(
            input_file=input_novel_file,
            output_dir=output_dir,
            chapters_per_file=chapters_per_file
        )
    else:
        print(f"❌ 找不到输入文件：{input_novel_file}")
        print("请检查：1.路径是否正确；2.文件是否存在；3.文件名是否有特殊字符")