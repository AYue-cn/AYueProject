import re


def remove_duplicate_chapters(input_file, output_file=None):
    """
    去除txt文档中重复的章节标题
    :param input_file: 输入文件路径（含.txt后缀）
    :param output_file: 输出文件路径（默认覆盖原文件）
    """
    # 如果未指定输出文件，默认覆盖原文件
    if output_file is None:
        output_file = input_file

    # 正则表达式匹配带方括号的重复章节格式（如【第1章：第1章 快来抓禽兽】）
    # 支持章节号为1位或多位数字
    pattern = r'^【第(\d+)章：第\1章 .+】$'

    with open(input_file, 'r', encoding='utf-8') as f_in, \
            open(output_file, 'w', encoding='utf-8') as f_out:

        for line in f_in:
            # 去除行首尾空白（避免换行符、空格影响匹配）
            line_stripped = line.strip()

            # 如果该行匹配重复格式，则跳过（不写入）
            if re.match(pattern, line_stripped):
                continue

            # 不匹配则保留该行，写入新文件
            f_out.write(line)

    print(f"处理完成！结果已保存到：{output_file}")


# ------------------- 使用示例 -------------------
if __name__ == "__main__":
    # 请修改为你的文件路径
    input_txt = "透视狂兵_自动保存.txt"  # 例如："小说.txt" 或 "C:/books/故事.txt"

    # 可选：指定输出文件（避免覆盖原文件）
    output_txt = input_txt+"处理后的文件.txt"

    # 调用函数（如果要覆盖原文件，只传input_txt即可）
    remove_duplicate_chapters(input_txt,output_file=output_txt)

    # 如果要保留原文件，使用：
    # remove_duplicate_chapters(input_txt, output_txt)