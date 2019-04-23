from urllib import parse

class helpers:
    @staticmethod
    def websocket_to_http(url):
        urlParts = parse.urlsplit(url)

        if "http" not in urlParts.scheme:
            if urlParts.scheme == "wss" : urlParts = urlParts._replace(scheme="https")  
            if urlParts.scheme == "ws" : urlParts = urlParts._replace(scheme="http")

        return parse.urlunsplit(urlParts)

    @staticmethod
    def http_to_websocket(url):
        urlParts = parse.urlsplit(url)

        if "ws" not in urlParts.scheme:
            if urlParts.scheme == "https" : urlParts = urlParts._replace(scheme="wss")  
            if urlParts.scheme == "http" : urlParts = urlParts._replace(scheme="ws")

        return parse.urlunsplit(urlParts)

    @staticmethod
    def get_negotiate_url(url):   
        urlParts = parse.urlsplit(helpers.websocket_to_http(url))

        negotiate_suffix = "negotiate" if urlParts.path.endswith('/') else "/negotiate"

        urlParts = urlParts._replace(path=urlParts.path + negotiate_suffix)

        return parse.urlunsplit(urlParts)

    @staticmethod
    def encode_connection_id(url, id):
        url_parts = parse.urlsplit(url)

        query_string_parts = parse.parse_qs(url_parts.query)
        query_string_parts["id"] = id

        url_parts = url_parts._replace(query=parse.urlencode(query_string_parts, doseq=True))

        return helpers.http_to_websocket(parse.urlunsplit(url_parts))