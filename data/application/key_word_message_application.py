import application
class KeyWordMessageApplication(application):

    key_words = []

    def __init__(self, application):
        super().__init__(application)
        self.application = application
  