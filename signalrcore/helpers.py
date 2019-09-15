import sys
import urllib
if sys.version_info.major is 2:
    import urlparse as parse
    query_encode = urllib.urlencode
else:
    import urllib.parse as parse
    query_encode = urllib.parse.urlencode


class Helpers:
    @staticmethod
    def has_querystring(url):
        return "?" in url

    @staticmethod
    def split_querystring(url):
        parts = url.split("?")
        return parts[0], parts[1]

    @staticmethod
    def replace_scheme(
            url,
            root_scheme,
            source,
            secure_source,
            destination,
            secure_destination):
        url_parts = parse.urlsplit(url)

        if root_scheme not in url_parts.scheme:            
            if url_parts.scheme == secure_source:
                url_parts = url_parts._replace(scheme=secure_destination)
            if url_parts.scheme == source:
                url_parts = url_parts._replace(scheme=destination)

        return parse.urlunsplit(url_parts)

    @staticmethod
    def websocket_to_http(url):
        return Helpers.replace_scheme(
            url,
            "http",
            "ws",
            "wss",
            "http",
            "https")

    @staticmethod
    def http_to_websocket(url):
        return Helpers.replace_scheme(
            url,
            "ws",
            "http",
            "https",
            "ws",
            "wss"
        )

    @staticmethod
    def get_negotiate_url(url):
        querystring = ""
        if Helpers.has_querystring(url):
            url, querystring = Helpers.split_querystring(url)
            
        url_parts = parse.urlsplit(Helpers.websocket_to_http(url))

        negotiate_suffix = "negotiate"\
            if url_parts.path.endswith('/')\
            else "/negotiate"

        url_parts = url_parts._replace(path=url_parts.path + negotiate_suffix)

        return parse.urlunsplit(url_parts) \
            if querystring is "" else\
                parse.urlunsplit(url_parts) + "?" + querystring

    @staticmethod
    def encode_connection_id(url, id):
        url_parts = parse.urlsplit(url)
        query_string_parts = parse.parse_qs(url_parts.query)
        query_string_parts["id"] = id

        url_parts = url_parts._replace(
            query=query_encode(
                query_string_parts,
                doseq=True))

        return Helpers.http_to_websocket(parse.urlunsplit(url_parts))
