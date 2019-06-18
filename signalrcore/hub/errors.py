class HubError(ConnectionResetError):
    pass


class UnAuthorizedHubError(HubError):
    pass
