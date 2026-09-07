import socket

import pytest

from core.validator import (
    ValidationError,
    format_log_level,
    format_media_dir,
    parse_log_level,
    validate_log_level,
    validate_media_dir,
    validate_port,
)


def test_validate_port_accepts_valid_value():
    assert validate_port("8200", check_in_use=False) == 8200


@pytest.mark.parametrize("value", ["not-a-number", "", "8200.5", None])
def test_validate_port_rejects_non_integer(value):
    with pytest.raises(ValidationError):
        validate_port(value, check_in_use=False)


@pytest.mark.parametrize("value", ["0", "-1", "65536", "999999"])
def test_validate_port_rejects_out_of_range(value):
    with pytest.raises(ValidationError):
        validate_port(value, check_in_use=False)


def test_validate_port_rejects_port_already_in_use():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("0.0.0.0", 0))
        busy_port = sock.getsockname()[1]
        with pytest.raises(ValidationError):
            validate_port(str(busy_port), check_in_use=True)


def test_validate_media_dir_without_type_has_no_type(tmp_path):
    type_part, _path = validate_media_dir(str(tmp_path))
    assert type_part is None


def test_validate_media_dir_without_type_keeps_the_path(tmp_path):
    _type_part, path = validate_media_dir(str(tmp_path))
    assert path == str(tmp_path)


def test_validate_media_dir_with_type_returns_the_type(tmp_path):
    type_part, _path = validate_media_dir(f"A,{tmp_path}")
    assert type_part == "A"


def test_validate_media_dir_with_type_keeps_the_path(tmp_path):
    _type_part, path = validate_media_dir(f"A,{tmp_path}")
    assert path == str(tmp_path)


def test_validate_media_dir_accepts_multiple_type_letters(tmp_path):
    type_part, _ = validate_media_dir(f"PV,{tmp_path}")
    assert type_part == "PV"


@pytest.mark.parametrize("bad_type", ["X", "AX", "AA"])
def test_validate_media_dir_rejects_invalid_type(tmp_path, bad_type):
    with pytest.raises(ValidationError):
        validate_media_dir(f"{bad_type},{tmp_path}")


def test_validate_media_dir_rejects_missing_path():
    with pytest.raises(ValidationError):
        validate_media_dir("A,")


def test_validate_media_dir_rejects_nonexistent_path(tmp_path):
    with pytest.raises(ValidationError):
        validate_media_dir(str(tmp_path / "does-not-exist"))


def test_validate_media_dir_skips_filesystem_check_when_disabled():
    type_part, path = validate_media_dir("A,/does/not/exist", check_fs=False)
    assert (type_part, path) == ("A", "/does/not/exist")


def test_validate_log_level_accepts_known_form():
    validate_log_level("general,artwork,database=warn")


def test_validate_log_level_accepts_bare_category_before_assignment():
    validate_log_level("general,http=info")


@pytest.mark.parametrize("value", ["", "   "])
def test_validate_log_level_rejects_empty(value):
    with pytest.raises(ValidationError):
        validate_log_level(value)


def test_validate_log_level_rejects_value_without_level_assignment():
    with pytest.raises(ValidationError):
        validate_log_level("general,artwork")


def test_validate_log_level_rejects_unknown_category():
    with pytest.raises(ValidationError):
        validate_log_level("not-a-category=warn")


def test_validate_log_level_rejects_unknown_level():
    with pytest.raises(ValidationError):
        validate_log_level("general=not-a-level")


def test_format_media_dir_joins_type_and_path():
    assert format_media_dir("A", "/srv/media/music") == "A,/srv/media/music"


def test_format_media_dir_omits_type_when_none():
    assert format_media_dir(None, "/srv/media/mixed") == "/srv/media/mixed"


def test_parse_log_level_reads_the_categories():
    categories, _level = parse_log_level("general,artwork=warn")
    assert categories == {"general", "artwork"}


def test_parse_log_level_reads_the_level():
    _categories, level = parse_log_level("general,artwork=warn")
    assert level == "warn"


def test_parse_log_level_falls_back_to_default_level_for_empty_value():
    _categories, level = parse_log_level("", default_level="info")
    assert level == "info"


def test_parse_log_level_returns_no_categories_for_empty_value():
    categories, _level = parse_log_level("")
    assert categories == set()


def test_parse_log_level_uses_the_last_level_token_when_mixed():
    _categories, level = parse_log_level("general=warn,artwork=debug")
    assert level == "debug"


def test_format_log_level_joins_sorted_categories_with_the_level():
    assert format_log_level({"artwork", "general"}, "warn") == "artwork,general=warn"


def test_format_log_level_returns_empty_string_for_no_categories():
    assert format_log_level(set(), "warn") == ""
