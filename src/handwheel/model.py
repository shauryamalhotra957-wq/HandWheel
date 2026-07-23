from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path


MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
MODEL_NAME = "hand_landmarker.task"


def model_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / MODEL_NAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model(download: bool = True) -> Path:
    target = model_path()
    if target.exists() and _sha256(target) == MODEL_SHA256:
        return target
    if target.exists():
        target.unlink()
    if not download:
        raise FileNotFoundError(
            f"MediaPipe model is missing at {target}. Run: python -m handwheel.model --download"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="handwheel-model-", suffix=".task", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        request = urllib.request.Request(
            MODEL_URL, headers={"User-Agent": "HandWheel/0.1"}
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            with temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        actual_hash = _sha256(temporary)
        if actual_hash != MODEL_SHA256:
            raise RuntimeError(
                f"Hand model checksum mismatch: expected {MODEL_SHA256}, got {actual_hash}"
            )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the HandWheel hand model.")
    parser.add_argument("--download", action="store_true", help="download if missing")
    arguments = parser.parse_args()
    path = ensure_model(download=arguments.download)
    print(f"Hand model ready: {path}")


if __name__ == "__main__":
    main()
