import pytest
from service import payment_service
from config import PACKAGES

@pytest.mark.asyncio
async def test_create_payment():
    result = await payment_service.create_payment(
        user_id=123456789,
        package="basic"
    )
    assert "payment_id" in result or "error" in result

def test_packages_config():
    assert "basic" in PACKAGES
    assert PACKAGES["basic"]["price"] > 0
