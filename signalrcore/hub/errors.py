class HubError(OSError):
    pass


class UnAuthorizedHubError(HubError):
    pass


class HubConnectionError(ValueError):
    """Hub connection error
    """
    pass


class HubReconnectingError(HubError):
    pass


class HandShakeError(HubError):
    pass