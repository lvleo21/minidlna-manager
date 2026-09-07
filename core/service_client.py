"""Client-side wrapper that calls the privileged helper via pkexec.

`is-installed` never needs privilege, so it runs the helper directly;
every other action goes through pkexec, which enforces Polkit
authentication before the helper (running as root) does anything.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

INSTALLED_HELPER_PATH = "/usr/lib/minidlna-manager/helper"
DEV_HELPER_PATH = str(Path(__file__).resolve().parent.parent / "helper" / "minidlna_manager_helper.py")

DEFAULT_TIMEOUT = 30
INSTALL_TIMEOUT = 600

PKEXEC_AUTH_DENIED = 126
PKEXEC_EXEC_NOT_FOUND = 127


class ServiceClientError(Exception):
    """Base error for failures talking to the privileged helper."""


class HelperNotFoundError(ServiceClientError):
    """Raised when pkexec or the helper executable can't be located/run."""


class PermissionDeniedError(ServiceClientError):
    """Raised when Polkit authentication was denied or cancelled."""


class HelperTimeoutError(ServiceClientError):
    """Raised when a helper invocation exceeds its timeout."""


def _helper_path() -> str:
    override = os.environ.get("MINIDLNA_MANAGER_HELPER")
    if override:
        return override
    if os.path.exists(INSTALLED_HELPER_PATH):
        return INSTALLED_HELPER_PATH
    return DEV_HELPER_PATH


def _parse_result(proc: subprocess.CompletedProcess) -> dict:
    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }


def _run_unprivileged(action: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    helper = _helper_path()
    try:
        proc = subprocess.run(
            [helper, action], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (FileNotFoundError, PermissionError) as exc:
        raise HelperNotFoundError(f"helper não encontrado ou não executável em {helper}") from exc
    except subprocess.TimeoutExpired as exc:
        raise HelperTimeoutError(f"'{action}' excedeu o tempo limite") from exc
    return _parse_result(proc)


def _run_privileged(action: str, stdin_data: str | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    helper = _helper_path()
    try:
        proc = subprocess.run(
            ["pkexec", helper, action],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HelperNotFoundError("pkexec não encontrado — o Polkit está instalado?") from exc
    except subprocess.TimeoutExpired as exc:
        raise HelperTimeoutError(f"'{action}' excedeu o tempo limite") from exc

    if proc.returncode == PKEXEC_AUTH_DENIED:
        raise PermissionDeniedError("autenticação negada ou cancelada pelo usuário")
    if proc.returncode == PKEXEC_EXEC_NOT_FOUND:
        raise HelperNotFoundError(f"helper não encontrado ou não executável em {helper}")

    return _parse_result(proc)


def is_installed() -> dict:
    return _run_unprivileged("is-installed")


def start() -> dict:
    return _run_privileged("start")


def stop() -> dict:
    return _run_privileged("stop")


def restart() -> dict:
    return _run_privileged("restart")


def enable() -> dict:
    return _run_privileged("enable")


def disable() -> dict:
    return _run_privileged("disable")


def install_package() -> dict:
    return _run_privileged("install-package", timeout=INSTALL_TIMEOUT)


def write_config(content: str) -> dict:
    return _run_privileged("write-config", stdin_data=content)


def _main(argv: list[str] | None = None) -> int:
    """Manual QA entry point: `python -m core.service_client <ação>`."""
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("uso: python -m core.service_client <is-installed|start|stop|restart|enable|disable|install-package>")
        return 2

    actions = {
        "is-installed": is_installed,
        "start": start,
        "stop": stop,
        "restart": restart,
        "enable": enable,
        "disable": disable,
        "install-package": install_package,
    }
    func = actions.get(argv[0])
    if func is None:
        print(f"ação desconhecida: {argv[0]}")
        return 2

    try:
        result = func()
    except ServiceClientError as exc:
        print(f"erro: {exc}")
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(_main())
