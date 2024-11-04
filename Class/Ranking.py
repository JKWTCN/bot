class Ranking:
    user_id: int
    group_id: int
    max_value: int
    time: int
    type: int

    def __init__(
        self, user_id: int, group_id: int, max_value: int, time: int, type: int
    ):
        self.user_id = user_id
        self.group_id = group_id
        self.max_value = max_value
        self.time = time
        self.type = type