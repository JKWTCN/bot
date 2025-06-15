import logging
import yagmail

from tools import GetLogTime, load_setting


# 发送日志文件到邮箱
def send_log_email():
    email = load_setting()["email"]
    # 连接邮箱服务器 发送方邮箱+授权码+邮箱服务地址
    yag = yagmail.SMTP(
        user=email["user"],
        password=email["password"],
        host=email["host"],
        encoding="GBK",
    )
    # 邮件正文 支持html，支持上传附件
    now = GetLogTime()
    log_path = f"log/{now}.log"
    content = [f"{GetLogTime()}的日志"]
    # logging.info(f"发送{log_path}日志文件到邮箱")
    print(f"发送{log_path}日志文件到邮箱")
    yag.send(
        email["rev_email"],
        "运行日志",
        content,
        [
            log_path,
        ],
    )
    yag.close()


# send_log_email()
