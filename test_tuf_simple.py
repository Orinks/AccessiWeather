"""Simple test for the new TUF update service."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accessiweather.services import TUFUpdateService

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def test_update_service():
    """Test the TUF update service."""
    print("🚀 Testing TUF Update Service")
    print("=" * 50)

    try:
        # Create update service
        update_service = TUFUpdateService(
            app_name="AccessiWeather", config_dir=Path.home() / ".accessiweather_test"
        )

        # Get settings
        settings = update_service.get_settings_dict()
        print("📊 Current Settings:")
        for key, value in settings.items():
            if key != "platform":
                print(f"   {key}: {value}")

        print(f"\n🖥️  Platform: {settings['platform']['system']} {settings['platform']['machine']}")
        print(f"🐍 Python: {settings['platform']['python_version']}")

        # Test TUF method if available
        if settings.get("tuf_available"):
            print("\n🔧 Testing TUF update check...")
            update_info = await update_service.check_for_updates(method="tuf")
            if update_info:
                print(f"✅ TUF update found: {update_info.version}")
            else:
                print("ℹ️  No TUF updates available")
        else:
            print("\n⚠️  TUF not available - tufup package not installed")

        # Test GitHub method
        print("\n🔧 Testing GitHub update check...")
        update_info = await update_service.check_for_updates(method="github")
        if update_info:
            print(f"✅ GitHub update found:")
            print(f"   Version: {update_info.version}")
            print(f"   Artifact: {update_info.artifact_name}")
            print(
                f"   Size: {update_info.file_size} bytes"
                if update_info.file_size
                else "   Size: Unknown"
            )
            print(f"   Prerelease: {update_info.is_prerelease}")
            print(
                f"   Notes: {update_info.release_notes[:100]}..."
                if len(update_info.release_notes) > 100
                else f"   Notes: {update_info.release_notes}"
            )
        else:
            print("ℹ️  No GitHub updates available")

        # Test settings update
        print("\n🔧 Testing settings update...")
        update_service.update_settings(method="github", channel="dev", auto_check=False)

        new_settings = update_service.get_settings_dict()
        print("📊 Updated Settings:")
        print(f"   method: {new_settings['method']}")
        print(f"   channel: {new_settings['channel']}")
        print(f"   auto_check: {new_settings['auto_check']}")

        # Cleanup
        await update_service.cleanup()

        print("\n✅ All tests completed successfully!")
        return 0

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


async def test_download():
    """Test downloading an update."""
    print("\n🧪 Testing Update Download")
    print("=" * 30)

    try:
        update_service = TUFUpdateService()

        # Check for updates first
        update_info = await update_service.check_for_updates(method="github")

        if update_info:
            print(f"📦 Found update: {update_info.version}")
            print("🔽 Starting download test...")

            # Download to temp directory
            downloaded_file = await update_service.download_update(update_info)

            if downloaded_file and downloaded_file.exists():
                print(f"✅ Download successful: {downloaded_file}")
                print(f"📊 File size: {downloaded_file.stat().st_size} bytes")

                # Clean up test download
                downloaded_file.unlink()
                print("🧹 Test file cleaned up")
            else:
                print("❌ Download failed")
                return 1
        else:
            print("ℹ️  No updates available to test download")

        await update_service.cleanup()
        return 0

    except Exception as e:
        print(f"❌ Download test failed: {e}")
        return 1


async def main():
    """Run all tests."""
    print("🎯 AccessiWeather TUF Update Service Tests")
    print("=" * 60)

    result1 = await test_update_service()
    result2 = await test_download()

    if result1 == 0 and result2 == 0:
        print("\n🎉 All tests passed!")
        return 0
    print("\n💥 Some tests failed!")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
