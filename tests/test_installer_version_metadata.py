from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_has_no_stale_version_fallback():
    script = (ROOT / "installer" / "accessiweather.iss").read_text()

    assert "0.4.4" not in script
    assert "Missing dist/version.txt" in script
    assert 'ReadIni("..\\dist\\version.txt"' in script


def test_inno_installer_avoids_ultra_compression_for_ci_runtime():
    script = (ROOT / "installer" / "accessiweather.iss").read_text()

    assert "Compression=lzma2/normal" in script
    assert "Compression=lzma2/ultra" not in script


def test_inno_installer_closes_running_accessiweather_instead_of_prompting():
    script = (ROOT / "installer" / "accessiweather.iss").read_text()

    assert "AppMutex=" not in script
    assert "CloseRunningAccessiWeather" in script
    assert "WaitForAccessiWeatherToExit" in script
    assert "taskkill.exe" in script
    assert "Parameters := '/IM ' + RunningAppImageName + ' /T';" in script
    assert "Parameters := '/F ' + Parameters;" in script
