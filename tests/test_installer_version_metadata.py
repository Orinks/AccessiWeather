from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_has_no_stale_version_fallback():
    script = (ROOT / "installer" / "accessiweather.iss").read_text()

    assert "0.4.4" not in script
    assert "Missing dist/version.txt" in script
    assert 'ReadIni("..\\dist\\version.txt"' in script


def test_build_workflow_writes_installer_version_file_before_compiling():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text()
    create_installer_step = workflow.index("- name: Create installer")
    write_version = workflow.index(
        "echo value=${{ needs.prepare.outputs.version }}", create_installer_step
    )
    compile_installer = workflow.index("ISCC.exe", create_installer_step)

    assert write_version < compile_installer
