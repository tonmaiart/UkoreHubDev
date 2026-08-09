import pytest

from core.events.notification_bus import NotificationBus


@pytest.fixture
def bus():
    return NotificationBus()


def test_entries_for_matches_repo_specific_entry(bus):
    bus.push("Source", "proj", "repo_a", "hello")

    assert [e.label for e in bus.entries_for("proj", "repo_a")] == ["hello"]
    assert bus.entries_for("proj", "repo_b") == []
    assert bus.entries_for("other_proj", "repo_a") == []


def test_entries_for_includes_project_wide_entry_for_any_repo(bus):
    bus.push("Source", "proj", None, "project wide")

    assert [e.label for e in bus.entries_for("proj", "repo_a")] == ["project wide"]
    assert [e.label for e in bus.entries_for("proj", "repo_b")] == ["project wide"]
    assert bus.entries_for("other_proj", "repo_a") == []


def test_entries_for_sorted_newest_first(bus):
    bus.push("Source", "proj", None, "first")
    bus.push("Source", "proj", None, "second")

    assert [e.label for e in bus.entries_for("proj", None)] == ["second", "first"]


def test_push_notifies_listeners(bus):
    received = []
    bus.add_listener(received.append)

    entry = bus.push("Source", "proj", None, "hello")

    assert received == [entry]
    bus.remove_listener(received.append)


def test_clear_empties_entries(bus):
    bus.push("Source", "proj", None, "hello")

    bus.clear()

    assert bus.entries() == []
