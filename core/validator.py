from __future__ import annotations

import os
import socket


class ValidationError(ValueError):
    """Raised when a minidlna.conf value fails validation."""


MEDIA_DIR_TYPES = {"A", "P", "V"}
LOG_CATEGORIES = {
    "general",
    "artwork",
    "database",
    "inotify",
    "scanner",
    "metadata",
    "http",
    "ssdp",
    "tivo",
}
LOG_LEVELS = {"off", "fatal", "error", "warn", "info", "debug"}


def validate_port(value: str, check_in_use: bool = True) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"port inválida: {value!r}") from exc
    if not 1 <= port <= 65535:
        raise ValidationError(f"port fora do intervalo válido (1-65535): {port}")
    if check_in_use and _port_in_use(port):
        raise ValidationError(f"port {port} já está em uso")
    return port


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return True
    return False


def parse_media_dir(value: str) -> tuple[str | None, str]:
    if "," in value:
        type_part, _, path = value.partition(",")
        return type_part.strip(), path.strip()
    return None, value.strip()


def validate_media_dir(value: str, check_fs: bool = True) -> tuple[str | None, str]:
    type_part, path = parse_media_dir(value)
    if type_part is not None:
        is_known_subset = type_part and all(ch in MEDIA_DIR_TYPES for ch in type_part)
        has_duplicates = len(set(type_part)) != len(type_part)
        if not is_known_subset or has_duplicates:
            raise ValidationError(f"tipo de media_dir inválido: {type_part!r}")
    if not path:
        raise ValidationError("media_dir sem path")
    if check_fs:
        if not os.path.isdir(path):
            raise ValidationError(f"path de media_dir não existe ou não é um diretório: {path}")
        if not os.access(path, os.R_OK):
            raise ValidationError(f"path de media_dir não é legível: {path}")
    return type_part, path


def validate_log_level(value: str) -> None:
    if not value.strip():
        raise ValidationError("log_level vazio")
    tokens = [t.strip() for t in value.split(",")]
    if not any("=" in token for token in tokens):
        raise ValidationError(
            f"log_level deve especificar um nível (ex.: general=warn): {value!r}"
        )
    for token in tokens:
        if "=" in token:
            category, _, level = token.partition("=")
            category = category.strip()
            level = level.strip()
            if category and category not in LOG_CATEGORIES:
                raise ValidationError(f"categoria de log inválida: {category!r}")
            if level not in LOG_LEVELS:
                raise ValidationError(f"nível de log inválido: {level!r}")
        elif token not in LOG_CATEGORIES:
            raise ValidationError(f"categoria de log inválida: {token!r}")
