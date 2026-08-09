from pathlib import Path

from core.events.hooks import AppLifecycleContext, AppLifecycleHooks


def _context(tmp_path) -> AppLifecycleContext:
    return AppLifecycleContext(project=None, repo=None, repo_path=Path(tmp_path))


def test_subscribe_and_fire_calls_handler(tmp_path):
    hooks = AppLifecycleHooks()
    received = []
    hooks.subscribe_app_start(received.append)

    context = _context(tmp_path)
    failures = hooks.fire_app_start(context)

    assert received == [context]
    assert failures == []


def test_fire_with_no_subscribers_is_noop(tmp_path):
    hooks = AppLifecycleHooks()
    assert hooks.fire_app_start(_context(tmp_path)) == []


def test_multiple_handlers_all_run(tmp_path):
    hooks = AppLifecycleHooks()
    calls = []
    hooks.subscribe_repo_changed(lambda ctx: calls.append("a"))
    hooks.subscribe_repo_changed(lambda ctx: calls.append("b"))

    hooks.fire_repo_changed(_context(tmp_path))

    assert calls == ["a", "b"]


def test_handler_exception_is_isolated_and_collected(tmp_path):
    hooks = AppLifecycleHooks()
    calls = []

    def broken(_ctx):
        raise RuntimeError("boom")

    hooks.subscribe_repo_changed(broken)
    hooks.subscribe_repo_changed(lambda ctx: calls.append("still runs"))

    failures = hooks.fire_repo_changed(_context(tmp_path))

    assert calls == ["still runs"]
    assert len(failures) == 1
    assert isinstance(failures[0], RuntimeError)


def test_lifecycle_points_are_isolated_from_each_other(tmp_path):
    hooks = AppLifecycleHooks()
    calls = []
    hooks.subscribe_app_start(lambda ctx: calls.append("start"))
    hooks.subscribe_app_close(lambda ctx: calls.append("close"))

    hooks.fire_app_start(_context(tmp_path))

    assert calls == ["start"]
