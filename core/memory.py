import logging
import requests
import json

logger = logging.getLogger("memory")

# 保留最近几轮不压缩（一轮 = 一问一答）
RECENT_KEEP_TURNS = 6
# 历史超过多少轮时触发压缩
COMPRESS_THRESHOLD = 10


def should_compress(chat_history: list) -> bool:
    """判断是否需要压缩：消息条数超过阈值"""
    # 只统计 user/assistant 消息
    turns = sum(1 for m in chat_history if m["role"] in ("user", "assistant")) // 2
    return turns > COMPRESS_THRESHOLD


def compress_history(chat_history: list, llm_base_url: str, params: dict) -> list:
    """
    把 chat_history 中较早的部分压缩为一条摘要消息，
    返回新的 chat_history（原列表不修改）。
    """
    # 只处理 user/assistant 消息，system 消息单独保留
    system_msgs = [m for m in chat_history if m["role"] == "system"]
    dialog_msgs = [m for m in chat_history if m["role"] in ("user", "assistant")]

    # 保留最近 RECENT_KEEP_TURNS 轮（每轮2条）
    keep_count = RECENT_KEEP_TURNS * 2
    to_compress = dialog_msgs[:-keep_count] if len(dialog_msgs) > keep_count else []
    recent = dialog_msgs[-keep_count:] if len(dialog_msgs) > keep_count else dialog_msgs

    if not to_compress:
        return chat_history  # 不够压缩，原样返回

    # 构建压缩 prompt
    history_text = ""
    for m in to_compress:
        role_label = "用户" if m["role"] == "user" else "助手"
        content = m["content"]
        if isinstance(content, list):
            content = next((p.get("text", "") for p in content if p.get("type") == "text"), "")
        history_text += f"{role_label}：{content}\n\n"

    compress_messages = [
        {
            "role": "system",
            "content": "你是一个对话摘要助手，请将以下对话历史压缩为简洁的摘要，"
                       "保留所有关键信息、结论和重要细节，使用第三人称描述，控制在300字以内。"
        },
        {
            "role": "user",
            "content": f"请压缩以下对话历史：\n\n{history_text}"
        }
    ]

    summary = _call_llm_sync(compress_messages, llm_base_url, params)
    if not summary:
        logger.warning("摘要生成失败，跳过压缩")
        return chat_history

    logger.info(f"对话历史已压缩，摘要长度：{len(summary)}")

    # 组装新历史：system + 摘要消息 + 最近 K 轮
    summary_msg = {
        "role": "assistant",
        "content": f"📝 【对话摘要】\n{summary}"
    }
    return system_msgs + [summary_msg] + recent


def _call_llm_sync(messages: list, base_url: str, params: dict) -> str:
    """同步调用 LLM 生成摘要（非流式）"""
    # 摘要生成用轻量参数，不需要 thinking
    payload = {
        "messages": messages,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": params.get("max_tokens", 512),
    }
    try:
        resp = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            timeout=60
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"摘要调用失败: {e}")
        return ""
