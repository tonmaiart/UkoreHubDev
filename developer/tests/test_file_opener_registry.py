from pathlib import Path

from core.extensibility.file_opener import FileOpenerRegistry, FileOpenerSpec


def _spec(plugin_id, extensions, opener=None):
    return FileOpenerSpec(
        plugin_id=plugin_id,
        extensions=frozenset(extensions),
        opener=opener or (lambda path, repo: True),
    )


def test_find_opener_matches_extension():
    registry = FileOpenerRegistry()
    spec = _spec("maya_launcher", {".ma", ".mb"})
    registry.register(spec)

    found = registry.find_opener(Path("scene.ma"))

    assert found is spec.opener


def test_no_match_when_extension_differs():
    registry = FileOpenerRegistry()
    registry.register(_spec("maya_launcher", {".ma", ".mb"}))

    found = registry.find_opener(Path("readme.txt"))

    assert found is None


def test_extension_matching_is_case_insensitive():
    registry = FileOpenerRegistry()
    spec = _spec("maya_launcher", {".ma", ".mb"})
    registry.register(spec)

    found = registry.find_opener(Path("SCENE.MA"))

    assert found is spec.opener


def test_multiple_registrations_first_match_wins():
    registry = FileOpenerRegistry()
    first = _spec("plugin_a", {".ma"})
    second = _spec("plugin_b", {".ma"})
    registry.register(first)
    registry.register(second)

    found = registry.find_opener(Path("scene.ma"))

    assert found is first.opener


def test_duplicate_registration_is_allowed_not_a_dict_keyed_registry():
    registry = FileOpenerRegistry()
    registry.register(_spec("maya_launcher", {".ma"}))
    registry.register(_spec("maya_launcher", {".ma"}))  # should not raise

    assert len(registry._specs) == 2
