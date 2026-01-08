"""
个性化提示词构建器
将用户画像和记忆注入到system prompt中
"""

import json
import logging
from typing import Dict, List


class PromptBuilder:
    """个性化提示词构建器"""

    def __init__(self, config_path: str = "intelligence_config.json"):
        """
        初始化提示词构建器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path

    def build_personalized_prompt(
        self,
        base_prompt: str,
        user_profile: Dict,
        memories: List[Dict],
        context_summary: str | None = None
    ) -> str:
        """
        构建个性化system prompt

        Args:
            base_prompt: 基础提示词(来自prompts.json)
            user_profile: 用户画像
            memories: 相关记忆列表
            context_summary: 上下文摘要(可选)

        Returns:
            个性化提示词
        """
        try:
            # 解析基础prompt
            try:
                base_config = json.loads(base_prompt)
            except:
                # 如果解析失败,使用默认配置
                base_config = {
                    "系统提示": "以傲娇且温柔的语气与用户互动,适当使用颜文字,每句话结尾加'喵'",
                    "互动方式": "简洁明了的回应"
                }

            # 构建个性化部分
            personalized_sections = []

            # 1. 用户画像部分
            profile_section = self._build_profile_section(user_profile)
            if profile_section:
                personalized_sections.append(profile_section)

            # 2. 记忆部分
            memory_section = self._build_memory_section(memories)
            if memory_section:
                personalized_sections.append(memory_section)

            # 3. 上下文摘要部分
            if context_summary:
                personalized_sections.append(f"## 对话摘要\n{context_summary}")

            # 4. 组合最终prompt
            if personalized_sections:
                personalized_content = "\n\n".join(personalized_sections)
                final_prompt = f"""{base_config.get("系统提示", "")}

## 用户个性化信息
{personalized_content}

请基于以上信息,调整你的回复风格和内容,使其更贴合该用户的特点。
"""
            else:
                final_prompt = base_config.get("系统提示", "")

            logging.debug(f"构建个性化prompt, 长度={len(final_prompt)}")
            return final_prompt

        except Exception as e:
            logging.error(f"构建个性化prompt失败: {e}", exc_info=True)
            # 出错时返回基础prompt
            return base_prompt

    def _build_profile_section(self, user_profile: Dict) -> str:
        """
        构建用户画像部分

        Args:
            user_profile: 用户画像

        Returns:
            画像部分的文本
        """
        sections = []

        # 兴趣标签
        interests = user_profile.get('interests', [])
        if interests:
            sections.append(f"- 兴趣爱好: {', '.join(interests[:5])}")

        # 交互风格
        interaction_style = user_profile.get('interaction_style', {})
        familiarity = user_profile.get('familiarity_level', 0.5)

        style_desc = []
        if familiarity > 0.7:
            style_desc.append("非常熟悉,可以使用更轻松随意的语气")
        elif familiarity > 0.4:
            style_desc.append("比较熟悉,保持友好但适度的距离")
        else:
            style_desc.append("初次接触,保持礼貌和热情")

        if interaction_style.get('humor', 0.5) > 0.7:
            style_desc.append("喜欢幽默风趣的表达")

        if style_desc:
            sections.append(f"- 交互特点: {'; '.join(style_desc)}")

        # 回复长度偏好
        length_pref = user_profile.get('preferred_response_length', 'medium')
        length_map = {
            'short': '简短精炼(15-35 token)',
            'medium': '适中长度(35-60 token)',
            'long': '详细阐述(60-100 token)'
        }
        if length_pref in length_map:
            sections.append(f"- 回复长度: {length_map[length_pref]}")

        # Emoji使用
        emoji_usage = user_profile.get('emoji_usage', 0.5)
        if emoji_usage > 0.7:
            sections.append("- 适当使用emoji和颜文字")
        elif emoji_usage < 0.3:
            sections.append("- 少用emoji,保持简洁")

        if sections:
            return "### 用户特征\n" + "\n".join(sections)
        return ""

    def _build_memory_section(self, memories: List[Dict]) -> str:
        """
        构建记忆部分

        Args:
            memories: 记忆列表

        Returns:
            记忆部分的文本
        """
        if not memories:
            return ""

        memory_items = []
        for mem in memories[:3]:  # 只显示top 3
            mem_type = mem.get('memory_type', 'fact')
            content = mem.get('content', '')

            type_map = {
                'preference': '偏好',
                'event': '事件',
                'agreement': '约定',
                'fact': '事实'
            }

            type_name = type_map.get(mem_type, mem_type)
            memory_items.append(f"- [{type_name}] {content}")

        if memory_items:
            return "### 重要记忆\n" + "\n".join(memory_items)
        return ""
