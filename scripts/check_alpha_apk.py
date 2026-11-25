"""Verify that the distributable is the separately signed production alpha."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.public_web.alpha import ALPHA_CERT_SHA256, ALPHA_PACKAGE


def build_tools() -> Path:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk and os.environ.get("LOCALAPPDATA"):
        sdk = str(Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk")
    if not sdk:
        raise RuntimeError("Set ANDROID_HOME or ANDROID_SDK_ROOT to the Android SDK")
    tools = Path(sdk) / "build-tools"
    if not tools.is_dir():
        raise RuntimeError("Android SDK build-tools not found")
    candidates = [
        path for path in tools.iterdir()
        if path.is_dir()
        and (path / "lib" / "apksigner.jar").is_file()
        and (path / ("aapt.exe" if os.name == "nt" else "aapt")).is_file()
    ]
    if not candidates:
        raise RuntimeError("aapt and apksigner are required")
    return max(candidates, key=lambda p: tuple(int(n) for n in re.findall(r"\d+", p.name)))


def run(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout


def apk_version(apk: Path, aapt: Path) -> int:
    badging = run(str(aapt), "dump", "badging", str(apk))
    match = re.search(r"^package: name='([^']+)' versionCode='(\d+)'", badging, re.MULTILINE)
    if not match or match.group(1) != ALPHA_PACKAGE:
        raise ValueError(f"Expected package {ALPHA_PACKAGE}")
    if "application-debuggable" in badging:
        raise ValueError("Debuggable APK is not permitted")
    if "application-label:'Vocabulario Alpha'" not in badging:
        raise ValueError("Expected the Vocabulario Alpha application label")
    version = int(match.group(2))
    if version < 1:
        raise ValueError("Invalid versionCode")
    return version


def verify_certificates(signatures: str, tools_name: str) -> None:
    certificate_lines = [line for line in signatures.splitlines() if "certificate SHA-256 digest:" in line]
    pattern = re.compile(
        r"^(?:Signer #\d+|V[\d.]+ Signer(?: #\d+)?):? certificate SHA-256 digest: ([0-9a-fA-F]+)$"
    )
    fingerprints = [match.group(1).lower() for line in certificate_lines if (match := pattern.fullmatch(line))]
    expected = ALPHA_CERT_SHA256.replace(":", "").lower()
    if not fingerprints or len(fingerprints) != len(certificate_lines) or any(
        fingerprint != expected for fingerprint in fingerprints
    ):
        raise ValueError(
            f"APK is not signed with the alpha certificate (build-tools {tools_name}; "
            f"certificate output: {certificate_lines})"
        )


def verify(apk: Path, previous: Path | None = None) -> None:
    tools = build_tools()
    aapt = tools / ("aapt.exe" if os.name == "nt" else "aapt")
    version = apk_version(apk, aapt)
    if previous is not None and version <= apk_version(previous, aapt):
        raise ValueError("New alpha versionCode must be greater than the previous APK")
    signatures = run("java", "-jar", str(tools / "lib" / "apksigner.jar"), "verify", "--print-certs", str(apk))
    verify_certificates(signatures, tools.name)
    with zipfile.ZipFile(apk) as archive:
        if archive.testzip() is not None:
            raise ValueError("APK archive is corrupt")
        dex_files = [name for name in archive.namelist() if re.fullmatch(r"classes\d*\.dex", name)]
        if not any(b"https://vocabulario.io/api/v1" in archive.read(name) for name in dex_files):
            raise ValueError("Production API URL is missing from APK")
    print(f"Verified {ALPHA_PACKAGE}, versionCode {version}, signature and production API")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    try:
        verify(args.apk, args.previous)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"Alpha APK verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
