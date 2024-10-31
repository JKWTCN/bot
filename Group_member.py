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

    # def __init__(
    #     self,
    #     group_id: int,
    #     user_id: int,
    #     nickname: str,
    #     card: str,
    #     sex: str,
    #     age: int,
    #     area: str,
    #     join_time: int,
    #     last_sent_time: int,
    #     level: int,
    #     role: int,
    #     unfriendly: bool,
    #     title: str,
    #     title_expire_time: int,
    #     card_changeable: bool,
    # ):
    #     self.group_id = group_id
    #     self.user_id = user_id
    #     self.nickname = nickname
    #     self.card = card
    #     self.sex = sex
    #     self.age = age
    #     self.area = area
    #     self.join_time = join_time
    #     self.last_sent_time = last_sent_time
    #     self.level = level
    #     self.role = role
    #     self.unfriendly = unfriendly
    #     self.title = title
    #     self.title_expire_time = title_expire_time
    #     self.card_changeable = card_changeable

    def __init__(self, list):
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
        "SELECT *,card FROM group_member_info where user_id=? and group_id=?",
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


def updata_user_info(group_member: Group_member):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    is_had, _group_member = get_user_info(group_member.user_id, group_member.group_id)
    if is_had:
        cur.execute(
            "DELETE FROM group_member_info where user_id=? and group_id=?",
            (group_member.user_id, group_member.group_id),
        )
        conn.commit()
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
