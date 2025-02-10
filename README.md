# QQ群聊机器人

一个基于WebSocket的QQ群聊机器人,支持多种娱乐和管理功能。

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

* [main.py](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) - 主程序入口
* [chat.py](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) - 聊天相关功能
* [bot\_database.py](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) - 数据库操作
* [tools.py](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) - 工具函数
* [Class](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) - 类定义
* [res](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) - 资源文件
* [log](vscode-file://vscode-app/c:/Users/15056/AppData/Local/Programs/Microsoft%20VS%20Code/resources/app/out/vs/code/electron-sandbox/workbench/workbench.html) - 日志文件

## 贡献

欢迎提交 Issue 和 Pull Request
