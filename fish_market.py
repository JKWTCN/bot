import sqlite3
from Class.Fish_record import Fish_record
import time


def add_fish_record(record: Fish_record):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO fish_record VALUES(?,?,?,?,?,?,?,?,?,?) ",
        (
            record.user_id,
            record.group_id,
            record.fish_nums,
            record.prices,
            record.type,
            record.sec_id,
            time.time(),
            None,
            False,
            None,
        ),
    )
    conn.commit()


def clear_all():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("DELETE from fish_record")
    conn.commit()


def find_all_record_this_week():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM fish_record")
    data = cur.fetchall()
    fish_record_list = []
    for i in data:
        now_record = Fish_record(i)
        fish_record_list.append(now_record)
    return fish_record_list


# rec = Fish_record(1, 2, 3, 4, Fish_type.buy.value, 6, 7, 0, False)
# add_fish_record(rec)
# find_all_record_this_week()
