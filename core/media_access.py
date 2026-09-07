"""Grants the minidlna service account read access to a media directory.

minidlnad runs as its own unprivileged user (see helper's SERVICE_NAME),
so a folder picked from inside the invoking user's home directory —
typically mode 750/700 — is otherwise unreadable to it. Fixing that is
just the invoking user managing their own files' ACLs, so this never
needs pkexec/the privileged helper.
"""
from __future__ import annotations

import os
import subprocess

SERVICE_USER = "minidlna"
SETFACL_TIMEOUT = 30


class SetfaclError(Exception):
    """Raised when granting ACL access via setfacl fails."""


def _setfacl(args: list[str]) -> None:
    try:
        subprocess.run(
            ["setfacl", *args], capture_output=True, text=True, timeout=SETFACL_TIMEOUT, check=True
        )
    except FileNotFoundError as exc:
        raise SetfaclError("comando 'setfacl' não encontrado — instale o pacote 'acl'") from exc
    except subprocess.TimeoutExpired as exc:
        raise SetfaclError("setfacl excedeu o tempo limite") from exc
    except subprocess.CalledProcessError as exc:
        raise SetfaclError(exc.stderr.strip() or str(exc)) from exc


def grant_directory_access(path: str, user: str = SERVICE_USER) -> dict:
    """Grant `user` traverse access down to `path` and read+traverse on
    `path` itself (existing entries and, via a default ACL, future ones
    too). Only ever widens access for this single service account —
    never "other" — and only within the invoking user's home directory.
    """
    home = os.path.expanduser("~")
    target = os.path.realpath(path)

    if target != home and not target.startswith(home + os.sep):
        return {
            "ok": False,
            "path": path,
            "error": f"{path} está fora do diretório pessoal; ajuste o acesso manualmente",
        }

    chain = [target]
    current = target
    while current != home:
        current = os.path.dirname(current)
        chain.append(current)
    chain.reverse()

    try:
        for directory in chain[:-1]:
            _setfacl(["-m", f"u:{user}:x", directory])
        _setfacl(["-R", "-m", f"u:{user}:rx", target])
        _setfacl(["-R", "-d", "-m", f"u:{user}:rx", target])
    except SetfaclError as exc:
        return {"ok": False, "path": path, "error": str(exc)}

    return {"ok": True, "path": path}
