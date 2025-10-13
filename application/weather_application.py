import re
from data.application.group_message_application import GroupMessageApplication
from data.application.application_info import ApplicationInfo
from data.enumerates import ApplicationCostType
from data.message.group_message_info import GroupMessageInfo
from function.say import ReplySay
import requests
from pypinyin import lazy_pinyin
from tools.tools import load_setting,load_static_setting
import logging


def chinese_to_pinyin(city_name):
    """将中文转换为拼音"""
    pinyin_list = lazy_pinyin(city_name)
    return ''.join(pinyin_list)

def is_chinese(string):
    """检查字符串是否包含中文字符"""
    for char in string:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def get_weather(city,city_raw):
    api_key = load_static_setting("open_weather_map_api_key","")
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&lang=zh_cn'  # 设置API请求的url
    print(url)
    response = requests.get(url,timeout=300)  # 发起GET请求获取天气信息
    data = response.json()  # 将返回的json数据转换为字典格式
    
    if data['cod'] == 200:
        weather = data['weather'][0]['description']  # 天气描述
        temp = data['main']['temp'] - 273.15  # 温度（转换为摄氏度）
        humidity = data['main']['humidity']  # 湿度
        wind_speed = data['wind']['speed']  # 风速
        logging.info(f"获取到{city}的天气数据：{data}")
        if city != city_raw:
            return f'{city_raw}的天气：{weather}\n温度：{temp:.2f}℃\n湿度：{humidity}%\n风速：{wind_speed}m/s 喵'
        else:
            return f'{city}的天气：{weather}\n温度：{temp:.2f}℃\n湿度：{humidity}%\n风速：{wind_speed}m/s 喵'
    else:
        return('未找到该城市的天气信息喵')


def extract_city_robust(text):
    pattern = r"\s*([^，,的]+?)\s*的天气"
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

class WeatherApplication(GroupMessageApplication):
    def __init__(
        self,
    ):
        applicationInfo = ApplicationInfo("天气应用", "获取特定城市的天气")
        super().__init__(applicationInfo, 50, False, ApplicationCostType.NORMAL)

    async def process(self, message: GroupMessageInfo):
        city_raw = extract_city_robust(message.plainTextMessage)
        city = city_raw
        if is_chinese(city):
            city = chinese_to_pinyin(city)
        weather_info = get_weather(city,city_raw)
        await ReplySay(message.websocket, message.groupId, message.messageId,weather_info)

    def judge(self, message: GroupMessageInfo) -> bool:
        city = extract_city_robust(message.plainTextMessage)
        if city:
            return True
        return False

