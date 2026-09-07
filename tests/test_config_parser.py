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


def test_load_reads_and_parses_file(tmp_path, sample_text):
    config_path = tmp_path / "minidlna.conf"
    config_path.write_text(sample_text)
    config = MiniDLNAConfig.load(str(config_path))
    assert config.get("port") == "8200"


def test_load_raises_when_file_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        MiniDLNAConfig.load(str(tmp_path / "does-not-exist.conf"))


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


def test_set_replaces_value_at_the_same_line(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.set("port", "9200")
    lines = config.serialize().splitlines()
    assert lines.index("port=9200") == sample_text.splitlines().index("port=8200")


def test_set_replaces_value_read_back_by_get(sample_text):
    config = MiniDLNAConfig.parse(sample_text)
    config.set("port", "9200")
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


@pytest.fixture
def serialized_after_edits(sample_text) -> str:
    config = MiniDLNAConfig.parse(sample_text)
    config.set("port", "9200")
    config.add("media_dir", "P,/srv/media/photos")
    return config.serialize()


def test_edits_preserve_leading_comment(serialized_after_edits):
    assert "# Sample minidlna.conf used by the test suite." in serialized_after_edits


def test_edits_preserve_section_comment(serialized_after_edits):
    assert "# Network" in serialized_after_edits


def test_edits_preserve_blank_line_count(sample_text, serialized_after_edits):
    assert serialized_after_edits.count("\n\n") == sample_text.count("\n\n")


@pytest.fixture
def reparsed_after_edit_cycle(sample_text) -> MiniDLNAConfig:
    """parse -> edit -> serialize -> reparse, exercising the full round
    trip the Sprint 1 acceptance criterion describes."""
    config = MiniDLNAConfig.parse(sample_text)
    config.set("port", "9200")
    config.remove("media_dir", "V,/srv/media/videos")
    config.add("media_dir", "P,/srv/media/photos")
    return MiniDLNAConfig.parse(config.serialize())


def test_edit_cycle_applies_the_port_change(reparsed_after_edit_cycle):
    assert reparsed_after_edit_cycle.get("port") == "9200"


def test_edit_cycle_applies_the_media_dir_changes(reparsed_after_edit_cycle):
    assert reparsed_after_edit_cycle.get_all("media_dir") == [
        "A,/srv/media/music",
        "/srv/media/mixed",
        "P,/srv/media/photos",
    ]


def test_edit_cycle_leaves_network_interface_untouched(reparsed_after_edit_cycle):
    assert reparsed_after_edit_cycle.get("network_interface") == "eth0"


def test_edit_cycle_leaves_friendly_name_untouched(reparsed_after_edit_cycle):
    assert reparsed_after_edit_cycle.get("friendly_name") == "MiniDLNA"


def test_edit_cycle_leaves_log_level_untouched(reparsed_after_edit_cycle):
    assert reparsed_after_edit_cycle.get("log_level") == (
        "general,artwork,database,inotify,scanner,metadata,http,ssdp,tivo=warn"
    )
