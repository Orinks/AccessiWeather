from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_has_no_stale_version_fallback():
    script = (ROOT / "installer" / "accessiweather.iss").read_text()

    assert "0.4.4" not in script
    assert "Missing dist/version.txt" in script
    assert 'ReadIni("..\\dist\\version.txt"' in script


def test_build_workflow_uses_nuitka_builder_for_windows_installer_metadata():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text()

    assert "choco install innosetup" in workflow
    assert "python installer/build_nuitka.py" in workflow
    assert "dist/AccessiWeather_Setup_*.exe" in workflow
    assert "echo value=${{ needs.prepare.outputs.version }}" not in workflow
