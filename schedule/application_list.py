from data.application.application import Application


class ApplicationList:
    def __init__(self):
        self.applicationList: list[Application] = []

    def get(self) -> list[Application]:
        return self.applicationList

    def add(self, application: Application):
        if len(self.applicationList) == 0:
            self.applicationList.append(application)
            return
        for i, item in enumerate(self.applicationList):
            if application.priority > item.priority:
                self.applicationList.insert(i, application)


otherApplicationList = ApplicationList()
groupMessageApplicationList = ApplicationList()
privateMessageApplicationList = ApplicationList()
noticeApplicationList = ApplicationList()
requestApplicationList = ApplicationList()
metaApplicationList = ApplicationList()
