import re
import sqlite3


class Group_member:
    group_id: int
    user_id: int
    nickname: str
    card: str
    sex: str
    age: int
    area: str
    join_time: int
    last_sent_time: int
    level: int
    role: int  # 角色，owner 或 admin 或 member
    unfriendly: bool  # 是否不良记录成员
    title: str  # 专属头衔
    title_expire_time: int  # 专属头衔过期时间戳
    card_changeable: bool  # 是否允许修改群名片

    def init_by_dict(self, member_info: dict):
        self.group_id = member_info["group_id"]
        self.user_id = member_info["user_id"]
        self.nickname = member_info["nickname"]
        self.card = member_info["card"]
        self.sex = member_info["sex"]
        self.age = member_info["age"]
        self.area = member_info["area"]
        self.join_time = member_info["join_time"]
        self.last_sent_time = member_info["last_sent_time"]
        self.level = member_info["level"]
        self.role = member_info["role"]
        self.unfriendly = member_info["unfriendly"]
        self.title = member_info["title"]
        self.title_expire_time = member_info["title_expire_time"]
        self.card_changeable = member_info["card_changeable"]

    def __init__(self, list: list = []):
        if len(list) == 0:
            return
        self.group_id = list[0]
        self.user_id = list[1]
        self.nickname = list[2]
        self.card = list[3]
        self.sex = list[4]
        self.age = list[5]
        self.area = list[6]
        self.join_time = list[7]
        self.last_sent_time = list[8]
        self.level = list[9]
        self.role = list[10]
        self.unfriendly = list[11]
        self.title = list[12]
        self.title_expire_time = list[13]
        self.card_changeable = list[14]


def get_user_info(user_id: int, group_id: int):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM group_member_info where user_id=? and group_id=?",
        (
            user_id,
            group_id,
        ),
    )
    data = cur.fetchall()
    # print(data)
    if len(data) == 0:
        return (False, None)
    else:
        return (True, Group_member(data[0]))


def get_user_name(user_id: int, group_id: int):
    res, user = get_user_info(user_id, group_id)
    if res:
        if user.card != "":
            return user.card
        else:
            return user.nickname
    else:
        return user_id


def is_in_group(user_id: int, group_id: int):
    res, user = get_user_info(user_id, group_id)
    return res


def updata_user_info(group_member: Group_member):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    is_had, _group_member = get_user_info(group_member.user_id, group_member.group_id)
    if is_had:
        cur.execute(
            "UPDATE group_member_info SET nickname = ?,card = ?,sex = ?,age = ?,area = ?,join_time = ?,last_sent_time = ?,level = ?,role = ?,unfriendly = ?,title = ?,title_expire_time = ?,card_changeable = ? WHERE group_id = ? AND user_id = ?;",
            (
                group_member.nickname,
                group_member.card,
                group_member.sex,
                group_member.age,
                group_member.area,
                group_member.join_time,
                group_member.last_sent_time,
                group_member.level,
                group_member.role,
                group_member.unfriendly,
                group_member.title,
                group_member.title_expire_time,
                group_member.card_changeable,
                group_member.group_id,
                group_member.user_id,
            ),
        )
        conn.commit()
    else:
        cur.execute(
            "INSERT INTO group_member_info VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                group_member.group_id,
                group_member.user_id,
                group_member.nickname,
                group_member.card,
                group_member.sex,
                group_member.age,
                group_member.area,
                group_member.join_time,
                group_member.last_sent_time,
                group_member.level,
                group_member.role,
                group_member.unfriendly,
                group_member.title,
                group_member.title_expire_time,
                group_member.card_changeable,
            ),
        )
        conn.commit()
    # print(is_had)


def get_group_member_list_payload(group_id: int):
    payload = {
        "action": "get_group_member_list",
        "params": {
            "group_id": group_id,
        },
        "echo": "update_group_member_list",
    }
    return payload
