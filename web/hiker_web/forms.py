"""Reading form fields: blank becomes None, numbers accept a German comma."""

from flask import Response, request

from hiker_web.api import api


class FormError(ValueError):
    """The form holds a value that cannot be read, e.g. text in a number field."""


def text(name: str) -> str | None:
    value = (request.form.get(name) or "").strip()
    return value or None


def to_number(value: str | None, name: str = "", convert=float):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return convert(float(value.replace(",", ".")))
    except (ValueError, OverflowError) as exc:
        raise FormError(name) from exc


def number(name: str, convert=float):
    return to_number(request.form.get(name), name, convert)


def whole(name: str) -> int | None:
    return number(name, lambda value: int(round(value)))


def checked(name: str) -> bool:
    return request.form.get(name) is not None


def image_response(upstream) -> Response:
    response = Response(
        upstream.content, mimetype=upstream.headers.get("content-type", "image/jpeg")
    )
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


def proxy_image(path: str, **params) -> Response:
    """Pass an image of the API on to the browser, with the user's token."""
    return image_response(api().request("GET", path, params=params))


def upload(field: str = "file", multiple: bool = False) -> dict | list:
    """The uploaded files of a form field, in the shape the API client sends them."""
    files = [
        (field, (item.filename, item.stream.read(), item.mimetype))
        for item in request.files.getlist(field)
        if item and item.filename
    ]
    return files if multiple else files[:1]


def download(path: str, fallback_name: str) -> Response:
    """Pass a file of the API on to the browser as a download."""
    upstream = api().request("GET", path)
    response = Response(
        upstream.content,
        mimetype=upstream.headers.get("content-type", "application/octet-stream"),
    )
    response.headers["Content-Disposition"] = upstream.headers.get(
        "content-disposition", f'attachment; filename="{fallback_name}"'
    )
    return response
