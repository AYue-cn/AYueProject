import os
from volcenginesdkarkruntime import Ark

# 请确保您已将 API Key 存储在环境变量 ARK_API_KEY 中
# 初始化Ark客户端，从环境变量中读取您的API Key
client = Ark(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key="d93cef80-19e9-4643-888d-05d4da4ec2c1",
)

# Non-streaming:
print("----- image input request -----")
completion = client.chat.completions.create(
    # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
    model="doubao-seed-1-6-lite-251015",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://ark-project.tos-cn-beijing.ivolces.com/images/view.jpeg"
                    },
                },
                {"type": "text", "text": "这是哪里？"},
            ],
        }
    ],
    reasoning_effort="medium",

)
print(completion.choices[0].message.content)

# # Streaming:
# print("----- streaming request -----")
# stream = client.chat.completions.create(
#     model="doubao-seed-1-6-lite-251015",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": "https://ark-project.tos-cn-beijing.ivolces.com/images/view.jpeg"
#                     },
#                 },
#                 {"type": "text", "text": "这是哪里？"},
#             ],
#         }
#     ],
#     reasoning_effort="medium",
#
#     # 响应内容是否流式返回
#     stream=True,
# )
# for chunk in stream:
#     if not chunk.choices:
#         continue
#     print(chunk.choices[0].delta.content, end="")
# print()
