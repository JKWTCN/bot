import json
import os
from enum import Enum


class DataType(Enum):
    DATA_UNKNOW = 0
    DATA_INT = 1
    DATA_STRING = 2
    DATA_BOOL = 3


class GroupConfigError(Enum):
    NO_OPPATION_Type = 0
    UNKNOW_DATA_TYPE = 1
    UNKNOW_OPPATION_ARG = 2


# 默认配置
default_configs = {
    "catgirl": [],  # 猫娘群友
    "kotomitako": [],  # 香香软软小南梁群友
    "blacklist": [],  # 黑名单群友
    "no_reply_list": [],  # 不回复的群友
    "cold_group": False,  # 冷群回复开关
    "cold_group_num_out": 5,  # 多少句触发冷群
    "cold_group_time_out": 300,  # 多久触发冷群
    "group_decrease_reminder": True,  # 退群提醒
    "cat_day_date": -1,  # 猫猫日日期，-1表示不设置
    "cat_day_ignore_admin": True,  # 猫猫日忽略管理员
    "kick_time_sec": -1,  # 踢掉多久没发言的群友，-1表示不踢
    "sensitive_words": [],  # 敏感词，发出会禁言
    "sensitive_ban_sec": 60,  # 敏感词禁言秒数
    "sensitive_withdrawn": False,  # 敏感词是否撤回
    "bilibili_parsing": True,  # 是否解析b站小程序
    "image_parsing": False,  # 是否解析图片
    "dont_at_me": False,  # @我是否要惩罚
    "hate_at_list": [],  # 不想被艾特的群友
    "level_limit": -1,  # 入群等级最低等级限制
    "bing_search":False#群搜索功能
}

intOptionType = [
    "catgirl",
    "kotomitako",
    "blacklist",
    "no_reply_list",
    "cold_group_num_out",
    "cold_group_time_out",
    "cat_day_date",
    "kick_time_sec",
    "sensitive_ban_sec",
    "hate_at_list",
    "level_limit"
]
stringOptionType = ["sensitive_words"]
boolOptionType = [
    "cold_group",
    "group_decrease_reminder",
    "cat_day_ignore_admin",
    "sensitive_withdrawn",
    "bilibili_parsing",
    "image_parsing",
    "dont_at_me",
    "bing_search"
]


def getArgType(optionType: str):
    if optionType in intOptionType:
        return DataType.DATA_INT
    elif optionType in stringOptionType:
        return DataType.DATA_STRING
    elif optionType in boolOptionType:
        return DataType.DATA_BOOL
    else:
        return DataType.DATA_UNKNOW


def set_config(
    config_name,
    value,
    group_id,
):
    """
    设置配置项的值并更新JSON配置文件
    :param config_name: 要设置的配置项名称
    :param value: 要设置的值
    :param group_id: 群组ID
    """
    config_file = f"groups/{group_id}/config.json"

    # 如果配置目录不存在则创建
    if not os.path.exists(f"groups/{group_id}"):
        os.makedirs(f"groups/{group_id}")

    # 如果配置文件不存在则创建空字典
    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            json.dump({}, f)

    try:
        # 读取现有配置
        with open(config_file, "r") as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        config = {}

    # 更新配置值
    config[config_name] = value

    # 写回配置文件
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"无法更新配置文件: {e}")
        return False

    return True


def get_config(
    config_name: str,
    group_id: int,
):
    """从JSON配置文件中读取配置项，如果不存在则使用默认值并更新文件

    Args:
        config_name (str): 配置项的名称
        group_id (int): 群的ID

    Returns:
        _type_: 配置项的值
    """

    default_value = default_configs.get(config_name, None)
    config_file = f"groups/{group_id}/config.json"
    # 如果配置文件不存在，则创建并写入空字典
    if not os.path.exists(f"groups/{group_id}"):
        os.mkdir(f"groups/{group_id}")
    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            json.dump({}, f)
    try:
        # 读取配置文件
        with open(config_file, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError:
        # 如果文件内容不是有效的JSON，则初始化为空字典
        config = {}

    # 如果配置项不存在，则使用默认值并更新文件
    if config_name not in config and default_value != None:
        config[config_name] = default_value
        try:
            with open(config_file, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"无法更新配置文件: {e}")
    return config.get(config_name, default_value)


import json
import os
from typing import Any, Union


def manage_config(config_str: str, group_id: int):
    """
    管理配置文件，支持对不同类型的配置项进行不同操作

    :param config_str: 操作字符串，格式如 ".catgirl.get" 或 ".blacklist.append 123"
    :param config_file: 配置文件路径
    :return: 操作后的配置项值
    """
    # 解析操作字符串
    parts = config_str.split(".")
    print(parts)
    if parts[0] != "":
        return (False, GroupConfigError.NO_OPPATION_Type)
    optionType = parts[1]
    parts = parts[2].split(" ")
    if len(parts) == 1:
        optionCommand = parts[0]
        oppationArg = None
    else:
        optionCommand = parts[0]
        oppationArg = parts[1]
    print(f"设置项:{optionType} 设置命令:{optionCommand} 设置参数:{oppationArg}")
    oldArg = get_config(optionType, group_id)
    if oldArg == None:
        return (False, GroupConfigError.NO_OPPATION_Type)
    # print(type(oldArg))
    match type(oldArg):
        case _ if isinstance(oldArg, list):
            match optionCommand:
                case "get":
                    return (True, oldArg)
                case "append":
                    match getArgType(optionType):
                        case DataType.DATA_INT:
                            oppationArg = int(oppationArg)  # type: ignore
                        case DataType.DATA_STRING:
                            oppationArg = str(oppationArg)
                        case DataType.DATA_BOOL:
                            oppationArg = bool(int(oppationArg))  # type: ignore
                        case DataType.DATA_UNKNOW:
                            return (False, GroupConfigError.UNKNOW_DATA_TYPE)

                    if oppationArg not in oldArg:
                        oldArg.append(oppationArg)
                        set_config(optionType, oldArg, group_id)
                    return (True, oldArg)
                case "remove":
                    match getArgType(optionType):
                        case DataType.DATA_INT:
                            oppationArg = int(oppationArg)  # type: ignore
                        case DataType.DATA_STRING:
                            oppationArg = str(oppationArg)
                        case DataType.DATA_BOOL:
                            oppationArg = bool(int(oppationArg))  # type: ignore
                        case DataType.DATA_UNKNOW:
                            return (False, GroupConfigError.UNKNOW_DATA_TYPE)
                    if oppationArg in oldArg:
                        oldArg.remove(oppationArg)
                        set_config(optionType, oldArg, group_id)
                    return (True, oldArg)
                case _:
                    return (False, GroupConfigError.UNKNOW_OPPATION_ARG)
        case _ if isinstance(oldArg, bool):
            # print(f"{optionCommand},{optionType},{getArgType(optionType)}")
            match optionCommand:
                case "set":
                    match getArgType(optionType):
                        case DataType.DATA_INT:
                            oppationArg = int(oppationArg)  # type: ignore
                        case DataType.DATA_STRING:
                            oppationArg = str(oppationArg)
                        case DataType.DATA_BOOL:
                            oppationArg = bool(int(oppationArg))  # type: ignore
                        case DataType.DATA_UNKNOW:
                            return (False, GroupConfigError.UNKNOW_DATA_TYPE)
                    oldArg = oppationArg
                    set_config(optionType, oldArg, group_id)
                    return (True, oldArg)
                case "get":
                    return (True, oldArg)
                case _:
                    return (False, GroupConfigError.UNKNOW_OPPATION_ARG)
        case _ if isinstance(oldArg, int):
            match optionCommand:
                case "set":
                    match getArgType(optionType):
                        case DataType.DATA_INT:
                            oppationArg = int(oppationArg)  # type: ignore
                        case DataType.DATA_STRING:
                            oppationArg = str(oppationArg)
                        case DataType.DATA_BOOL:
                            oppationArg = bool(int(oppationArg))  # type: ignore
                        case DataType.DATA_UNKNOW:
                            return (False, GroupConfigError.UNKNOW_DATA_TYPE)
                    oldArg = oppationArg
                    set_config(optionType, oldArg, group_id)
                    return (True, oldArg)
                case "get":
                    return (True, oldArg)
                case _:
                    return (False, GroupConfigError.UNKNOW_OPPATION_ARG)

    # print(oldArg)


# # 使用示例
# if __name__ == "__main__":
#     example = ".kick_time_sec.get"
#     try:
#         result = manage_config(example, 916279260)
#         print(f"操作: {example} => 结果: {result} (类型: {type(result).__name__})")
#     except ValueError as e:
#         print(f"操作: {example} => 错误: {e}")
