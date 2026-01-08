"""
用户画像特征提取器
从用户消息中提取特征,更新用户画像
"""

import json
import logging
import re
from typing import Dict, List


class ProfileExtractor:
    """用户画像特征提取器"""

    def __init__(self):
        """初始化特征提取器"""
        # 兴趣关键词库
        self.interest_keywords = {
            '编程': ['代码', '编程', '开发', '程序', '算法', 'bug', 'git', 'python', 'java', '前端'],
            '游戏': ['游戏', '玩', '攻略', '副本', '段位', '排位', '王者荣耀', '原神', 'steam'],
            '学习': ['学习', '考试', '作业', '课程', '知识', '研究', '论文'],
            '音乐': ['音乐', '歌曲', '歌手', '听歌', '吉他', '钢琴', '演唱会'],
            '运动': ['运动', '健身', '跑步', '篮球', '足球', '游泳', '瑜伽'],
            '美食': ['吃', '美食', '餐厅', '菜', '做饭', '奶茶', '咖啡'],
            '影视': ['电影', '电视剧', '动漫', '番剧', '综艺', '剧集'],
            '旅行': ['旅行', '旅游', '景点', '出差', '度假', '酒店']
        }

        # 时间偏好关键词
        self.time_keywords = {
            '早上': ['早上', '清晨', '早晨', '上午'],
            '下午': ['下午', '午后'],
            '晚上': ['晚上', '夜间', '今晚', '深夜'],
            '周末': ['周末', '星期六', '星期日', '周六', '周日'],
        }

        # 语气风格关键词
        self.tone_keywords = {
            'formal': ['请', '谢谢', '您好', '麻烦', '请问'],
            'casual': ['哈哈', '嘿嘿', '哎', '嗯嗯', '噢噢', '哇'],
            'humor': ['笑死', '哈哈', '嘿嘿', '搞笑', '逗', '梗']
        }

    def extract_from_message(self, message: str, user_id: int) -> Dict:
        """
        从消息中提取特征

        Args:
            message: 消息内容
            user_id: 用户ID

        Returns:
            提取的特征字典
        """
        features = {
            'interests': [],
            'time_preference': None,
            'tone_style': {'formality': 0.5, 'humor': 0.5},
            'emoji_usage': 0.0
        }

        # 1. 提取兴趣
        features['interests'] = self._extract_interests(message)

        # 2. 提取时间偏好
        features['time_preference'] = self._extract_time_preference(message)

        # 3. 提取语气风格
        features['tone_style'] = self._extract_tone_style(message)

        # 4. 计算emoji使用频率
        features['emoji_usage'] = self._calculate_emoji_usage(message)

        return features

    def _extract_interests(self, message: str) -> List[str]:
        """提取兴趣标签"""
        interests = []

        for interest, keywords in self.interest_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    if interest not in interests:
                        interests.append(interest)
                    break

        return interests

    def _extract_time_preference(self, message: str) -> str | None:
        """提取时间偏好"""
        for time_period, keywords in self.time_keywords.items():
            for keyword in keywords:
                if keyword in message:
                    return time_period
        return None

    def _extract_tone_style(self, message: str) -> Dict[str, float]:
        """提取语气风格"""
        style = {'formality': 0.5, 'humor': 0.5}

        # 计算正式度
        formal_count = sum(1 for kw in self.tone_keywords['formal'] if kw in message)
        if formal_count > 0:
            style['formality'] = min(1.0, 0.5 + formal_count * 0.15)

        # 计算幽默度
        humor_count = sum(1 for kw in self.tone_keywords['humor'] if kw in message)
        if humor_count > 0:
            style['humor'] = min(1.0, 0.5 + humor_count * 0.2)

        # 检查非正式语气
        casual_count = sum(1 for kw in self.tone_keywords['casual'] if kw in message)
        if casual_count > 0:
            style['formality'] = max(0.0, style['formality'] - casual_count * 0.1)

        return style

    def _calculate_emoji_usage(self, message: str) -> float:
        """计算emoji使用频率"""
        # 检测emoji模式
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+"
        )

        emoji_count = len(emoji_pattern.findall(message))
        message_length = len(message)

        if message_length == 0:
            return 0.0

        # 简单的频率计算
        frequency = emoji_count / max(1, message_length / 10)  # 每10个字符的emoji数
        return min(1.0, frequency)

    def merge_with_existing_profile(
        self,
        existing_profile: Dict,
        new_features: Dict
    ) -> Dict:
        """
        将新特征合并到现有画像中

        Args:
            existing_profile: 现有画像
            new_features: 新提取的特征

        Returns:
            更新后的画像
        """
        updates = {}

        # 1. 合并兴趣标签
        existing_interests = set(existing_profile.get('interests', []))
        new_interests = set(new_features.get('interests', []))
        merged_interests = existing_interests | new_interests  # 并集

        if len(merged_interests) > len(existing_interests):
            updates['interests'] = list(merged_interests)

        # 2. 更新语气风格(加权平均)
        existing_style = existing_profile.get('interaction_style', {'formality': 0.5, 'humor': 0.5})
        new_style = new_features.get('tone_style', {'formality': 0.5, 'humor': 0.5})

        # 使用0.9的权重保留旧值,0.1的权重接受新值
        merged_style = {
            'formality': existing_style.get('formality', 0.5) * 0.9 + new_style.get('formality', 0.5) * 0.1,
            'humor': existing_style.get('humor', 0.5) * 0.9 + new_style.get('humor', 0.5) * 0.1
        }

        if abs(merged_style['formality'] - existing_style.get('formality', 0.5)) > 0.05:
            updates['interaction_style'] = merged_style

        # 3. 更新emoji使用频率
        existing_emoji = existing_profile.get('emoji_usage', 0.5)
        new_emoji = new_features.get('emoji_usage', 0.5)
        merged_emoji = existing_emoji * 0.95 + new_emoji * 0.05

        if abs(merged_emoji - existing_emoji) > 0.05:
            updates['emoji_usage'] = merged_emoji

        return updates
