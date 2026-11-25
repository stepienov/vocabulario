"""Identity and location of the separately signed public alpha APK."""

from pathlib import Path

ALPHA_PACKAGE = "io.vocabulario.alpha"
ALPHA_CERT_SHA256 = "0C:D3:DF:F5:C1:B2:F5:A5:CD:12:15:DE:99:A8:55:44:7C:11:1A:12:01:F0:7B:B7:37:7C:8A:E9:7A:BF:3F:B3"
ALPHA_APK = Path(__file__).resolve().parent / "downloads" / "Vocabulario-alpha.apk"
