# QQ群聊机器人

一个基于WebSocket的遵循OneBot11的群聊机器人,支持多种娱乐和管理功能。

## 主要功能

* 💬 群聊对话 - 支持AI模型对话,包含冷场检测
* 🎮 娱乐功能
  * 俄罗斯轮盘
  * 塔罗牌
  * 漂流瓶
  * 大头菜交易
  * 积分系统
* 👥 群管理
  * 成员验证
  * 退群提醒
  * 不受欢迎名单
* 📊 数据统计
  * 聊天记录统计
  * 活跃度排行
  * 系统状态监控

## 安装

**# 安装依赖**

```
pip install -r requirements.txt
```

## 配置

1. 修改 [setting.json](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) 配置文件

   ```
   {
       "developers_list": [
           1234567890<管理员账号>
       ],
       "kick_time": {
           "需要定时踢不活跃群的群号": 123<单位秒>,
       },
       "bot_id": 12345670<机器人账号>,
       "admin_group_main": 12345670<测试群>,
       "blacklist": {
           "黑名单账号": "黑名单行为",
       },
       "timeout": 5,
       "defense_times": 100,
       "group_list": [
       ],
       "is_thanos": false,
       "thanos_time": 0,
       "kohlrabi_price": 0,
       "kohlrabi_version": 1,
       "gambling_limit": 5000,
       "alarm_member": [
           {
               "user_id": 1234567890<需要定时提醒的群友账号>,
               "time_hour": 8<定时提醒的时>,
               "time_minute": 0<定时提醒的分>,
               "group_id": 1234567890<定时提醒的群>,
               "text": "提醒文字",
               "time": 0
           },
           {
               "user_id": 1234567890<需要定时提醒的群友账号>,
               "time_hour": 8<定时提醒的时>,
               "time_minute": 0<定时提醒的分>,
               "group_id": 1234567890<定时提醒的群>,
               "text": "提醒文字",
               "time": 0,
               "res": "提醒一同发送的图片目录"
           },
       ],
       "cold_group_king": [

       ],
       "last_update_time": 0,
       "cold_group_king_setting": {
           "num_out": 5,
           "time_out": 300
       },
       "need_cold_reply_list": [
       ],
       "group_decrease_reply_list": [
       ],
       "bleak_admin": [],
       "other_bots": [
           <其他BOT白名单账号>
       ],
       "meme_path": "随机图片的本地文件夹地址",
       "delete_message_list": [],
       "email": {
           "user": "",
           "password": "",
           "host": "",
           "rev_email": ""
       },
       "boring": [
       ],
       "model": "deepseek-r1:1.5b",
       "think_display": false
   }
   ```

2. 初始化数据库:

   ```
   sqlite3 bot.db < init_database.sql
   ```

## 启动

### Linux

```
sh start.sh
```

### Windows

```
win_start.bat
```

## 目录结构

```
bot/├── main.py                # 主程序入口
    ├── bot_database.py        # 数据库操作
    ├── chat.py               # 聊天功能模块
    ├── chat_record.py        # 聊天记录
    ├── drifting_bottles.py   # 漂流瓶功能
    ├── e_mail.py            # 邮件功能
    ├── easter_egg.py        # 彩蛋功能
    ├── group_operate.py     # 群操作功能
    ├── kohlrabi.py          # 大头菜交易功能
    ├── level.py            # 等级系统
    ├── luck_dog.py         # 抽奖功能
    ├── private.py          # 私聊功能
    ├── random_meme.py      # 随机表情包
    ├── rankings.py         # 排行榜功能
    │
    ├── Class/              # 类定义目录
    │   ├── __init__.py
    │   ├── Group_member.py # 群成员类
    │   └── Ranking.py      # 排行榜类
    │
    ├── res/               # 资源目录
    ├── vcode/         # 验证码资源
    │
    ├── log/              # 日志目录
    │
    ├── setting.json      # 配置文件
    └── requirements.txt  # 项目依赖
```
