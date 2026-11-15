import inspect


async def maybe_await(value):
    """Awaits the value when it is awaitable, otherwise returns it.

    Keeps the sync callbacks working while allowing coroutine callbacks
    in the asyncio implementation.
    """
    if inspect.isawaitable(value):
        return await value
    return value


async def call_callback(callback, *args, **kwargs):
    """Calls a sync or async callback and awaits its result if needed.

    A missing callback is a no-op so optional hooks stay optional.
    """
    if callback is None:
        return None

    return await maybe_await(callback(*args, **kwargs))


def is_coroutine_function(callback) -> bool:
    return inspect.iscoroutinefunction(callback)
