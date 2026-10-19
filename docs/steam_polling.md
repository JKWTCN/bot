# Steam 状态轮询

自动轮询前先通过 OneBot `get_group_list` 确认 bot 仍在群里，再通过
`get_group_member_list` 获取该群实际成员。只有仍在群内的绑定用户会触发
Steam 状态请求、状态提醒和成就提醒，缓冲期结束的退出提醒也使用同一轮校验结果。

名单查询失败时跳过相应群，本轮不请求 Steam、不推送、不删除绑定。
确认 bot 或用户离群后保留绑定，清理旧状态、待发送的退出提醒及成就快照；
回群后重新建立基线，避免补发离群期间的提醒。每轮每个群只查询一次成员名单。

同一 Steam ID 的多个有效绑定共用状态请求，每次最多批量查询 100 个不同 ID。
接口限制见 [Steam 官方文档](https://partner.steamgames.com/doc/webapi/ISteamUser#GetPlayerSummaries)。

## 配置

配置写在 `static_setting.json`：

| 配置 | 默认值 | 含义 |
| --- | --- | --- |
| `steam_poll_mode` | `smart` | `smart` 按状态分级；`fixed` 使用固定间隔 |
| `steam_smart_poll_intervals` | `5,5,30,60,300,600` | 游戏中、在线或离线 12 分钟内、离线 3 小时内、24 小时内、48 小时内、更久的间隔，单位秒 |
| `steam_fixed_poll_interval` | `5` | 固定模式间隔，单位秒 |
| `steam_heartbeat_throttle` | `5` | 心跳处理的最小间隔，单位秒 |
| `steam_status_daily_budget` | `80000` | 状态请求的每日估算预算，最大 80000 |
| `steam_retry_times` | `3` | 每批状态请求的最大尝试次数 |

所有状态轮询间隔至少为 5 秒。根据有效绑定中不同 Steam ID 的数量，额外计算预算下限：

```text
批次数 = ceil(有效 Steam ID 数 / 100)
预算下限秒数 = max(5, ceil(批次数 × 86400 × 最大尝试次数 / 状态日预算))
实际安排间隔 = max(状态分级或固定间隔, 预算下限秒数)
```

默认配置下，100 个以内有效 Steam 用户的在线/游戏中状态可每 5 秒轮询；
101～200 个用户的预算下限为 7 秒。长期离线的用户继续低频轮询。
无有效绑定时不请求 Steam。

Steam 官方规定每天最多 [100000 次 Web API 请求](https://steamcommunity.com/dev/apiterms)。
默认状态预算预留 20000 次给成就、在线人数和手动查询。
这是状态轮询的容量估算，不是所有 Steam 接口共享的严格日计数器；
同一个 key 在其他程序中的请求也需自行计入。

轮询由 OneBot 心跳驱动。要达到 5 秒，OneBot 的心跳上报间隔需要设为
5000 毫秒或更短；网络、渲染、消息发送耗时也可能延长实际间隔。
本地已有配置会覆盖代码默认值，修改后需重启 bot。
