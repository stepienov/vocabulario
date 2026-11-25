"""Certificate output formats supported by the Android SDK build tools."""

import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[2] / "scripts" / "check_alpha_apk.py"
spec = importlib.util.spec_from_file_location("check_alpha_apk", path)
alpha_apk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alpha_apk)

FINGERPRINT = alpha_apk.ALPHA_CERT_SHA256.replace(":", "").lower()


@pytest.mark.parametrize("prefix", ["Signer #1", "V2 Signer:", "V3.1 Signer:"])
def test_accepts_expected_certificate_in_sdk_output(prefix):
    alpha_apk.verify_certificates(f"{prefix} certificate SHA-256 digest: {FINGERPRINT}\n", "test")


def test_rejects_unexpected_or_unrecognized_signers():
    valid = f"V2 Signer: certificate SHA-256 digest: {FINGERPRINT}\n"
    with pytest.raises(ValueError):
        alpha_apk.verify_certificates(valid + "V3 Signer: certificate SHA-256 digest: 00\n", "test")
    with pytest.raises(ValueError):
        alpha_apk.verify_certificates(valid + "Other certificate SHA-256 digest: 00\n", "test")
    with pytest.raises(ValueError):
        alpha_apk.verify_certificates("", "test")
