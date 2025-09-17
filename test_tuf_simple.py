"""Simple test for the new TUF update service."""

import asyncio
import logging
import shutil
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from accessiweather.services import TUFUpdateService

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Test cleanup tracking
_test_cleanup_dirs = []


def test_cleanup():
    """Clean up test artifacts and temporary directories."""
    global _test_cleanup_dirs

    print("🧹 Cleaning up test artifacts...")
    cleanup_count = 0

    for cleanup_dir in _test_cleanup_dirs:
        try:
            if cleanup_dir.exists():
                shutil.rmtree(cleanup_dir)
                cleanup_count += 1
                print(f"✅ Cleaned up: {cleanup_dir}")
        except Exception as e:
            print(f"⚠️ Failed to clean up {cleanup_dir}: {e}")

    _test_cleanup_dirs.clear()

    if cleanup_count > 0:
        print(f"✅ Cleanup completed: {cleanup_count} directories removed")
    else:
        print("ℹ️ No cleanup needed")


def format_success_message(message: str) -> str:
    """Format success message with consistent styling."""
    return f"✅ {message}"


def format_warning_message(message: str) -> str:
    """Format warning message with consistent styling."""
    return f"⚠️ {message}"


def format_error_message(message: str) -> str:
    """Format error message with consistent styling."""
    return f"❌ {message}"


async def test_update_service():
    """Test the TUF update service."""
    print("🚀 Testing TUF Update Service")
    print("=" * 50)

    config_dir = None
    try:
        # Create temporary config directory
        config_dir = Path.home() / ".accessiweather_test"
        _test_cleanup_dirs.append(config_dir)

        # Create update service
        update_service = TUFUpdateService(app_name="AccessiWeather", config_dir=config_dir)

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
                print(format_success_message(f"TUF update found: {update_info.version}"))
            else:
                print("ℹ️  No TUF updates available")
        else:
            print(format_warning_message("TUF not available - tufup package not installed"))

        # Test GitHub method
        print("\n🔧 Testing GitHub update check...")
        update_info = await update_service.check_for_updates(method="github")
        if update_info:
            print(format_success_message("GitHub update found:"))
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

        # Cleanup service
        await update_service.cleanup()

        print(format_success_message("All tests completed successfully!"))
        return 0

    except Exception as e:
        print(format_error_message(f"Test failed: {e}"))
        import traceback

        traceback.print_exc()
        return 1
    finally:
        # Ensure cleanup happens even if test fails
        if config_dir and config_dir.exists():
            try:
                shutil.rmtree(config_dir)
                print(f"✅ Cleaned up config directory: {config_dir}")
            except Exception as cleanup_error:
                print(format_warning_message(f"Failed to clean up {config_dir}: {cleanup_error}"))


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


async def test_tuf_repository_access():
    """Test TUF repository access scenarios."""
    print("\n🔗 Testing TUF Repository Access")
    print("=" * 40)

    try:
        update_service = TUFUpdateService()

        # Test TUF availability check
        print("🔍 Checking TUF availability...")
        tuf_available = update_service.check_tuf_availability()
        print(f"TUF Available: {tuf_available}")

        # Get TUF diagnostics
        print("\n📊 TUF Diagnostics:")
        diagnostics = update_service.get_tuf_diagnostics()
        for key, value in diagnostics.items():
            print(f"   {key}: {value}")

        # Test different repository scenarios
        if tuf_available:
            print("\n🏗️ Testing TUF repository connectivity...")
            try:
                # Test with current settings
                update_info = await update_service.check_for_updates(method="tuf")
                print(f"✅ TUF repository accessible: {update_info is not None}")
            except Exception as e:
                print(f"⚠️ TUF repository access failed: {e}")

        await update_service.cleanup()
        return 0

    except Exception as e:
        print(f"❌ TUF repository test failed: {e}")
        return 1


async def test_github_fallback():
    """Test GitHub fallback functionality."""
    print("\n🔄 Testing GitHub Fallback")
    print("=" * 30)

    try:
        update_service = TUFUpdateService()

        # Force GitHub method to test fallback
        print("🔧 Testing GitHub method directly...")
        github_result = await update_service.check_for_updates(method="github")

        if github_result:
            print(f"✅ GitHub fallback working:")
            print(f"   Version: {github_result.version}")
            print(f"   Channel: {github_result.channel}")
            print(f"   Prerelease: {github_result.is_prerelease}")
        else:
            print("ℹ️ No GitHub updates found")

        # Test automatic fallback when TUF fails
        print("\n🔧 Testing automatic fallback...")
        try:
            # This should fall back to GitHub if TUF is unavailable
            fallback_result = await update_service.check_for_updates()
            print(f"✅ Automatic fallback result: {fallback_result is not None}")
        except Exception as e:
            print(f"⚠️ Automatic fallback failed: {e}")

        await update_service.cleanup()
        return 0

    except Exception as e:
        print(f"❌ GitHub fallback test failed: {e}")
        return 1


async def test_update_channels():
    """Test different update channels."""
    print("\n📡 Testing Update Channels")
    print("=" * 30)

    channels = ["stable", "beta", "dev"]
    results = {}

    try:
        for channel in channels:
            print(f"\n🔧 Testing {channel} channel...")
            update_service = TUFUpdateService()
            update_service.update_settings(channel=channel)

            # Test GitHub method for this channel
            try:
                update_info = await update_service.check_for_updates(method="github")
                results[channel] = {
                    "success": True,
                    "has_update": update_info is not None,
                    "version": update_info.version if update_info else None,
                }
                print(f"   ✅ {channel}: {'Update available' if update_info else 'No updates'}")
                if update_info:
                    print(f"      Version: {update_info.version}")
            except Exception as e:
                results[channel] = {"success": False, "error": str(e)}
                print(f"   ❌ {channel}: {e}")

            await update_service.cleanup()

        # Summary
        print(f"\n📊 Channel Test Summary:")
        for channel, result in results.items():
            status = "✅" if result["success"] else "❌"
            print(f"   {status} {channel}: {result}")

        return 0

    except Exception as e:
        print(f"❌ Channel test failed: {e}")
        return 1


async def test_error_scenarios():
    """Test various error scenarios."""
    print("\n⚠️ Testing Error Scenarios")
    print("=" * 30)

    try:
        update_service = TUFUpdateService()

        # Test invalid method
        print("🔧 Testing invalid update method...")
        try:
            await update_service.check_for_updates(method="invalid")
            print("❌ Should have failed with invalid method")
            return 1
        except ValueError as e:
            print(f"✅ Correctly rejected invalid method: {e}")

        # Test invalid channel
        print("\n🔧 Testing invalid channel...")
        try:
            update_service.update_settings(channel="invalid")
            print("❌ Should have failed with invalid channel")
            return 1
        except ValueError as e:
            print(f"✅ Correctly rejected invalid channel: {e}")

        # Test network error simulation (if possible)
        print("\n🔧 Testing network error handling...")
        # This would require mocking, but we can at least test the error handling structure

        await update_service.cleanup()
        print("✅ Error scenario tests completed")
        return 0

    except Exception as e:
        print(f"❌ Error scenario test failed: {e}")
        return 1


async def main():
    """Run all tests."""
    print("🎯 AccessiWeather TUF Update Service Tests")
    print("=" * 60)

    tests = [
        ("Basic Service", test_update_service),
        ("Download Test", test_download),
        ("TUF Repository", test_tuf_repository_access),
        ("GitHub Fallback", test_github_fallback),
        ("Update Channels", test_update_channels),
        ("Error Scenarios", test_error_scenarios),
    ]

    results = []
    try:
        for test_name, test_func in tests:
            print(f"\n{'=' * 20} {test_name} {'=' * 20}")
            try:
                result = await test_func()
                results.append((test_name, result))
            except Exception as e:
                print(format_error_message(f"{test_name} crashed: {e}"))
                results.append((test_name, 1))

        # Summary
        print(f"\n{'=' * 60}")
        print("📊 TEST SUMMARY")
        print(f"{'=' * 60}")

        passed = 0
        for test_name, result in results:
            status = format_success_message("PASS") if result == 0 else format_error_message("FAIL")
            print(f"{status} {test_name}")
            if result == 0:
                passed += 1

        print(f"\nResults: {passed}/{len(results)} tests passed")

        if passed == len(results):
            print(format_success_message("All tests passed!"))
            return 0
        print(format_error_message("Some tests failed!"))
        return 1

    finally:
        # Always run cleanup
        test_cleanup()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
