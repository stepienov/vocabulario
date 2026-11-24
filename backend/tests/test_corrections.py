"""The legacy automatic card correction API is no longer available."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/corrections/quota"),
        ("POST", "/api/v1/cards/00000000-0000-0000-0000-000000000001/corrections"),
        ("GET", "/api/v1/cards/00000000-0000-0000-0000-000000000001/corrections/latest"),
        (
            "POST",
            "/api/v1/cards/00000000-0000-0000-0000-000000000001/corrections/"
            "00000000-0000-0000-0000-000000000002/escalate",
        ),
    ],
)
async def test_legacy_correction_endpoints_are_removed(method, path):
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == 404
