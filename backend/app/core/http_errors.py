from fastapi import HTTPException


def api_error(
    status_code: int, code: str, message: str = "", headers: dict[str, str] | None = None
) -> HTTPException:
    """User-facing HTTP error. Clients map `code`; `message` is for logs / old clients."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message or code},
        headers=headers,
    )
