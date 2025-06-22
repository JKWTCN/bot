from data.application.application import Application


class ApplicationList:
    def __init__(self):
        self.applicationList: list[Application] = []

    def get(self) -> list[Application]:
        return self.applicationList

    def add(self, application: Application):
        if len(self.applicationList) == 0:
            self.applicationList.append(application)
            # print(len(self.applicationList))
            return
        for i, item in enumerate(self.applicationList):
            if application.priority > item.priority:
                self.applicationList.insert(i, application)
                # print(len(self.applicationList))
                return
        self.applicationList.append(application)
        # print(len(self.applicationList))


otherApplicationList = ApplicationList()
groupMessageApplicationList = ApplicationList()
privateMessageApplicationList = ApplicationList()
noticeApplicationList = ApplicationList()
requestApplicationList = ApplicationList()
metaApplicationList = ApplicationList()
