from typing import Union


class BaseClient(object):

    def connect(self) -> None:  # pragma: no cover
        raise NotImplementedError()

    def close(self) -> None:  # pragma: no cover
        raise NotImplementedError()

    def dispose(self) -> None:  # pragma: no cover
        raise NotImplementedError()

    def is_connection_closed() -> bool:  # pragma: no cover
        raise NotImplementedError()

    def is_trace_enabled() -> bool:  # pragma: no cover
        raise NotImplementedError()

    def send(message: Union[bytes, str], **kwargs) -> None:  # pragma: no cover
        raise NotImplementedError()
