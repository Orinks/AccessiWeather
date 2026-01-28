# Custom PyInstaller hook for sound_lib
# Excludes incompatible x86 (i386/ppc) binaries on macOS ARM64 runners.
# Only includes x64 dylibs which work under Rosetta 2 on Apple Silicon.
# Based on approach from https://github.com/masonasons/FastSM

import sys
from pathlib import Path

binaries = []

if sys.platform == "darwin":
    # On macOS, only include x64 dylibs — the x86 directory contains old
    # i386/ppc binaries that PyInstaller can't process on ARM64 runners.
    try:
        import sound_lib

        sl_path = Path(sound_lib.__file__).parent
        x64_lib = sl_path / "lib" / "x64"
        if x64_lib.exists():
            for dylib in x64_lib.glob("*.dylib"):
                binaries.append((str(dylib), "sound_lib/lib/x64"))
    except ImportError:
        pass
else:
    # On Windows/Linux, use the default behavior
    from PyInstaller.utils.hooks import collect_dynamic_libs

    binaries = collect_dynamic_libs("sound_lib")
