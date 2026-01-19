"""
配置缓存系统
避免重复读取配置文件
"""
import json
import asyncio
from typing import Dict, Any, Callable
from datetime import datetime, timedelta


class ConfigCache:
    """配置缓存管理器"""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._ttl = timedelta(seconds=ttl_seconds)

    async def get(self, key: str, loader: Callable) -> Any:
        """
        获取配置，如果缓存过期则重新加载

        Args:
            key: 缓存键
            loader: 加载函数
        """
        async with self._lock:
            now = datetime.now()

            # 检查缓存
            if key in self._cache:
                if now - self._timestamps[key] < self._ttl:
                    return self._cache[key]

            # 重新加载
            value = loader()
            self._cache[key] = value
            self._timestamps[key] = now
            return value

    def invalidate(self, key: str):
        """使缓存失效"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def clear_all(self):
        """清空所有缓存"""
        self._cache.clear()
        self._timestamps.clear()


# 全局单例
config_cache = ConfigCache(ttl_seconds=300)


# 便捷函数
async def get_bot_config() -> dict:
    """获取机器人配置"""
    return await config_cache.get(
        "bot_config",
        lambda: json.load(open("static_setting.json", "r", encoding="utf-8"))
    )


async def get_intelligence_config() -> dict:
    """获取智能配置"""
    return await config_cache.get(
        "intelligence_config",
        lambda: json.load(open("intelligence_config.json", "r", encoding="utf-8"))
    )


async def get_setting(key: str, default=None):
    """获取setting.json中的配置"""
    async def load_setting():
        return json.load(open("setting.json", "r", encoding="utf-8"))

    config = await config_cache.get("setting", load_setting)
    return config.get(key, default)


async def get_static_setting(key: str, default=None):
    """获取static_setting.json中的配置"""
    config = await get_bot_config()
    return config.get(key, default)
