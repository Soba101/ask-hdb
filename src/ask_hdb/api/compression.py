"""Use the same gzip acceptance check for cached data and response middleware."""

from starlette.datastructures import Headers
from starlette.middleware.gzip import GZipMiddleware as StarletteGZipMiddleware


def accepts_gzip(value):
    # A zero quality forbids gzip even when its name is present in the header.
    for item in value.lower().split(","):
        coding, *parameters = item.split(";")
        if coding.strip() != "gzip":
            continue
        for parameter in parameters:
            name, _, quality = parameter.partition("=")
            if name.strip() == "q":
                try:
                    return 0 < float(quality) <= 1
                except ValueError:
                    return False
        return True
    return False


class GZipMiddleware(StarletteGZipMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Starlette checks only for a substring. Normalize its decision before
            # either compression path runs, without changing the caller's scope.
            encoding = b"gzip" if accepts_gzip(Headers(scope=scope).get("accept-encoding", "")) else b"identity"
            scope = {**scope, "headers": [(key, encoding if key == b"accept-encoding" else value)
                                         for key, value in scope["headers"]]}
        await super().__call__(scope, receive, send)
