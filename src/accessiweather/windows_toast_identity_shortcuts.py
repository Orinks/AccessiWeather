"""Windows shortcut and property-store helpers for toast identity setup."""

from __future__ import annotations

import ctypes
import logging
import sys
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_ole32 = None
_shell32 = None

if sys.platform == "win32":
    from ctypes import HRESULT, POINTER, byref, c_int, c_void_p, windll
    from ctypes.wintypes import DWORD, LPCWSTR, LPWSTR, MAX_PATH, WORD

    _ole32 = windll.ole32
    _shell32 = windll.shell32

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", DWORD),
            ("Data2", WORD),
            ("Data3", WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", DWORD)]

    class PROPVARIANT(ctypes.Structure):
        _fields_ = [
            ("vt", WORD),
            ("wReserved1", WORD),
            ("wReserved2", WORD),
            ("wReserved3", WORD),
            ("pointer_value", c_void_p),
        ]

    # System.AppUserModel.ID property key
    # {9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}, pid 5
    _PKEY_AppUserModel_ID = PROPERTYKEY(
        GUID(0x9F4C2855, 0x9F79, 0x4B39, (0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)),
        5,
    )
    _PKEY_AppUserModel_ToastActivatorCLSID = PROPERTYKEY(
        GUID(0x9F4C2855, 0x9F79, 0x4B39, (0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)),
        26,
    )

    # IID_IPropertyStore = {886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}
    _IID_IPropertyStore = GUID(
        0x886D8EEB, 0x8CF2, 0x4446, (0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99)
    )

    # VT_LPWSTR = 0x001F
    _VT_LPWSTR = 0x001F
    _VT_CLSID = 0x0048

    # GPS_READWRITE = 2
    _GPS_READWRITE = 2


def _guid_from_string(clsid: str) -> GUID:  # pragma: no cover
    """Convert a CLSID string into the local GUID structure."""
    parsed = uuid.UUID(clsid)
    data4 = tuple(parsed.bytes[8:])
    return GUID(parsed.time_low, parsed.time_mid, parsed.time_hi_version, data4)


def _guid_to_string(guid: GUID) -> str:  # pragma: no cover
    """Convert a local GUID structure to uppercase-braced string form."""
    return (
        "{"
        f"{guid.Data1:08X}-{guid.Data2:04X}-{guid.Data3:04X}-"
        f"{guid.Data4[0]:02X}{guid.Data4[1]:02X}-"
        f"{guid.Data4[2]:02X}{guid.Data4[3]:02X}{guid.Data4[4]:02X}"
        f"{guid.Data4[5]:02X}{guid.Data4[6]:02X}{guid.Data4[7]:02X}"
        "}"
    )


def _resolve_start_menu_shortcut_path(display_name: str) -> Path:
    """Find the real Start Menu shortcut path, including nested subfolders."""
    appdata = Path.home() / "AppData" / "Roaming"
    programs_dir = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    nested_default = programs_dir / display_name / f"{display_name}.lnk"
    top_level_default = programs_dir / f"{display_name}.lnk"

    if nested_default.exists():
        return nested_default
    if top_level_default.exists():
        return top_level_default

    for candidate in sorted(programs_dir.rglob(f"{display_name}.lnk")):
        if candidate.is_file():
            return candidate

    return nested_default


def _read_shortcut_target_wscript(shortcut_path: Path) -> str | None:
    """Read shortcut target using the Windows Script Host COM object."""
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore[import-untyped]

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        return shortcut.TargetPath or None
    except ImportError:
        pass

    # Fallback: pythoncom/comtypes not available — try ctypes-only approach
    try:
        return _read_shortcut_target_ctypes(shortcut_path)
    except Exception as exc:
        logger.debug("ctypes shortcut read failed: %s", exc)
        return None


def _read_shortcut_target_ctypes(shortcut_path: Path) -> str | None:
    """Read shortcut target using raw ctypes COM (IShellLinkW + IPersistFile)."""
    if sys.platform != "win32":
        return None

    CLSID_ShellLink = GUID(
        0x00021401, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IShellLinkW = GUID(
        0x000214F9, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IPersistFile = GUID(
        0x0000010B, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )

    CLSCTX_INPROC_SERVER = 1
    p_shell_link = c_void_p()

    hr = _ole32.CoCreateInstance(
        byref(CLSID_ShellLink),
        None,
        CLSCTX_INPROC_SERVER,
        byref(IID_IShellLinkW),
        byref(p_shell_link),
    )
    if hr != 0:
        return None

    # Query IPersistFile
    p_persist_file = c_void_p()
    # Get vtable for IShellLinkW — we need QueryInterface at vtable[0]
    vtable = ctypes.cast(p_shell_link, POINTER(POINTER(c_void_p)))[0]
    query_interface = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p))(
        vtable[0]
    )
    hr = query_interface(p_shell_link, byref(IID_IPersistFile), byref(p_persist_file))
    if hr != 0:
        # Release IShellLinkW
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
        release(p_shell_link)
        return None

    # IPersistFile::Load (vtable index 5)
    pf_vtable = ctypes.cast(p_persist_file, POINTER(POINTER(c_void_p)))[0]
    pf_load = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR, DWORD)(pf_vtable[5])
    hr = pf_load(p_persist_file, str(shortcut_path), 0)

    target = None
    if hr == 0:
        # IShellLinkW::GetPath (vtable index 3)
        get_path = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPWSTR, c_int, c_void_p, DWORD)(vtable[3])
        buf = ctypes.create_unicode_buffer(MAX_PATH)
        hr2 = get_path(p_shell_link, buf, MAX_PATH, None, 0)
        if hr2 == 0 and buf.value:
            target = buf.value

    # Release both interfaces
    pf_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(pf_vtable[2])
    pf_release(p_persist_file)
    sl_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
    sl_release(p_shell_link)

    return target


def _create_shortcut(shortcut_path: Path, target_path: str, display_name: str) -> bool:
    """Create a .lnk shortcut file."""
    if sys.platform != "win32":
        return False

    shortcut_path.parent.mkdir(parents=True, exist_ok=True)

    # Try win32com first (most reliable for shortcut creation)
    try:
        import win32com.client  # type: ignore[import-untyped]

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = target_path
        shortcut.WorkingDirectory = str(Path(target_path).parent)
        shortcut.Description = display_name
        shortcut.IconLocation = f"{target_path},0"
        shortcut.Save()
        return True
    except ImportError:
        pass

    # Fallback: raw ctypes COM with IShellLinkW + IPersistFile
    return _create_shortcut_ctypes(shortcut_path, target_path, display_name)


def _create_shortcut_ctypes(shortcut_path: Path, target_path: str, display_name: str) -> bool:
    """Create a .lnk shortcut using raw ctypes COM."""
    if sys.platform != "win32":
        return False

    CLSID_ShellLink = GUID(
        0x00021401, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IShellLinkW = GUID(
        0x000214F9, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )
    IID_IPersistFile = GUID(
        0x0000010B, 0x0000, 0x0000, (0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46)
    )

    CLSCTX_INPROC_SERVER = 1
    p_shell_link = c_void_p()

    hr = _ole32.CoCreateInstance(
        byref(CLSID_ShellLink),
        None,
        CLSCTX_INPROC_SERVER,
        byref(IID_IShellLinkW),
        byref(p_shell_link),
    )
    if hr != 0:
        logger.warning(
            "[notify-init] CoCreateInstance(ShellLink) failed: HR=0x%08X", hr & 0xFFFFFFFF
        )
        return False

    vtable = ctypes.cast(p_shell_link, POINTER(POINTER(c_void_p)))[0]

    # IShellLinkW::SetPath (vtable index 20)
    set_path = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR)(vtable[20])
    set_path(p_shell_link, target_path)

    # IShellLinkW::SetWorkingDirectory (vtable index 10)
    set_working_dir = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR)(vtable[10])
    set_working_dir(p_shell_link, str(Path(target_path).parent))

    # IShellLinkW::SetDescription (vtable index 8)
    set_description = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR)(vtable[8])
    set_description(p_shell_link, display_name)

    # IShellLinkW::SetIconLocation (vtable index 18)
    set_icon = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR, c_int)(vtable[18])
    set_icon(p_shell_link, target_path, 0)

    # QueryInterface for IPersistFile
    p_persist_file = c_void_p()
    query_interface = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p))(
        vtable[0]
    )
    hr = query_interface(p_shell_link, byref(IID_IPersistFile), byref(p_persist_file))
    if hr != 0:
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
        release(p_shell_link)
        return False

    # IPersistFile::Save (vtable index 6)
    pf_vtable = ctypes.cast(p_persist_file, POINTER(POINTER(c_void_p)))[0]
    pf_save = ctypes.CFUNCTYPE(HRESULT, c_void_p, LPCWSTR, ctypes.c_bool)(pf_vtable[6])
    hr = pf_save(p_persist_file, str(shortcut_path), True)

    # Release both
    pf_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(pf_vtable[2])
    pf_release(p_persist_file)
    sl_release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(vtable[2])
    sl_release(p_shell_link)

    if hr != 0:
        logger.warning("[notify-init] IPersistFile::Save failed: HR=0x%08X", hr & 0xFFFFFFFF)
        return False
    return True


def _read_shortcut_string_property(  # pragma: no cover
    shortcut_path: Path, property_key: PROPERTYKEY
) -> str | None:
    """Read a string-valued property from a shortcut via IPropertyStore."""
    if sys.platform != "win32" or not shortcut_path.exists() or _shell32 is None:
        return None

    try:
        p_store = c_void_p()
        hr = _shell32.SHGetPropertyStoreFromParsingName(
            str(shortcut_path),
            None,
            0,  # GPS_DEFAULT (read-only)
            byref(_IID_IPropertyStore),
            byref(p_store),
        )
        if hr != 0:
            return None

        store_vtable = ctypes.cast(p_store, POINTER(POINTER(c_void_p)))[0]

        # IPropertyStore::GetValue (vtable index 5)
        pv = PROPVARIANT()
        get_value = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(
            store_vtable[5]
        )
        hr = get_value(p_store, byref(property_key), byref(pv))

        result = None
        if hr == 0 and pv.vt == _VT_LPWSTR and pv.pointer_value:
            result = ctypes.cast(pv.pointer_value, ctypes.c_wchar_p).value

        # Release
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
        release(p_store)
        return result
    except Exception as exc:
        logger.debug("[notify-init] Failed to read shortcut string property: %s", exc)
        return None


def _set_shortcut_string_property(  # pragma: no cover
    shortcut_path: Path, property_key: PROPERTYKEY, value: str
) -> bool:
    """Set a string-valued property on a shortcut via IPropertyStore."""
    if sys.platform != "win32" or _shell32 is None:
        return False

    try:
        p_store = c_void_p()
        hr = _shell32.SHGetPropertyStoreFromParsingName(
            str(shortcut_path),
            None,
            _GPS_READWRITE,
            byref(_IID_IPropertyStore),
            byref(p_store),
        )
        if hr != 0:
            logger.warning(
                "[notify-init] SHGetPropertyStoreFromParsingName(READWRITE) failed: HR=0x%08X",
                hr & 0xFFFFFFFF,
            )
            return False

        store_vtable = ctypes.cast(p_store, POINTER(POINTER(c_void_p)))[0]

        # IPropertyStore::SetValue (vtable index 6)
        pv = PROPVARIANT()
        pv.vt = _VT_LPWSTR
        wchar_value = ctypes.c_wchar_p(value)
        pv.pointer_value = ctypes.cast(wchar_value, c_void_p).value
        set_value = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(
            store_vtable[6]
        )
        hr = set_value(p_store, byref(property_key), byref(pv))
        if hr != 0:
            logger.warning(
                "[notify-init] IPropertyStore::SetValue failed: HR=0x%08X", hr & 0xFFFFFFFF
            )
            release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
            release(p_store)
            return False

        # IPropertyStore::Commit (vtable index 7)
        commit = ctypes.CFUNCTYPE(HRESULT, c_void_p)(store_vtable[7])
        hr = commit(p_store)

        # Release
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
        release(p_store)

        if hr != 0:
            logger.warning(
                "[notify-init] IPropertyStore::Commit failed: HR=0x%08X", hr & 0xFFFFFFFF
            )
            return False
        return True
    except Exception as exc:
        logger.warning("[notify-init] Failed to set shortcut string property: %s", exc)
        return False


def _read_shortcut_guid_property(  # pragma: no cover
    shortcut_path: Path, property_key: PROPERTYKEY
) -> str | None:
    """Read a GUID-valued property from a shortcut via IPropertyStore."""
    if sys.platform != "win32" or not shortcut_path.exists() or _shell32 is None:
        return None

    try:
        p_store = c_void_p()
        hr = _shell32.SHGetPropertyStoreFromParsingName(
            str(shortcut_path),
            None,
            0,
            byref(_IID_IPropertyStore),
            byref(p_store),
        )
        if hr != 0:
            return None

        store_vtable = ctypes.cast(p_store, POINTER(POINTER(c_void_p)))[0]
        pv = PROPVARIANT()
        get_value = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(
            store_vtable[5]
        )
        hr = get_value(p_store, byref(property_key), byref(pv))

        result = None
        if hr == 0 and pv.vt == _VT_CLSID and pv.pointer_value:
            guid_pointer = ctypes.cast(pv.pointer_value, POINTER(GUID))
            result = _guid_to_string(guid_pointer.contents)

        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
        release(p_store)
        return result
    except Exception as exc:
        logger.debug("[notify-init] Failed to read shortcut GUID property: %s", exc)
        return None


def _set_shortcut_guid_property(  # pragma: no cover
    shortcut_path: Path, property_key: PROPERTYKEY, value: str
) -> bool:
    """Set a GUID-valued property on a shortcut via IPropertyStore."""
    if sys.platform != "win32" or _shell32 is None:
        return False

    try:
        p_store = c_void_p()
        hr = _shell32.SHGetPropertyStoreFromParsingName(
            str(shortcut_path),
            None,
            _GPS_READWRITE,
            byref(_IID_IPropertyStore),
            byref(p_store),
        )
        if hr != 0:
            logger.warning(
                "[notify-init] SHGetPropertyStoreFromParsingName(READWRITE) failed: HR=0x%08X",
                hr & 0xFFFFFFFF,
            )
            return False

        store_vtable = ctypes.cast(p_store, POINTER(POINTER(c_void_p)))[0]
        pv = PROPVARIANT()
        pv.vt = _VT_CLSID
        guid_value = _guid_from_string(value)
        pv.pointer_value = ctypes.addressof(guid_value)
        set_value = ctypes.CFUNCTYPE(HRESULT, c_void_p, POINTER(PROPERTYKEY), POINTER(PROPVARIANT))(
            store_vtable[6]
        )
        hr = set_value(p_store, byref(property_key), byref(pv))
        if hr != 0:
            logger.warning(
                "[notify-init] IPropertyStore::SetValue(GUID) failed: HR=0x%08X",
                hr & 0xFFFFFFFF,
            )
            release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
            release(p_store)
            return False

        commit = ctypes.CFUNCTYPE(HRESULT, c_void_p)(store_vtable[7])
        hr = commit(p_store)
        release = ctypes.CFUNCTYPE(ctypes.c_ulong, c_void_p)(store_vtable[2])
        release(p_store)

        if hr != 0:
            logger.warning(
                "[notify-init] IPropertyStore::Commit(GUID) failed: HR=0x%08X",
                hr & 0xFFFFFFFF,
            )
            return False
        return True
    except Exception as exc:
        logger.warning("[notify-init] Failed to set shortcut GUID property: %s", exc)
        return False


def _read_shortcut_app_id(shortcut_path: Path) -> str | None:
    """Read the AppUserModelID property from a shortcut via IPropertyStore."""
    return _read_shortcut_string_property(shortcut_path, _PKEY_AppUserModel_ID)


def _set_shortcut_app_id(shortcut_path: Path, app_id: str) -> bool:
    """Set the AppUserModelID property on a shortcut via IPropertyStore."""
    return _set_shortcut_string_property(shortcut_path, _PKEY_AppUserModel_ID, app_id)


def _read_shortcut_toast_activator_clsid(shortcut_path: Path) -> str | None:
    """Read the ToastActivatorCLSID property from a shortcut."""
    return _read_shortcut_guid_property(shortcut_path, _PKEY_AppUserModel_ToastActivatorCLSID)


def _set_shortcut_toast_activator_clsid(shortcut_path: Path, clsid: str) -> bool:
    """Set the ToastActivatorCLSID property on a shortcut."""
    return _set_shortcut_guid_property(shortcut_path, _PKEY_AppUserModel_ToastActivatorCLSID, clsid)
