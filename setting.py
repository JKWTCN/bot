from random import choice


class setting:
    developers_list = [1505617447, 3070004098]
    admin_list = [
        2781865679,
        3011745967,
        3835689054,
        2362647500,
        2239158081,
        921065312,
        1580584754,
        1286145524,
        692309296,
    ]
    bot_id = 3443801350
    admin_group_main = 868030377
    admin_group_list = [868030377, 116177178]
    blacklist = {"2564163440": "辱骂行为", "2689752704": "多种辱骂、嘲讽、拱火行为"}
    # miaomiao群友
    miaomiao_group_member = 2325333054
    test_group = 116177178
    timeout = 5


def cxxm(group_id: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": "3011745967"}},
                {"type": "text", "data": {"text": choice([" 抽象小马!", " 🤡🐘👌🐴"])}},
            ],
        },
    }
    return payload


def cxgl(group_id: int, user_id: int):
    match user_id:
        case 3835689054:
            cx_str = choice([" 抽象数字哥!", " 🤡🐘🔢🈹"])
        case 2362647500:
            cx_str = choice([" 抽象玛卡!", " 🤡🐘🐎☕"])
        case 2239158081:
            cx_str = choice([" 抽象羽鳞!", " 🤡🐘☔️0️⃣"])
        case 3011745967:
            cx_str = choice([" 抽象小马!", " 🤡🐘👌🐴"])
        case 2781865679:
            cx_str = choice([" 抽象树宝!", " 🤡🐘🎒"])
        case 921065312:
            cx_str = choice([" 抽象阿姆罗!", " 🤡🐘😦🪦🐪"])
        case 1580584754:
            cx_str = choice([" 抽象暴龙!", " 🤡🐘🦖"])
        case 1286145524:
            cx_str = choice([" 抽象管理!", " 🤡🐘🧪🍐"])
        case 692309296:
            cx_str = choice([" 抽象月饼!", " 🤡🐘🥮"])
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {"type": "at", "data": {"qq": user_id}},
                {"type": "text", "data": {"text": cx_str}},
            ],
        },
    }
    return payload