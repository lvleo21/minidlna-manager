from pathlib import Path

import pytest

from core.config_parser import MiniDLNAConfig

FIXTURE = Path(__file__).parent / "fixtures" / "minidlna.conf.sample"


@pytest.fixture
def sample_text() -> str:
    return FIXTURE.read_text()


def test_roundtrip_is_lossless(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    assert config.serialize() == sample_text


def test_get_returns_last_value_for_key(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    assert config.get("port") == "8200"


def test_get_returns_none_for_missing_key(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    assert config.get("does_not_exist") is None


def test_get_all_returns_every_media_dir(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    assert config.get_all("media_dir") == [
        "A,/srv/media/music",
        "V,/srv/media/videos",
        "/srv/media/mixed",
    ]


def test_set_replaces_value_in_place(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.set("port", "9200")
    lines = config.serialize().splitlines()
    assert lines.index("port=9200") == sample_text.splitlines().index("port=8200")
    assert config.get("port") == "9200"


def test_set_appends_when_key_is_absent(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.set("root_container", ".")
    assert config.serialize().splitlines()[-1] == "root_container=."


def test_add_appends_new_repeatable_entry(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.add("media_dir", "P,/srv/media/photos")
    assert config.get_all("media_dir")[-1] == "P,/srv/media/photos"


def test_remove_specific_value_only(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.remove("media_dir", "V,/srv/media/videos")
    assert config.get_all("media_dir") == ["A,/srv/media/music", "/srv/media/mixed"]


def test_remove_all_entries_for_key(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.remove("media_dir")
    assert config.get_all("media_dir") == []


def test_comments_and_blank_lines_are_preserved_after_edits(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.set("port", "9200")
    config.add("media_dir", "P,/srv/media/photos")
    serialized = config.serialize()
    assert "# Sample minidlna.conf used by the test suite." in serialized
    assert "# Network" in serialized
    assert serialized.count("\n\n") == sample_text.count("\n\n")


def test_edit_cycle_is_semantically_equivalent_plus_expected_changes(sample_text):
    config = MiniDLNAConfig.parse(sample_text)

    config.set("port", "9200")
    config.remove("media_dir", "V,/srv/media/videos")
    config.add("media_dir", "P,/srv/media/photos")

    reparsed = MiniDLNAConfig.parse(config.serialize())

    assert reparsed.get("port") == "9200"
    assert reparsed.get_all("media_dir") == [
        "A,/srv/media/music",
        "/srv/media/mixed",
        "P,/srv/media/photos",
    ]
    # everything untouched by the edits above must still match the original
    assert reparsed.get("network_interface") == "eth0"
    assert reparsed.get("friendly_name") == "MiniDLNA"
    assert reparsed.get("log_level") == (
        "general,artwork,database,inotify,scanner,metadata,http,ssdp,tivo=warn"
    )
