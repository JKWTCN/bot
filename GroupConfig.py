import json
import os


default_configs = {
    "catgirl": [],
    "blacklist": [],
    "no_reply_list": [],
    "cold_group": False,
    "cold_group_num_out": 5,
    "cold_group_time_out": 300,
    "group_decrease_reminder": True,
    "cat_day_switch": False,
    "cat_day_date": 25,
    "cat_day_ignore_admin": True,
}


def get_config(
    config_name,
    group_id,
):
    """
    从JSON配置文件中读取配置项，如果不存在则使用默认值并更新文件
    :param config_name: 要读取的配置项名称
    :param default_value: 配置项的默认值（如果不存在）
    :param config_file: 配置文件路径
    :return: 配置项的值
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

# 默认配置
default_configs = {
    "catgirl": [],
    "blacklist": [],
    "no_reply_list": [],
    "cold_group": False,
    "cold_group_num_out": 5,
    "cold_group_time_out": 300,
    "group_decrease_reminder": True,
    "cat_day_switch": False,
    "cat_day_date": 25,
    "cat_day_ignore_admin": True,
}


def manage_config(config_str: str, group_id: int) -> Any:
    """
    管理配置文件，支持对不同类型的配置项进行不同操作

    :param config_str: 操作字符串，格式如 ".catgirl.get" 或 ".blacklist.append 123"
    :param config_file: 配置文件路径
    :return: 操作后的配置项值
    """
    # 解析操作字符串
    parts = config_str.split(".")
    if not parts or not parts[0].startswith("."):
        raise ValueError("无效的操作格式，应以 .config_name 开头")

    # 提取配置项名称和操作
    config_path = parts[0][1:]  # 去掉开头的点
    operation = parts[1] if len(parts) > 1 else "get"
    operation_args = parts[2:] if len(parts) > 2 else []

    config_file = f"groups/{group_id}/config.json"
    # 如果配置文件不存在，则创建并写入空字典
    if not os.path.exists(f"groups/{group_id}"):
        os.mkdir(f"groups/{group_id}")
    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            json.dump({}, f)

    # 加载配置文件
    if not os.path.exists(config_file):
        with open(config_file, "w") as f:
            json.dump({}, f)
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        config = {}

    # 如果配置项不存在，使用默认值
    if config_path not in config:
        if config_path not in default_configs:
            raise ValueError(f"未知的配置项: {config_path}")
        config[config_path] = default_configs[config_path]

    # 获取当前值
    current_value = config[config_path]

    # 根据类型执行操作
    if isinstance(current_value, list):
        if operation == "get":
            pass  # 直接返回当前值
        elif operation == "append":
            if not operation_args:
                raise ValueError("append 操作需要一个参数")
            item = operation_args[0]
            if item not in current_value:
                current_value.append(item)
        elif operation == "delete":
            if not operation_args:
                raise ValueError("delete 操作需要一个参数")
            item = operation_args[0]
            if item in current_value:
                current_value.remove(item)
        else:
            raise ValueError(f"列表类型不支持的操作: {operation}")
    elif isinstance(current_value, bool):
        if operation == "get":
            pass  # 直接返回当前值
        elif operation == "set":
            if not operation_args:
                raise ValueError("set 操作需要一个参数 (True/False)")
            value_str = operation_args[0].lower()
            if value_str == "true":
                current_value = True
            elif value_str == "false":
                current_value = False
            else:
                raise ValueError("布尔值只能设置为 True 或 False")
        else:
            raise ValueError(f"布尔类型不支持的操作: {operation}")
    else:  # 其他类型 (int, str, etc.)
        if operation == "get":
            pass  # 直接返回当前值
        elif operation == "set":
            if not operation_args:
                raise ValueError("set 操作需要一个参数")
            # 尝试转换为原始类型
            if isinstance(default_configs[config_path], int):
                try:
                    current_value = int(operation_args[0])
                except ValueError:
                    raise ValueError(f"配置项 {config_path} 需要整数值")
            else:
                current_value = operation_args[0]
        else:
            raise ValueError(f"此类型不支持的操作: {operation}")

    # 更新配置并保存
    config[config_path] = current_value
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)

    return current_value


# 使用示例
if __name__ == "__main__":
    # # 示例默认配置

    # # 获取用户想查询的配置项
    # config_name = input("请输入要查询的配置项名称: ")
    # group_id = 123
    # # 获取配置值（如果不存在则使用默认值）

    # value = get_config(config_name, group_id)

    # print(f"配置项 '{config_name}' 的值为: {value}")
    example = ".catgirl.get"
    try:
        result = manage_config(example, 123)
        print(f"操作: {example} => 结果: {result} (类型: {type(result).__name__})")
    except ValueError as e:
        print(f"操作: {example} => 错误: {e}")
