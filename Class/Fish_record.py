from enum import Enum


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
    no: int

    def __init__(
        self,
        user_id: int,
        group_id: int,
        fish_num: int,
        prices: int,
        sec_id: int,
        type: int,
        start_time: int,
    ):
        self.user_id = user_id
        self.group_id = group_id
        self.fish_nums = fish_num
        self.prices = prices
        self.sec_id = sec_id
        self.type = type
        self.start_time = start_time
