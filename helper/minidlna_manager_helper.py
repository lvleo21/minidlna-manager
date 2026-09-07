#!/usr/bin/env python3
"""Privileged helper for minidlna-manager, invoked via pkexec.

Accepts only a fixed set of subcommands (enforced by argparse's
subparsers) and never runs a caller-supplied command; the config path
written by `write-config` is likewise hardcoded rather than accepted
as an argument, since this process runs as root once authorized.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

SERVICE_NAME = "minidlna.service"
PACKAGE_NAME = "minidlna"
DEFAULT_CONFIG_PATH = "/etc/minidlna.conf"
SYSTEMCTL_TIMEOUT = 30
INSTALL_TIMEOUT = 600

PACKAGE_MANAGER_BINARIES = {
    "apt": "apt-get",
    "dnf": "dnf",
    "pacman": "pacman",
    "zypper": "zypper",
}
INSTALL_COMMANDS = {
    "apt": ["apt-get", "install", "-y", PACKAGE_NAME],
    "dnf": ["dnf", "install", "-y", PACKAGE_NAME],
    "pacman": ["pacman", "-S", "--noconfirm", PACKAGE_NAME],
    "zypper": ["zypper", "install", "-y", PACKAGE_NAME],
}
PACKAGE_CHECK_COMMANDS = {
    "apt": ["dpkg", "-s", PACKAGE_NAME],
    "dnf": ["rpm", "-q", PACKAGE_NAME],
    "pacman": ["pacman", "-Qi", PACKAGE_NAME],
    "zypper": ["rpm", "-q", PACKAGE_NAME],
}


def detect_package_manager() -> str | None:
    for name, binary in PACKAGE_MANAGER_BINARIES.items():
        if shutil.which(binary):
            return name
    return None


def _is_package_installed(manager: str) -> bool:
    command = PACKAGE_CHECK_COMMANDS[manager]
    if not shutil.which(command[0]):
        return False
    proc = subprocess.run(command, capture_output=True, text=True, check=False)
    return proc.returncode == 0


def is_installed() -> dict:
    binary_path = shutil.which("minidlnad")
    package_manager = detect_package_manager()
    package_installed = bool(package_manager) and _is_package_installed(package_manager)
    return {
        "ok": True,
        "installed": bool(binary_path) or package_installed,
        "binary_path": binary_path,
        "package_manager": package_manager,
    }


def install_package() -> dict:
    manager = detect_package_manager()
    if manager is None:
        return {
            "ok": False,
            "package_manager": None,
            "error": "nenhum gerenciador de pacotes suportado (apt/dnf/pacman/zypper) foi encontrado",
        }
    try:
        proc = subprocess.run(
            INSTALL_COMMANDS[manager],
            capture_output=True,
            text=True,
            timeout=INSTALL_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "package_manager": manager, "error": "instalação excedeu o tempo limite"}
    return {
        "ok": proc.returncode == 0,
        "package_manager": manager,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def systemctl_action(action: str) -> dict:
    try:
        proc = subprocess.run(
            ["systemctl", action, SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=SYSTEMCTL_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "action": action, "error": f"'{action}' excedeu o tempo limite"}
    return {
        "ok": proc.returncode == 0,
        "action": action,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def write_config(content: str, path: str = DEFAULT_CONFIG_PATH) -> dict:
    if not content.strip():
        return {"ok": False, "path": path, "error": "conteúdo de config vazio"}
    try:
        # minidlnad drops privileges to run as its own user/group, so it
        # needs to be able to read this file; preserve the mode of the file
        # being replaced (or fall back to a world-readable default for a
        # brand new one) rather than inheriting mkstemp's 0600.
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        mode = 0o644
    directory = os.path.dirname(path) or "."
    try:
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".minidlna.conf.")
    except OSError as exc:
        return {"ok": False, "path": path, "error": str(exc)}
    try:
        os.chmod(tmp_path, mode)
        with os.fdopen(fd, "w") as tmp_file:
            tmp_file.write(content)
        os.replace(tmp_path, path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        return {"ok": False, "path": path, "error": str(exc)}
    return {"ok": True, "path": path}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minidlna-manager-helper")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("is-installed")
    subparsers.add_parser("install-package")
    subparsers.add_parser("write-config")
    for action in ("start", "stop", "restart", "enable", "disable"):
        subparsers.add_parser(action)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.action == "is-installed":
        result = is_installed()
    elif args.action == "install-package":
        result = install_package()
    elif args.action == "write-config":
        result = write_config(sys.stdin.read())
    else:
        result = systemctl_action(args.action)

    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
