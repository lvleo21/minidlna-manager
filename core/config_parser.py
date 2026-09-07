from __future__ import annotations


class MiniDLNAConfig:
    """In-memory, order-preserving representation of a minidlna.conf file.

    Comments and blank lines are kept verbatim on the raw line list so
    serialize() can round-trip a file losslessly; only lines matching
    `key=value` are touched by get/set/add/remove.
    """

    def __init__(self, lines: list[str] | None = None) -> None:
        self._lines: list[str] = list(lines) if lines is not None else []

    @classmethod
    def parse(cls, text: str) -> MiniDLNAConfig:
        return cls(text.splitlines())

    def serialize(self) -> str:
        if not self._lines:
            return ""
        return "\n".join(self._lines) + "\n"

    @staticmethod
    def _split_entry(line: str) -> tuple[str, str] | None:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            return None
        key, _, value = line.partition("=")
        return key.strip(), value.strip()

    def get(self, key: str) -> str | None:
        values = self.get_all(key)
        return values[-1] if values else None

    def get_all(self, key: str) -> list[str]:
        return [
            entry[1]
            for line in self._lines
            if (entry := self._split_entry(line)) is not None and entry[0] == key
        ]

    def set(self, key: str, value: str) -> None:
        """Replace the first entry for `key` in place, or append if absent.

        Any further pre-existing entries for the same key are dropped, since
        `set` is meant for single-value keys (e.g. port, log_level).
        """
        new_lines = []
        replaced = False
        for line in self._lines:
            entry = self._split_entry(line)
            if entry is not None and entry[0] == key:
                if not replaced:
                    new_lines.append(f"{key}={value}")
                    replaced = True
                continue
            new_lines.append(line)
        if not replaced:
            new_lines.append(f"{key}={value}")
        self._lines = new_lines

    def add(self, key: str, value: str) -> None:
        """Append a new entry, for repeatable keys like media_dir."""
        self._lines.append(f"{key}={value}")

    def remove(self, key: str, value: str | None = None) -> None:
        """Remove entries for `key`.

        If `value` is given, only the entry with that exact value is
        removed (e.g. dropping one media_dir among several); otherwise
        every entry for `key` is removed.
        """
        self._lines = [
            line
            for line in self._lines
            if not (
                (entry := self._split_entry(line)) is not None
                and entry[0] == key
                and (value is None or entry[1] == value)
            )
        ]
