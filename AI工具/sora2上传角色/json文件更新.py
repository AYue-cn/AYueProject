import json
import os


def load_json_file(file_path):
    """
    读取JSON文件，处理文件不存在、格式错误等异常，返回解析后的列表（默认空列表）
    """
    try:
        if not os.path.exists(file_path):
            print(f"提示：文件 {file_path} 不存在，将使用空列表替代")
            return []

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 确保读取的数据是列表格式
        if not isinstance(data, list):
            print(f"警告：{file_path} 内容不是列表格式，将使用空列表替代")
            return []

        return data
    except json.JSONDecodeError as e:
        print(f"错误：{file_path} JSON格式错误 - {e}，将使用空列表替代")
        return []
    except Exception as e:
        print(f"错误：读取 {file_path} 时发生未知错误 - {e}，将使用空列表替代")
        return []


def save_json_file(file_path, data):
    """
    将数据写入JSON文件，保证格式缩进（和示例一致），覆盖原有内容
    """
    try:
        # 确保目标目录存在（比如cache文件夹不存在时自动创建）
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            # indent=2 保证和示例格式一致，ensure_ascii=False 支持中文
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"成功写入文件：{file_path}")
        return True
    except Exception as e:
        print(f"错误：写入 {file_path} 时发生错误 - {e}")
        return False


def merge_and_deduplicate_json():
    """
    核心逻辑：读取两个文件 → 合并 → 去重 → 覆盖写入
    """
    # 定义两个文件的路径
    current_file = "sora_characters.json"
    cache_file = os.path.join("cache", "sora_characters.json")

    # 1. 读取两个文件的内容
    current_data = load_json_file(current_file)
    cache_data = load_json_file(cache_file)

    # 2. 合并并去重（以character_id为唯一标识）
    # 用字典存储：key=character_id，value=完整数据（自动去重）
    deduplicated_dict = {}

    # 先添加当前目录的数据
    for item in current_data:
        char_id = item.get("character_id")
        if char_id:  # 跳过无character_id的无效数据
            deduplicated_dict[char_id] = item

    # 再添加cache目录的数据（重复的会被覆盖，保留cache的最新数据，可根据需求调整顺序）
    for item in cache_data:
        char_id = item.get("character_id")
        if char_id:
            deduplicated_dict[char_id] = item

    # 转换回列表格式
    merged_data = list(deduplicated_dict.values())

    # 3. 覆盖写入两个文件
    save_json_file(current_file, merged_data)
    save_json_file(cache_file, merged_data)

    print(f"\n合并完成！共处理 {len(current_data) + len(cache_data)} 条原始数据，去重后剩余 {len(merged_data)} 条数据")


if __name__ == "__main__":
    print("开始合并sora_characters.json文件...")
    merge_and_deduplicate_json()
    print("操作全部完成！")