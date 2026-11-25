from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from plugin_api.registries.registry_base import KeyedOrderedRegistry

logger = logging.getLogger("FileContextActions")


@dataclass(frozen=True)
class FileContextActionSpec:
    """One plugin-contributed entry in a file browser's right-click menu
    (plugins/core/explorer's file table). `match` gets the right-clicked
    paths (files and/or folders, absolute) and decides whether the entry
    shows at all; `run` gets the same list when it's clicked. Both run on
    the UI thread at menu time, so `match` should stay cheap (no recursive
    folder scans)."""

    key: str
    label: str
    order: int
    match: Callable[[list[Path]], bool]
    run: Callable[[list[Path]], None]


class FileContextActionRegistry(KeyedOrderedRegistry[FileContextActionSpec]):
    """Open, ordered collection of FileContextActionSpecs — lets a plugin
    (e.g. MayaPublisher's "Add to Maya Publish Queue") add to Explorer's
    context menu without Explorer knowing about it. A raising `match` is
    logged and treated as no match, so one broken plugin can't break the
    menu for everyone."""

    def __init__(self) -> None:
        super().__init__(label="File context action")

    def actions_for(self, paths: list[Path]) -> list[FileContextActionSpec]:
        matched = []
        for spec in self.ordered():
            try:
                if spec.match(list(paths)):
                    matched.append(spec)
            except Exception:
                logger.exception(f"match() of file context action '{spec.key}' raised")
        return matched
