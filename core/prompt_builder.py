from datetime import datetime

class PromptBuilder:
    @staticmethod
    def build_messages(
        chat_history: list,
        base_system_prompt: str,
        doc_text: str = None,
        rag_context: str = None,
        search_context: str = None,
        max_doc_length: int = 12000,
    ) -> list:
        # 1. 组装系统提示词 (含时间和知识截止日)
        now = datetime.now()
        weekday = ['一', '二', '三', '四', '五', '六', '日'][now.weekday()]
        system_lines = [
            f"当前日期时间：{now.strftime('%Y年%m月%d日 %H:%M')} 星期{weekday}。",
            "系统时间仅用于组织表达，不代表任何信息已被搜索引擎收录或已更新；不要基于系统时间臆测事实。",
            base_system_prompt,
        ]
        if search_context:
            system_lines.insert(
                1,
                "当问题涉及时效性或最新动态时，只能基于搜索结果中的来源内容作答；若来源缺失或日期不明，请明确说明不确定。"
            )
        else:
            system_lines.insert(
                1,
                "当问题涉及时效性或最新动态时，如果没有搜索结果，请明确说明可能无法掌握最新情况。"
            )
        system_content = "\n".join(system_lines)
        
        system_parts = [system_content]

        # 2. 场景A：文件对话
        if doc_text:
            truncated = doc_text[:max_doc_length]
            if len(doc_text) > max_doc_length:
                truncated += f"\n\n（文档内容较长，以上为前 {max_doc_length} 字）"
            system_parts.append(
                f"以下是用户附加的文档原文，请根据用户指令对其进行处理"
                f"（总结/续写/改写/问答等）：\n\n"
                f"【文档内容开始】\n{truncated}\n【文档内容结束】"
            )

        # 3. 场景B：向量知识库检索
        if rag_context:
            system_parts.append(
                f"以下是知识库中与问题相关的参考内容，请优先参考：\n\n{rag_context}"
            )

        # 4. 联网搜索注入
        if search_context:
            system_parts.append(search_context)

        messages = [
            {"role": "system", "content": "\n\n---\n\n".join(system_parts)}
        ] + list(chat_history)

        return messages
