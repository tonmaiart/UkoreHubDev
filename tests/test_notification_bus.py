import pytest

from core.extensibility import notification_bus


@pytest.fixture(autouse=True)
def _clear_bus():
    notification_bus.clear()
    yield
    notification_bus.clear()


def test_entries_for_matches_repo_specific_entry():
    notification_bus.push("Source", "proj", "repo_a", "hello")

    assert [e.label for e in notification_bus.entries_for("proj", "repo_a")] == ["hello"]
    assert notification_bus.entries_for("proj", "repo_b") == []
    assert notification_bus.entries_for("other_proj", "repo_a") == []


def test_entries_for_includes_project_wide_entry_for_any_repo():
    notification_bus.push("Source", "proj", None, "project wide")

    assert [e.label for e in notification_bus.entries_for("proj", "repo_a")] == ["project wide"]
    assert [e.label for e in notification_bus.entries_for("proj", "repo_b")] == ["project wide"]
    assert notification_bus.entries_for("other_proj", "repo_a") == []


def test_entries_for_sorted_newest_first():
    notification_bus.push("Source", "proj", None, "first")
    notification_bus.push("Source", "proj", None, "second")

    assert [e.label for e in notification_bus.entries_for("proj", None)] == ["second", "first"]


def test_push_notifies_listeners():
    received = []
    notification_bus.add_listener(received.append)

    entry = notification_bus.push("Source", "proj", None, "hello")

    assert received == [entry]
    notification_bus.remove_listener(received.append)


def test_clear_empties_entries():
    notification_bus.push("Source", "proj", None, "hello")

    notification_bus.clear()

    assert notification_bus.entries() == []
