# Bilibili 动态订阅应用

对应 Python 模块：`application/bilibili_dynamic_subscription_application.py`

## 功能简介

本应用用于订阅 Bilibili UP 主的动态和直播状态，并通过 OneBot 群消息自动推送更新。

中文指令必须带有 `static_setting.json` 中配置的 `bot_name`，并以 bot 名开头；
以 `/` 开头的指令不需要 bot 名。下文使用默认名称“乐可”展示中文示例。

主要功能包括：

- Bilibili App 扫码登录；
- 按群订阅 UP 主；
- 查看和删除本群订阅；
- 自动轮询动态及开播状态；
- 动态 ID 缓存与重复推送防护；
- 动态类型、抽奖内容和正则表达式过滤；
- `@全体成员` 和 `@订阅者` 提醒；
- 同一 UID 跨群合并请求。

首次添加订阅时只会记录当前动态快照，不会补发 UP 主的历史动态。

## 安装依赖

应用生成登录二维码需要 `qrcode`：

```bash
pip3 install "qrcode>=7.4"
```

也可以重新安装项目依赖：

```bash
pip3 install -r control/requirements.txt
```

安装完成后需要重启机器人。

## Bilibili 扫码登录

机器人开发者私聊机器人发送：

```text
/bili_login
```

也可以使用中文指令：

```text
<bot_name> B站登录
```

机器人将发送登录二维码。使用 Bilibili App 扫描并在手机中确认后，机器人会校验登录状态并保存 Cookie。

登录限制：

- 仅 `static_setting.json` 中 `developers_list` 配置的机器人开发者可以登录；
- 登录指令必须在私聊中使用；
- 群聊执行登录指令时只会返回私聊提示；
- 同一时间只允许进行一个扫码登录流程；
- 二维码超时或失效后需要重新执行指令。

登录凭据存放在：

```text
db/bilibili_dynamic.db
```

凭据不会写入 `static_setting.json`。登录成功后，所有已有订阅会在下次 OneBot 心跳时立即恢复检查。

## 订阅指令

### 添加或更新订阅

```text
<bot_name> 订阅动态 <UID> [过滤器或选项...]
```

英文别名：

```text
/bili_sub <UID> [过滤器或选项...]
```

示例：

```text
乐可 订阅动态 123456
乐可 订阅动态 123456 lottery forward
乐可 订阅动态 123456 video 关注
乐可 订阅动态 123456 at_sub
```

对已经订阅的 UID 再次执行该指令，会更新过滤条件和提醒设置，并重新建立当前动态快照。

### 查看本群订阅

```text
<bot_name> 订阅列表
```

英文别名：

```text
/bili_sub_list
```

### 删除订阅

```text
<bot_name> 订阅删除 <UID>
```

英文别名：

```text
/bili_sub_del <UID>
```

订阅以群为单位保存，查看和删除操作只影响当前群。

## 过滤器

订阅指令支持以下保留过滤器：

| 过滤器              | 效果               |
| ------------------- | ------------------ |
| `forward`         | 过滤转发动态       |
| `lottery`         | 过滤抽奖动态       |
| `video`           | 过滤视频投稿动态   |
| `article`         | 过滤专栏动态       |
| `draw`            | 过滤图文动态       |
| `live`            | 关闭开播提醒       |
| `forward_lottery` | 过滤转发的抽奖动态 |

不属于上述保留字和提醒选项的参数会被当作正则表达式，用于匹配动态标题及正文。匹配成功的动态不会推送。

例如：

```text
乐可 订阅动态 123456 lottery 关注|抽奖
```

该订阅会过滤抽奖动态，以及标题或正文中包含“关注”或“抽奖”的动态。

无效正则表达式会被拒绝，不会更新订阅。

## 提醒选项

| 选项           | 效果                             | 权限要求               |
| -------------- | -------------------------------- | ---------------------- |
| `at_sub`     | 推送时`@` 当前指令发送者       | 所有群成员             |
| `unat_sub`   | 取消对当前指令发送者的`@` 提醒 | 所有群成员             |
| `at_all`     | 动态及直播推送时`@全体成员`    | 群管理员或机器人开发者 |
| `live_atall` | 仅开播推送时`@全体成员`        | 群管理员或机器人开发者 |

机器人自身需要具有相应的群管理权限，否则 `@全体成员` 可能无法生效。

## 配置项

以下配置均从 `static_setting.json` 读取，未配置时使用默认值：

| 配置项                                  |  默认值 | 说明                                            |
| --------------------------------------- | ------: | ----------------------------------------------- |
| `bilibili_cookie`                     |      空 | 手动配置的完整 Bilibili Cookie                  |
| `bilibili_sessdata`                   |      空 | 仅配置 SESSDATA 时的兼容选项                    |
| `bilibili_dynamic_check_interval`     | `300` | 每个 UID 的动态检查间隔，单位为秒，最小 30 秒   |
| `bilibili_dynamic_heartbeat_throttle` |  `30` | OneBot 心跳触发节流时间，单位为秒，最小 5 秒    |
| `bilibili_dynamic_request_timeout`    |  `20` | Bilibili HTTP 请求超时时间，单位为秒，最小 3 秒 |
| `bilibili_dynamic_limit`              |   `5` | 单次检查最多推送的动态数量                      |
| `bilibili_recent_dynamic_cache`       |  `30` | 每条订阅保存的最近动态 ID 数量                  |
| `bilibili_dynamic_text_limit`         | `500` | 推送正文的最大字符数，最小 100                  |

扫码登录保存的凭据优先于 `static_setting.json` 中手动填写的 Cookie。

## 数据存储

应用使用独立 SQLite 数据库：

```text
db/bilibili_dynamic.db
```

其中包含：

- `bilibili_dynamic_subscription`：群订阅、过滤条件、提醒设置、最近动态 ID 和直播状态；
- `bilibili_credential`：扫码登录获得的 Cookie。

`db/` 已被项目 `.gitignore` 排除，不应将登录凭据提交到版本库。

## 推送机制

应用通过 OneBot `heartbeat` 元事件触发检查：

1. 从数据库查询已经到达检查时间的订阅；
2. 按 UID 合并多个群的订阅，避免重复请求同一 UP 主；
3. 拉取最新动态和直播状态；
4. 使用最近动态 ID 判断是否为新动态；
5. 应用类型和正则过滤规则；
6. 按发布时间顺序推送文字、链接和最多三张图片；
7. 更新动态缓存、直播状态和下次检查时间。

Bilibili 请求失败时不会覆盖已有动态或直播状态，并会在稍后重试。

## 常见问题

### 提示 HTTP 412 或错误码 -352

这是 Bilibili 风控拦截。请由机器人开发者私聊执行：

```text
/bili_login
```

确认登录成功后再添加或等待已有订阅恢复检查。

### 没有收到二维码

请检查：

- 是否在私聊中执行登录指令；
- 当前 QQ 是否位于 `developers_list`；
- 是否已经安装 `qrcode`；
- OneBot 实现是否支持发送 Base64 图片。

### 登录成功但没有推送

请检查：

- OneBot 是否持续上报 `heartbeat` 元事件；
- 当前群是否已经添加订阅；
- 过滤规则是否过滤了对应动态；
- `bilibili_dynamic_check_interval` 是否设置过大；
- 日志中是否存在 Bilibili API 或消息发送错误。

### 为什么订阅后没有立即发送最新动态

这是预期行为。首次订阅会把当前动态记录为初始快照，防止历史内容集中刷屏。只有订阅后发布的新动态才会推送。
