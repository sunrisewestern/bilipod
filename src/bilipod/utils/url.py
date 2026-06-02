import re
from urllib.parse import urlsplit, urlunsplit


def sanitize_url(url) -> str:
    """Collapse repeated path slashes without changing the URL scheme."""
    if not isinstance(url, str):
        return ""

    stripped_url = url.strip()
    if not stripped_url:
        return ""

    parts = urlsplit(stripped_url)
    sanitized_path = re.sub(r"/{2,}", "/", parts.path)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            sanitized_path,
            parts.query,
            parts.fragment,
        )
    )


def join_url(base_url: str, *path_parts) -> str:
    clean_parts = [
        str(part).strip("/")
        for part in path_parts
        if part is not None and str(part).strip("/")
    ]
    if clean_parts:
        return sanitize_url("/".join([str(base_url).rstrip("/"), *clean_parts]))
    return sanitize_url(base_url)
