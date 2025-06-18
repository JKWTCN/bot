from data.register.register_event_type import RegisterEventType
from data.application.application import Application
from data.application.application_type import ApplicationType


groupKeyWordList: list[Application] = []


def RegisterEvent(
    application: Application,
    registerEventType: RegisterEventType,
    priority: float = 0.0,
):
    match application.applicationType:
        case ApplicationType.GROUP_KEY_WORD:
            groupKeyWordList.append(application)
            pass
        
    pass
