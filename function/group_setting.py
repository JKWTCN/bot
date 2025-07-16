import json
import logging
import os


def LoadGroupSetting(settingName: str, groupId: int, default_value):
    settingPath = f"groups/{groupId}/GroupSetting.json"
    if not os.path.exists(settingPath):
        os.makedirs(os.path.dirname(settingPath), exist_ok=True)
    try:
        with open("setting.json", "r", encoding="utf-8") as file:
            setting = json.load(file)
        return setting[settingName]
    except Exception as e:
        logging.error(f"读取配置文件出错: {e}")
        DumpGroupSetting(settingName, groupId, default_value)
        return default_value


def DumpGroupSetting(settingName: str, groupId: int, value):
    settingPath = f"groups/{groupId}/GroupSetting.json"
    if not os.path.exists(settingPath):
        os.makedirs(os.path.dirname(settingPath), exist_ok=True)
    try:
        with open(settingPath, "r", encoding="utf-8") as file:
            setting = json.load(file)
    except Exception as e:
        logging.error(f"读取配置文件出错: {e}")
        setting = {}
    setting[settingName] = value
    with open(settingPath, "w", encoding="utf-8") as f:
        json.dump(setting, f, ensure_ascii=False, indent=4)
