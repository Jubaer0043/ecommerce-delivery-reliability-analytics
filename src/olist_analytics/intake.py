"""Acquire official source bytes, validate the archive, and preserve raw files."""
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .config import DOWNLOAD_URL, EXTERNAL, FILES, RAW, REPORTS, SOURCE_URL


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_hashes() -> dict:
    return {filename: sha256(RAW / filename) for filename in FILES.values()}


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def acquire(archive: Path | None = None) -> dict:
    """Do not overwrite existing raw files; conflicting content is an error."""
    RAW.mkdir(parents=True, exist_ok=True)
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    destination = EXTERNAL / "olist_official.zip"
    if archive is not None:
        archive = archive.resolve()
        if not archive.is_file():
            raise FileNotFoundError(archive)
    elif destination.exists():
        archive = destination
    else:
        with tempfile.NamedTemporaryFile(dir=EXTERNAL, suffix=".part", delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "OlistPortfolio/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response, temp_path.open("wb") as out:
                shutil.copyfileobj(response, out)
            if not zipfile.is_zipfile(temp_path):
                raise ValueError("Kaggle returned non-ZIP content. Download manually from the official source.")
            temp_path.replace(destination)
        finally:
            temp_path.unlink(missing_ok=True)
        archive = destination

    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise ValueError("Archive CRC validation failed")
        names = zipped.namelist()
        if len(names) != len(set(names)) or set(names) != set(FILES.values()):
            raise ValueError("Expected exactly the nine original Olist CSV files; refusing unexpected members")
        if sum(info.file_size for info in zipped.infolist()) > 500_000_000:
            raise ValueError("Archive exceeds the expected extraction size limit")
        # Validate every conflict before writing anything.
        for name in names:
            target = RAW / name
            if target.exists():
                expected = hashlib.sha256(zipped.read(name)).hexdigest()
                if sha256(target) != expected:
                    raise ValueError(f"Raw file differs from source: {name}; refusing to overwrite")
        for name in names:
            target = RAW / name
            if not target.exists():
                with zipped.open(name) as inp, target.open("xb") as out:
                    shutil.copyfileobj(inp, out)
    if archive != destination.resolve() and archive != destination:
        if destination.exists() and sha256(destination) != sha256(archive):
            raise ValueError("An existing source archive differs; refusing to overwrite")
        if not destination.exists():
            with archive.open("rb") as inp, destination.open("xb") as out:
                shutil.copyfileobj(inp, out)
    manifest_path = REPORTS / "source_manifest.json"
    current = raw_hashes()
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old["raw_sha256"] != current or old["archive_sha256"] != sha256(destination):
            raise ValueError("Source differs from recorded manifest")
        return old
    manifest = {
        "source_url": SOURCE_URL,
        "download_url": DOWNLOAD_URL,
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
        "license": "CC BY-NC-SA 4.0",
        "archive_sha256": sha256(destination),
        "raw_sha256": current,
        "source_version": "Version not inferred; exact downloaded bytes identified by SHA-256",
    }
    write_json(manifest_path, manifest)
    return manifest


def verify_raw() -> dict:
    path = REPORTS / "source_manifest.json"
    if not path.exists():
        raise FileNotFoundError("Run the acquire stage first; no source manifest found")
    expected = json.loads(path.read_text(encoding="utf-8"))["raw_sha256"]
    actual = raw_hashes()
    if expected != actual:
        raise ValueError("Raw input checksum mismatch: originals may have changed")
    return actual
