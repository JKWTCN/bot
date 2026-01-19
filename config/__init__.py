"""
配置缓存模块
提供配置文件缓存功能
"""
from config.config_cache import (
    config_cache,
    get_bot_config,
    get_intelligence_config,
    get_setting,
    get_static_setting
)

__all__ = [
    'config_cache',
    'get_bot_config',
    'get_intelligence_config',
    'get_setting',
    'get_static_setting'
]
