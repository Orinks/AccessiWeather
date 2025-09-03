import asyncio
import tempfile
from pathlib import Path

from accessiweather.services.github_update_service import GitHubUpdateService


async def main():
    tmpdir = tempfile.TemporaryDirectory()
    svc = GitHubUpdateService(app_name="AccessiWeatherTest", config_dir=tmpdir.name)
    info = await svc.check_for_updates(current_version="0.0.0")
    print("Check for updates returned:", info)
    if info:
        path = await svc.download_update(info)
        print("Download returned:", path)
        if path:
            print("Exists:", Path(path).exists())
        else:
            print("Download failed or returned False")
    else:
        print("No update found")
    await svc.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
