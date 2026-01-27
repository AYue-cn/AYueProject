#!/usr/bin/env python3
"""
edge-tts 修复版 Demo
解决：zh-CN Female 语音筛选失败问题 + 增加语音列表验证
"""
import asyncio
import sys
import edge_tts
from edge_tts import VoicesManager

# ===================== 配置项（已修正） =====================
TEXT = """
edge-tts 是基于微软 Edge 在线 TTS 服务的 Python 库，支持多语言、多音色。
Edge TTS supports multiple languages and voices, such as English, Chinese, Spanish, etc.
人生得意须尽欢，莫使金樽空对月。
"""
OUTPUT_AUDIO = "demo_output.mp3"
OUTPUT_SRT = "demo_output.srt"
# 修正：用 Locale 筛选完整地区，或用 Language="zh"
VOICE_FILTER = {
    "Locale": "zh-CN",  # 筛选“中文（中国）”地区
    "Gender": "Female"  # 筛选女声
}
STREAM_VOICE = "zh-CN-YunxiNeural"  # 确保该语音存在（可通过 list_voices 验证）


# ===================== 新增：验证可用语音（调试用） =====================
async def print_available_voices():
    """打印指定条件的可用语音列表（调试必备）"""
    voices = await VoicesManager.create()
    # 1. 打印所有 zh-CN 语音（验证是否存在）
    zh_cn_voices = voices.find(Locale="zh-CN")
    print("=== 所有 zh-CN 可用语音 ===")
    for v in zh_cn_voices:
        print(f"- 名称：{v['Name']} | 性别：{v['Gender']} | 友好名：{v['FriendlyName']}")
    return zh_cn_voices


# ===================== 核心功能（修正筛选逻辑） =====================
async def async_generate_audio_with_subtitle() -> None:
    """异步生成音频+字幕（修正语音筛选）"""
    # 1. 获取语音列表并筛选（改用 Locale 筛选）
    voices = await VoicesManager.create()
    available_voices = voices.find(**VOICE_FILTER)

    if not available_voices:
        print(f"❌ 仍未找到符合条件的语音：{VOICE_FILTER}")
        return
    # 选择第一个符合条件的语音
    selected_voice = available_voices[0]["Name"]
    print(f"✅ 选中语音：{selected_voice}")

    # 2. 生成音频+字幕（逻辑不变）
    communicate = edge_tts.Communicate(TEXT, selected_voice)
    submaker = edge_tts.SubMaker()

    with open(OUTPUT_AUDIO, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)

    with open(OUTPUT_SRT, "w", encoding="utf-8") as srt_file:
        srt_file.write(submaker.get_srt())

    print(f"✅ 异步生成完成：\n- 音频：{OUTPUT_AUDIO}\n- 字幕：{OUTPUT_SRT}")


def sync_stream_play_and_print_subtitle() -> None:
    """同步流式播放+打印字幕（逻辑不变）"""
    print("\n--- 开始同步流式播放并打印字幕 ---")
    communicate = edge_tts.Communicate(TEXT, STREAM_VOICE, boundary="SentenceBoundary")
    submaker = edge_tts.SubMaker()
    audio_chunks = []

    for chunk in communicate.stream_sync():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            submaker.feed(chunk)

    print(f"音频数据总长度：{len(b''.join(audio_chunks))} 字节")
    print("\n生成的字幕：")
    print(submaker.get_srt())


# ===================== 主函数 =====================
async def main():
    # 1. 先打印可用语音（调试）
    await print_available_voices()
    # 2. 异步生成音频+字幕
    await async_generate_audio_with_subtitle()
    # 3. 同步流式播放
    sync_stream_play_and_print_subtitle()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())