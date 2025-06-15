from enum import Enum
from multimethod import multimethod


class Fish_type(Enum):
    sell = 1
    buy = 2
    sell_market = 3
    buy_market = 4


class Fish_record:
    user_id: int
    group_id: int
    fish_nums: int
    prices: int
    type: int
    sec_id: int
    start_time: int
    finsh_time: int
    is_finish: bool
    no: int

    @multimethod
    def __init__(
        self,
        user_id: int,
        group_id: int,
        fish_num: int,
        prices: int,
        type: int,
        sec_id: int,
        start_time: int,
        finsh_time: int,
        is_finish: bool,
    ):
        self.user_id = user_id
        self.group_id = group_id
        self.fish_nums = fish_num
        self.prices = prices
        self.type = type
        self.sec_id = sec_id
        self.start_time = start_time
        self.finsh_time = finsh_time
        self.is_finish = is_finish

    @multimethod
    def __init__(self, record: list):
        self.user_id = record[0]
        self.group_id = record[1]
        self.fish_nums = record[2]
        self.prices = record[3]
        self.type = record[4]
        self.sec_id = record[5]
        self.start_time = record[6]
        self.finsh_time = record[7]
        self.is_finish = record[8]
