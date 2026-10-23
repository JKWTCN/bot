# 随机群聊

`intelligence_config.json` 的 `chat_quality.group_overrides` 按群号覆盖聊天质量参数。
目前仅 `765698568` 启用新的 `random_chat_policy`；其他群继续采用旧的 0.5% 抽样和评分逻辑。

该群的新策略：

- 叫机器人名字、@机器人，或引用回复机器人消息，直接进入模型判断。引用消息会异步查询 OneBot 消息详情，核对发送者，且详情提供群号时核对群号；引用其他群友的消息仍走随机策略。
- 问题、求助先评分，达到 `question_threshold=50` 后按 `question_probability=0.20` 抽样。
- 普通有内容的聊天达到 `normal_threshold=40` 后按 `normal_probability=0.03` 抽样。普通陈述的基础分是 40，单用 50 分门槛会挡住它们。
- 空文本、短反应、纯媒体占位、命令等不进入随机聊天。
- 模型仍可以选择 `wait`，所以抽样概率不等于实际回复概率。

随机回复受群级限制：`cooldown_seconds=90`，滚动 `window_seconds=600` 秒内最多
`max_replies_per_window=3` 次。候选进入异步处理前占用该群名额，避免并发请求绕过限流；
只有回复发送调用成功后才计入次数和冷却。模型等待、失败均释放占用，随机处理失败不向群里发送错误提示。
限流状态保存在进程内，重启后清空。直接点名、@、引用回复机器人不占随机额度。

群配置的 `enable_chat`、`random_chat`、`replay_chat`、`silent_mode` 和不回复名单继续生效。
`random_reply_frequency` 继续表示评分倍率，抽样概率由上面的独立字段控制。
配置在判定时读取，代码变更需要重启进程。

日志：INFO 记录候选通过、限流和发送结果；DEBUG 记录无效内容及未抽中/评分不足。
不会为了测试触发条件而向群里发送消息。

验证：` .venv/bin/python -m unittest discover -s tests -p test_random_chat.py -v `。
