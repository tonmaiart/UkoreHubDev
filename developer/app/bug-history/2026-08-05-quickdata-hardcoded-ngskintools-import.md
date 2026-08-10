# QuickData.py crashed the whole MayaToolkit plugin when ngSkinTools2 wasn't installed

## Symptom

Loading the `ukoreMaya.py` plug-in in Maya failed outright:

```
ModuleNotFoundError: file .../tmlib/core/QuickData.py line 7: No module named 'ngSkinTools2'
Warning: Failed to run file: .../maya-plug-ins/ukoreMaya.py
```

This happened on any machine without the third-party ngSkinTools2 package
installed — the entire Ukore Studio Tool menu failed to load, not just the
ngSkinTools-specific features.

## Root cause

`plugins/repo_internal/MayaToolkit/maya-scripts/tmlib/core/QuickData.py`
had unconditional module-level imports:

```python
import ngSkinTools2
from ngSkinTools2.api import import_export
from ngSkinTools2.operations import removeLayerData
from ngSkinTools2.api import transfer
```

`ukoreMaya.py`'s startup path (`Plugin.reload_scripts()`) imports every
`tmlib.core` module eagerly, including `QuickData`, so a missing
third-party dependency for one optional feature (SkinNG import/export)
took down plugin load entirely.

A second, narrower instance of the same shape existed in
`maya-scripts/WeightPuller/interface.py`: `from ngSkinTools2.api import
get_layers_enabled` sat *above* the `try:` block meant to catch its
absence, so it would have raised uncaught on click rather than falling
back to the plain Maya weight-move path.

## Fix

- `QuickData.py`: wrapped the ngSkinTools2 imports in `try/except
  ImportError`, setting `NGSKINTOOLS_AVAILABLE`. `import_skin_quick`'s
  and `export_skin_quick`'s `import_ng`/`export_ng` branches now check
  the flag first and emit `cmds.displayWarning(...)` instead of
  importing ngSkinTools2 APIs when it's unavailable.
- `WeightPuller/interface.py`: moved the `from ngSkinTools2.api import
  get_layers_enabled` import inside the existing `try:` block so a
  missing package falls through to the existing Maya-native fallback
  instead of raising.

## Lesson

A third-party dependency needed by only one optional feature must never
be imported at module top level in a file that sits on a shared eager-load
path (here, `Plugin.reload_scripts()` importing all of `tmlib.core`).
Guard it with `try/except ImportError` at the top of the file (a single
`_AVAILABLE` flag checked at each call site), and when an import is
deliberately deferred inside a function to avoid this exact problem, make
sure the import statement itself is inside the `try` block that's meant to
catch its absence — not just the code that uses it.
