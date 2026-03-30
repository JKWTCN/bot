# bot

基于 OneBot11 WebSocket 事件流的 QQ 群聊机器人，采用应用注册 + 调度器模式，支持聊天、娱乐、积分、群管理、入群验证、天气、B 站解析、银行利息等功能。

## 当前特性

- 消息类型支持：群聊、私聊、通知、请求、元事件
- 应用调度：按规则匹配应用，支持阻断式链路和异步任务执行
- 功能模块：
  - 聊天与复读相关（群聊、私聊、复读检测、随机回复）
  - 娱乐与互动（塔罗、漂流瓶、随机图、抽签、答案之书等）
  - 群管理（入群验证、敏感词、艾特管理、加精、退群通知）
  - 积分经济（签到、积分抽奖、银行、利息更新）
  - 工具能力（天气、系统状态、B 站链接解析、翻译）
- 数据层：SQLite + WAL + 连接池，包含 bot 主库与智能记忆库
- 智能模块：独立 intelligence 子系统，支持上下文窗口、长期记忆、用户画像

## 运行环境

- Python 3.10 及以上（建议 3.11）
- 可访问 OneBot11 WebSocket 服务（例如 NapCat）
- 可选：本地或远端 AI 服务（OpenAI 兼容或 Ollama）

## 快速开始

1. 克隆并进入项目

```bash
git clone <your-repo-url>
cd bot
```

2. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r control/requirements.txt
```

3. 准备配置文件

- 修改 `setting.json`（运行时动态配置）
- 修改 `static_setting.json`（静态配置、密钥和账号）
- 按需修改 `intelligence_config.json`（记忆与画像策略）

4. 启动机器人

```bash
python main.py
```

## 配置说明

### 1) setting.json（动态配置）

常用键位（示例）：

- `napcat_wclient_port`：OneBot11 WebSocket 客户端端口（默认常见为 27431）
- `napcat_hserver_port`：NapCat HTTP 服务端口
- `ollama_port`：本地 Ollama 端口
- `debug_mode`：调试日志开关
- `group_list`：启用群列表
- `use_local_ai`：是否优先使用本地 AI
- `gambling_limit`、`defense_times`、`timeout`：功能相关阈值

### 2) static_setting.json（静态配置）

常用键位（示例）：

- `developers_list`：开发者/管理员账号
- `bot_id`、`bot_name`：机器人标识
- `meme_path`：本地图片素材目录
- `open_ai_api_key`、`open_ai_base_url`、`open_ai_model`：OpenAI 兼容模型配置
- `open_weather_map_api_key`、`tushare_token`：第三方服务密钥

### 3) intelligence_config.json（智能配置）

- `context_window`：上下文窗口最小/最大长度
- `memory`：记忆抽取频率和阈值
- `personalization`：画像缓存与 token 上限

## 数据库说明

程序启动时会自动执行数据库初始化（`bot.db`、`bot_intelligence.db`）并开启 WAL 优化。

如需手动初始化（首次部署或迁移）：

```bash
sqlite3 bot.db < control/init_database.sql
sqlite3 bot.db < database/bot_indexes.sql
sqlite3 bot_intelligence.db < database/intel_indexes.sql
```

## 启动与运维

### 前台运行（推荐调试）

```bash
python main.py
```

### 使用 control 脚本

- `control/start.sh`、`control/restart.sh`、`control/stop.sh` 默认包含固定路径和端口，请先按你的机器环境修改。
- `control/win_start.bat` 默认使用 `..\venv\Scripts\python.exe`，Windows 下请确认虚拟环境路径一致。

## 目录结构（精简）

```text
bot/
├── main.py
├── registered_application_list.py
├── setting.json
├── static_setting.json
├── intelligence_config.json
├── application/          # 业务应用（按功能拆分）
├── function/             # 常用功能函数与数据库操作
├── schedule/             # 调度器与应用注册框架
├── data/                 # 消息对象与枚举定义
├── database/             # 连接池、初始化与索引脚本
├── intelligence/         # 智能记忆与画像模块
├── control/              # 启停与数据库初始化脚本
└── log/                  # 运行日志
```

## 故障排查

- 无法连接 WebSocket：确认 OneBot11 已启动，且端口与 `setting.json` 保持一致
- 启动即报依赖错误：确认已安装 `control/requirements.txt`，并在正确虚拟环境中运行
- 功能不触发：确认对应群号在 `group_list`，且未被配置规则拦截
- 智能相关报错：检查 `intelligence_config.json` 和 `bot_intelligence.db` 权限
- 图片/资源发送失败：检查 `meme_path`、`res/`、`figs/` 文件读写权限

## 安全建议

- 不要将真实 API Key、Cookie、邮箱口令直接提交到仓库
- 推荐使用环境变量或本地私有配置覆盖敏感信息
- 如果密钥已经提交过历史记录，请立即轮换并清理历史
