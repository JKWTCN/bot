from data.application.application import Application
from schedule.application_list import ApplicationList
from data.enumerates import ApplicationType
import application_list


def RegisterApplication(application: Application):
    match application.applicationType:
        case ApplicationType.GROUP_MESSAGE:
            application_list.groupMessageApplicationList.add(application)
        case ApplicationType.PRIVATE_MESSSAGE:
            application_list.privateMessageApplicationList.add(application)
        case ApplicationType.NOTICE:
            application_list.noticeApplicationList.add(application)
        case ApplicationType.REQUEST:
            application_list.requestApplicationList.add(application)
        case ApplicationType.META:
            application_list.metaApplicationList.add(application)
        case _:
            application_list.applicationList.add(application)
