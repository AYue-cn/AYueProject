import base64


def parse_sub_url(sub_url: str) -> str:
    """
    解析 sub:// 格式的订阅地址，还原真实的 HTTPS 订阅链接
    :param sub_url: 原始的 sub:// 格式地址
    :return: 解码后的真实订阅地址
    """
    # 步骤1：校验输入格式，必须以 sub:// 开头
    if not sub_url.startswith("sub://"):
        raise ValueError("输入的地址不是合法的 sub:// 格式！")

    # 步骤2：去掉 sub:// 前缀，再去掉 # 及后面的备注内容
    # 例如：sub://xxx#备注 → 提取 xxx 部分
    base64_str = sub_url.replace("sub://", "").split("#")[0].strip()

    # 步骤3：Base64 补位（编码长度必须是 4 的倍数，不足补 =）
    # 计算需要补充的等号数量
    padding = len(base64_str) % 4
    if padding != 0:
        base64_str += "=" * (4 - padding)

    # 步骤4：Base64 解码（UTF-8 格式）
    try:
        # 解码：先转 bytes 再解码为字符串
        real_url = base64.b64decode(base64_str).decode("utf-8")
        return real_url
    except base64.binascii.Error as e:
        raise ValueError(f"Base64 解码失败，原始编码串可能无效：{e}")
    except UnicodeDecodeError as e:
        raise ValueError(f"解码后的内容不是 UTF-8 格式：{e}")


# 测试示例（替换成你要解析的 sub:// 地址）
if __name__ == "__main__":
    # 你提供的示例地址
    test_sub_url = "sub://aHR0cHM6Ly9teXN1Yi5jYy9zdWJzY3JpYmUvMTMwNTMvUVY5SkNFOXhIMy9zc3Iv#IPLC.VIP"

    try:
        # 调用解析函数
        real_sub_url = parse_sub_url(test_sub_url)
        print("✅ 解析成功！真实订阅地址：")
        print(real_sub_url)
    except Exception as e:
        print(f"❌ 解析失败：{e}")
