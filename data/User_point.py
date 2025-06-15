class User_point:
    user_id: int
    point: int
    time: int

    def __init__(self, user_id: int, point: int, time: int):
        self.user_id = user_id
        self.point = point
        self.time = time