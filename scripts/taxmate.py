#!/usr/bin/env python3
"""TaxMate Australia full-runtime command launcher."""

from __future__ import annotations

import argparse
import json
import os
import platform
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.request import Request, urlopen


COMMANDS = ("refresh", "skills", "validate", "finance", "calc")
OWNER = "nijanthan-dev"
REPO = "taxmate-australia"
BINARY_TEMPLATE = "taxmate-australia-{command}"
OS_PLATFORMS = {
    "darwin": ["darwin-amd64", "darwin-arm64", "darwin_amd64", "darwin_arm64"],
    "linux": ["linux-amd64", "linux-arm64", "linux_amd64", "linux_arm64"],
    "windows": ["windows-amd64", "windows_amd64"],
}


def _find_repo_root(start: Path) -> Path:
    explicit_root = os.environ.get("TAXMATE_AUSTRALIA_ROOT")
    if explicit_root:
        candidate = Path(explicit_root).expanduser().resolve()
        if candidate.joinpath(".codex-plugin", "plugin.json").exists():
            return candidate

    for candidate in (start, *start.parents):
        if candidate.joinpath(".codex-plugin", "plugin.json").exists():
            return candidate

    return Path.cwd()


def _normalize_arch(machine: str) -> str:
    machine = machine.lower()
    if machine in {"x86_64", "amd64"}:
        return "amd64"
    if machine in {"aarch64", "arm64"}:
        return "arm64"
    return ""


def _platform_labels() -> List[str]:
    os_name = platform.system().lower()
    labels = OS_PLATFORMS.get(os_name, [])
    if not labels:
        return []

    machine = _normalize_arch(platform.machine())
    if not machine:
        return labels

    preferred = [
        f"{os_name}-{machine}",
        f"{os_name}_{machine}",
    ]
    remaining = [item for item in labels if item not in preferred]
    return preferred + remaining


def _binary_name(command: str) -> str:
    binary = BINARY_TEMPLATE.format(command=command)
    if os.name == "nt" and not binary.endswith(".exe"):
        return f"{binary}.exe"
    return binary


def _binary_candidates(root: Path, command: str) -> List[Path]:
    binary = _binary_name(command)
    return [
        root / "bin" / binary,
        Path.home() / ".cache" / "taxmate-australia" / "bin" / binary,
    ]


def _find_local_binary(command: str, root: Path) -> Optional[Path]:
    for candidate in _binary_candidates(root, command):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _ensure_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode() | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract_binary(archive_path: Path, command: str) -> Optional[Path]:
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zf:
            candidates = [
                name
                for name in zf.namelist()
                if f"taxmate-australia-{command}" in Path(name).name
            ]
            if not candidates:
                return None
            extracted = zf.extract(candidates[0], path=archive_path.parent)
            return Path(extracted)

    if archive_path.suffixes[-2:] == [".tar", ".gz"]:
        with tarfile.open(archive_path, "r:gz") as tf:
            candidates = [
                name for name in tf.getnames() if f"taxmate-australia-{command}" in Path(name).name
            ]
            if not candidates:
                return None
            tf.extract(candidates[0], path=archive_path.parent)
            return Path(archive_path.parent) / candidates[0]

    return None


def _download_release_binary(command: str, cache_dir: Path) -> Path:
    api_url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
    headers = {
        "User-Agent": "taxmate-australia-runtime",
        "Accept": "application/vnd.github+json",
    }

    try:
        with urlopen(Request(api_url, headers=headers), timeout=20) as response:
            payload = json.load(response)
    except Exception as exc:
        raise RuntimeError("unable to load release metadata") from exc

    assets = payload.get("assets", [])
    if not assets:
        raise RuntimeError("release has no assets")

    desired_prefix = f"taxmate-australia-{command}"
    labels = _platform_labels()
    selected = None
    for label in labels:
        normalized_label = label.replace("_", "-")
        for asset in assets:
            name = str(asset.get("name", "")).lower()
            if desired_prefix in name and normalized_label in name:
                selected = asset
                break
        if selected is not None:
            break

    if selected is None:
        raise RuntimeError(f"no compatible release asset for {command} on this platform")

    download_url = selected.get("browser_download_url")
    if not download_url:
        raise RuntimeError("release asset is missing download URL")

    cache_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / str(selected["name"]) 
        with urlopen(download_url, timeout=30) as remote, tmp_path.open("wb") as file:
            file.write(remote.read())

        extracted = _extract_binary(tmp_path, command)
        source = extracted or tmp_path

        target = cache_dir / _binary_name(command)
        target.write_bytes(source.read_bytes())
        _ensure_executable(target)
        return target


def _run_local_binary(binary: Path, command: str, args: List[str], root: Path) -> int:
    return subprocess.run([str(binary), *args], cwd=str(root)).returncode



def _run_python_command(script: str, args: List[str], root: Path) -> int:
    script_path = Path(__file__).resolve().parent / script
    if not script_path.exists():
        print(f"error: missing script {script}", file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, str(script_path), *args], cwd=str(root)).returncode


def _dispatch(command: str, args: List[str]) -> int:
    root = _find_repo_root(Path.cwd())
    if command in {"calc", "finance", "refresh", "skills", "validate"}:
        script = {
            "calc": "taxmate_calc.py",
            "finance": "taxmate_finance.py",
            "refresh": "taxmate_refresh.py",
            "skills": "taxmate_skills.py",
            "validate": "taxmate_validate.py",
        }[command]
        return _run_python_command(script, args, root)

    local = _find_local_binary(command, root)

    if local is not None:
        return _run_local_binary(local, command, args, root)

    skip_release_fetch = os.environ.get("TAXMATE_AUSTRALIA_SKIP_RELEASE_FETCH", "0") == "1"
    if not skip_release_fetch:
        try:
            cache_dir = Path.home() / ".cache" / "taxmate-australia" / "bin"
            release_binary = _download_release_binary(command, cache_dir)
            return _run_local_binary(release_binary, command, args, root)
        except Exception as exc:  # noqa: BLE001
            print(f"warning: {exc}", file=sys.stderr)

    print(
        "error: no local binary and no release binary available",
        file=sys.stderr,
    )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run full-runtime TaxMate Australia commands.")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main(argv: List[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return _dispatch(args.command, list(args.args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
