import pytest
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.payment.service import payment_service
from src.shared.config import PACKAGES

@pytest.mark.asyncio
async def test_get_tariffs():
    """Test getting available tariffs - requires database"""
    # This test requires a real database connection
    # Skip if database is not available
    try:
        tariffs = await payment_service.get_tariffs()
        assert isinstance(tariffs, list), "Tariffs should return a list"
    except (RuntimeError, ConnectionRefusedError, Exception) as e:
        if "Database not initialized" in str(e) or "ConnectionRefused" in str(e.__class__.__name__):
            pytest.skip(f"Database not available for testing: {e}")
        raise

def test_packages_config():
    """Test that PACKAGES configuration is valid"""
    assert "basic" in PACKAGES
    assert PACKAGES["basic"]["price"] > 0
    assert PACKAGES["basic"]["images"] > 0
    
    # Check all required packages exist
    required_packages = ['once', 'basic', 'premium', 'pro']
    for package in required_packages:
        assert package in PACKAGES, f"Package '{package}' is missing"
        assert "price" in PACKAGES[package], f"Package '{package}' missing price"
        assert "images" in PACKAGES[package], f"Package '{package}' missing images"

def test_payment_service_providers():
    """Test that payment service has providers configured"""
    assert hasattr(payment_service, 'providers'), "Payment service should have providers"
    assert "yookassa" in payment_service.providers, "YooKassa provider should be available"
    assert "cloudpayments" in payment_service.providers, "CloudPayments provider should be available"
