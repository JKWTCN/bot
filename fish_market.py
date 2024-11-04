import sqlite3
from Class.Fish_record import Fish_record, Fish_type


def add_fish_record(record: Fish_record):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "insert into fish_record values(?,?,?,?,?,?,?,?,?,?) ",
        (
            record.user_id,
            record.group_id,
            record.fish_nums,
            record.prices,
            record.type,
            record.sec_id,
            record.start_time,
            0,
            False,
            None,
        ),
    )
    conn.commit()


def find_all_record_this_week():
    pass


rec = Fish_record(1, 2, 3, 4, Fish_type.buy.value, 6, 7)
print(rec.type)
add_fish_record(rec)
