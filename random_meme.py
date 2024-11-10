import base64
import logging
import random
from random import choice
import glob
from tools import GetDirSizeByUnit


def MemeStatistics(group_id: int):
    all_file = find_all_file("../meme")
    num, unit = GetDirSizeByUnit("../meme")
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": f"共有{len(all_file)}张图片,占用{num}{unit}空间喵!"
                    },
                },
            ],
        },
    }
    return payload


def find_all_file(path: str):
    s = []
    dir_path = "{}/**/*.*".format(path)
    for file in glob.glob(dir_path, recursive=True):
        # print(file)
        s.append(file)
    return s


def twenty_random_meme(group_id: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    all_file = find_all_file("../meme")
    for i in range(20):
        dir = choice(all_file)
        print(dir)
        while dir.endswith(".mp4"):
            dir = choice(all_file)
        logging.info("乐可发送了图片:{}".format(dir))
        with open(dir, "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data)
        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {"file": "base64://" + image_base64.decode("utf-8")},
            }
        )
    return payload


def ten_random_meme(group_id: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    all_file = find_all_file("../meme")
    for i in range(10):
        dir = choice(all_file)
        while dir.endswith(".mp4"):
            dir = choice(all_file)
        print(dir)
        logging.info("乐可发送了图片:{}".format(dir))
        with open(dir, "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data)
        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {"file": "base64://" + image_base64.decode("utf-8")},
            }
        )
    return payload


def send_meme_merge_forwarding(group_id: int, nums: int):
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": [],
        },
    }
    all_file = find_all_file("../meme")
    for i in range(nums):
        dir = choice(all_file)
        while dir.endswith(".mp4"):
            dir = choice(all_file)
        print(dir)
        logging.info("乐可发送了图片:{}".format(dir))
        with open(dir, "rb") as image_file:
            image_data = image_file.read()
        image_base64 = base64.b64encode(image_data)
        payload["params"]["message"].append(
            {
                "type": "image",
                "data": {"file": "base64://" + image_base64.decode("utf-8")},
            }
        )
    return payload


def send_random_meme(group_id: int):
    # s = find_all_file("./meme")
    # files = os.listdir("meme/unchoise")
    # path = "{}/{}".format("meme/unchoise", choice(files))
    all_file = find_all_file("../meme")
    path = choice(all_file)
    while path.endswith(".mp4"):
        path = choice(all_file)
    print(path)
    logging.info("乐可发送了图片:{}".format(path))
    with open(path, "rb") as image_file:
        image_data = image_file.read()
    # 对读取的二进制数据进行Base64编码
    image_base64 = base64.b64encode(image_data)
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": {
                "type": "image",
                "data": {"file": "base64://" + image_base64.decode("utf-8")},
            },
        },
    }
    return payload


def send_radom_http_cat(group_id: int):
    http_code = [
        100,
        101,
        200,
        201,
        202,
        203,
        204,
        205,
        206,
        300,
        301,
        302,
        303,
        304,
        305,
        306,
        307,
        400,
        401,
        402,
        403,
        404,
        405,
        406,
        407,
        408,
        409,
        410,
        411,
        412,
        413,
        414,
        415,
        416,
        417,
        418,
        500,
        501,
        502,
        503,
        504,
        505,
    ]
    payload = {
        "action": "send_msg",
        "params": {
            "group_id": group_id,
            "message": {
                "type": "image",
                "data": {
                    "file": "https://http.cat/{}".format(
                        http_code[random.randint(0, len(http_code) - 1)]
                    )
                },
            },
        },
    }
    return payload


# print(ten_random_meme(123))
# print(len(find_all_file("meme")))
