from data.application.application import Application


class ApplicationList:
    applicationList: list[Application] = []

    def get(self) -> list[Application]:
        return self.applicationList

    def add(self, application: Application):
        for i, item in enumerate(self.applicationList):
            if application.priority > item.priority:
                self.applicationList.insert(i, application)


applicationList: ApplicationList
groupMessageApplicationList: ApplicationList
privateMessageApplicationList: ApplicationList
noticeApplicationList: ApplicationList
requestApplicationList: ApplicationList
metaApplicationList: ApplicationList
