from bs4 import BeautifulSoup
import os
import re
from tkinter import Tk, filedialog, messagebox
import sys


def extract_single_chapter(html_content, debug=False):
    """
    针对性解析：适配单p标签内嵌套未闭合<p>的HTML结构
    核心逻辑：
    1. 定位第一个有内容的id="concent"的p标签（唯一存储小说内容的标签）
    2. 提取该标签内所有文本（自动处理未闭合嵌套标签）
    3. 按原段落结构拆分（基于嵌套<p>的位置）
    4. 清理格式残留，保留纯文本
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    novel_text = []

    if debug:
        print("=== 调试模式：开始解析 ===")

    # 步骤1：找到所有id="concent"的p标签，筛选出有实际内容的那个
    concent_tags = soup.find_all('p', id='concent')
    target_tag = None
    for tag in concent_tags:
        # 过滤掉空标签（只保留有文本内容的）
        tag_text = tag.get_text(strip=True)
        if tag_text and len(tag_text) > 10:  # 过滤掉长度小于10的空标签
            target_tag = tag
            break

    if not target_tag:
        if debug:
            print("❌ 未找到包含内容的id='concent'标签")
        return None

    if debug:
        print(f"✅ 找到目标标签：id='concent'，文本长度：{len(target_tag.get_text())}")

    # 步骤2：提取标签内所有文本（BeautifulSoup会自动处理未闭合标签）
    full_text = target_tag.get_text()

    # 步骤3：按原段落结构拆分（基于嵌套<p>的语义，按句子/对话自然拆分）
    # 拆分规则：以中文标点（。！？”）结尾的为一个段落，或单独的对话为一个段落
    # 增强版拆分正则：匹配中文标点+换行/空格，作为段落分隔
    paragraphs = re.split(r'([。！？”])\s*', full_text)

    # 重组段落（将拆分的标点和文本合并）
    current_paragraph = ""
    for part in paragraphs:
        if part in ['。', '！', '？', '”']:
            if current_paragraph:
                current_paragraph += part
                novel_text.append(current_paragraph.strip())
                current_paragraph = ""
        else:
            current_paragraph += part

    # 处理最后一个未完成的段落
    if current_paragraph.strip():
        novel_text.append(current_paragraph.strip())

    # 步骤4：过滤无效内容，清理格式
    valid_paragraphs = []
    ignore_keywords = ['客服QQ', '刷新无效', '联系我们', '下一章', '上一章', '目录']
    for para in novel_text:
        # 过滤空段落和过短的无意义段落
        if not para or len(para) < 2:
            continue
        # 过滤无关控制文本
        if any(keyword in para for keyword in ignore_keywords):
            if debug:
                print(f"过滤无关文本：{para[:20]}...")
            continue
        valid_paragraphs.append(para)

    if debug:
        print(f"✅ 拆分后有效段落数：{len(valid_paragraphs)}")
        if valid_paragraphs:
            print(f"第一段：{valid_paragraphs[0]}")
            print(f"最后一段：{valid_paragraphs[-1]}")

    # 拼接成完整章节内容
    if valid_paragraphs:
        chapter_content = '\n'.join(valid_paragraphs)
        # 清理多余空行
        chapter_content = re.sub(r'\n+', '\n', chapter_content)
        return chapter_content.strip()

    return None


def get_file_encoding(file_path):
    """自动检测文件编码（支持常见编码）"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(1024)  # 只读前1024字节检测编码
            return encoding
        except Exception:
            continue
    return None


def extract_chapter_number(filename):
    """增强版章节号提取（适配更多命名格式）"""
    pattern = r'(第\s*(\d+)\s*章)|(chapter\s*(\d+))|(chap\s*(\d+))|(\d+)\s*章|(\d+)'
    matches = re.findall(pattern, filename, re.IGNORECASE)
    for match in matches:
        for group in match:
            if group and group.isdigit():
                return int(group)
    return 9999


def get_sorted_html_files(folder_path, recursive=False):
    """获取排序后的HTML文件列表"""
    html_files = []
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            if filename.lower().endswith(('.html', '.htm')):
                file_path = os.path.join(root, filename)
                chapter_num = extract_chapter_number(filename)
                html_files.append((chapter_num, file_path, filename))
        if not recursive:
            break

    html_files.sort(key=lambda x: x[0])
    return [file_info[1] for file_info in html_files]


def merge_novel_chapters(folder_path, output_filename="完整小说_透视狂兵.txt", recursive=False, debug=False):
    """合并所有章节"""
    sorted_files = get_sorted_html_files(folder_path, recursive)
    if not sorted_files:
        print("❌ 未找到任何HTML/HTM文件！")
        return

    print(f"找到 {len(sorted_files)} 个章节文件，开始提取...")
    print("-" * 60)

    full_novel = []
    failed_files = []

    for idx, file_path in enumerate(sorted_files, 1):
        try:
            # 自动检测编码
            encoding = get_file_encoding(file_path)
            if not encoding:
                print(f"❌ 跳过 {os.path.basename(file_path)}：无法识别编码")
                failed_files.append(os.path.basename(file_path))
                continue

            # 读取文件
            with open(file_path, 'r', encoding=encoding) as f:
                html_content = f.read()

            # 提取章节内容（仅对第一个文件开启debug，避免输出过多）
            chapter_content = extract_single_chapter(html_content, debug=debug and idx == 1)

            if not chapter_content:
                print(f"⚠️  跳过 {os.path.basename(file_path)}：未提取到有效内容")
                failed_files.append(os.path.basename(file_path))
                continue

            # 提取章节标题（优先取前20字符内包含"第X章"的内容）
            chapter_title = f"第{idx}章"
            title_match = re.search(r'第\s*\d+\s*章.*?(?=\n|$)', chapter_content)
            if title_match:
                chapter_title = title_match.group().strip()
            else:
                # 若未找到明确标题，取第一段作为标题
                first_para = chapter_content.split('\n')[0][:20] + "..." if len(
                    chapter_content.split('\n')[0]) > 20 else chapter_content.split('\n')[0]
                chapter_title = f"第{idx}章 {first_para}"

            # 格式化章节
            formatted_chapter = f"【{chapter_title}】\n{chapter_content}\n" + "=" * 80 + "\n"
            full_novel.append(formatted_chapter)

            print(f"✅ 已处理：{os.path.basename(file_path)} -> {chapter_title}")

        except Exception as e:
            error_msg = str(e)[:50] + "..." if len(str(e)) > 50 else str(e)
            print(f"❌ 失败：{os.path.basename(file_path)} - {error_msg}")
            failed_files.append(os.path.basename(file_path))

    # 输出结果
    print("-" * 60)
    if full_novel:
        output_path = os.path.join(folder_path, output_filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(full_novel))

        print(f"🎉 汇总完成！")
        print(f"📁 保存路径：{output_path}")
        print(f"📚 成功处理章节数：{len(full_novel)}")
        print(f"📝 总字符数：{sum(len(chapter) for chapter in full_novel)}")
    else:
        print("❌ 未提取到任何有效小说内容！")

    # 输出失败文件
    if failed_files:
        print(f"\n⚠️  处理失败/跳过的文件（共{len(failed_files)}个）：")
        for file in failed_files[:5]:
            print(f"  - {file}")
        if len(failed_files) > 5:
            print(f"  - 还有 {len(failed_files) - 5} 个文件未列出")


def main():
    print("=" * 80)
    print("          小说汇总工具（专属适配霜月短文HTML结构）")
    print("=" * 80)
    print("适配特征：所有内容在单个id='concent'的p标签内，嵌套未闭合<p>标签")
    print("功能：自动识别编码、提取文本、按章节排序、汇总为TXT")
    print("=" * 80)

    # 选择文件夹
    root = Tk()
    root.withdraw()
    folder_path = filedialog.askdirectory(title="选择小说章节文件夹")
    if not folder_path:
        print("未选择文件夹，程序退出")
        return

    # 询问递归和调试
    recursive = messagebox.askyesno("递归遍历", "是否递归遍历子文件夹？")
    debug = messagebox.askyesno("调试模式", "是否开启调试模式？（首次使用建议开启）")

    # 开始汇总
    merge_novel_chapters(folder_path, recursive=recursive, debug=debug)

    input("\n按回车键退出...")


if __name__ == "__main__":
    main()