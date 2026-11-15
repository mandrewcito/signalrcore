import ssl
from ssl import SSLContext

WINDOW_SIZE = 1024


def create_ssl_context(verify_ssl: bool) -> SSLContext:
    context = ssl.create_default_context()\
        if verify_ssl else\
        ssl._create_unverified_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context
