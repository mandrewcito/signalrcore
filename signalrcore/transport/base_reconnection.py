class BaseReconnection(object):
    def __init__(self):
        self.reconnecting = False

    def next(self):
        raise NotImplementedError()

    def reset(self):
        raise NotImplementedError()
