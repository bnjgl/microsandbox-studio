"""Download the static shpool binaries that the app copies into sandboxes."""

import hashlib
import io
import tarfile
import urllib.request
from pathlib import Path

from microsandbox_studio.terminal import SHPOOL_VERSION as VERSION

RELEASE = f"https://github.com/shell-pool/shpool/releases/download/v{VERSION}"
# SHA-256 of the release archives, as listed on the GitHub release. Update
# them together with SHPOOL_VERSION; a mismatch stops the download.
ARCHIVES = {
    "aarch64": "98402f7ba14b0e9050b31eab80c6dfb26761f1aed45733f393841f615000d18b",
    "x86_64": "132f786bd275749a46224c17a071474a850f0be1fbb752b1c96d910778543c9b",
}
LICENSE = f"https://raw.githubusercontent.com/shell-pool/shpool/v{VERSION}/LICENSE"
TARGET = Path(__file__).resolve().parents[1] / "src" / "microsandbox_studio" / "assets" / "shpool"


def download(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()


def main() -> None:
    for arch, digest in ARCHIVES.items():
        data = download(f"{RELEASE}/shpool-{arch}-unknown-linux-musl.tar.gz")
        if hashlib.sha256(data).hexdigest() != digest:
            raise SystemExit(f"Checksum mismatch for {arch}.")
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            binary = archive.extractfile("shpool")
            if binary is None:
                raise SystemExit(f"Archive for {arch} does not contain shpool.")
            path = TARGET / arch / "shpool"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(binary.read())
        print(path.relative_to(TARGET.parents[3]))
    (TARGET / "LICENSE").write_bytes(download(LICENSE))


if __name__ == "__main__":
    main()
