class User_fish:
    user_id: int
    group_id: int
    fish_nums: int
    time: int

    def __init__(self, user_id: int, group_id: int, fish_nums: int, time: int):
        self.user_id = user_id
        self.group_id = group_id
        self.fish_nums = fish_nums
        self.time = time

    def add_fish_nums(self, nums: int):
        self.fish_nums += nums

    def change_fish_nums(self, nums: int):
        self.fish_nums = nums
