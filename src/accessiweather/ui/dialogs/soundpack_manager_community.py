"""Community browsing and sharing handlers for the sound pack manager dialog."""

from __future__ import annotations

import asyncio
import logging
import threading

import wx

logger = logging.getLogger(__name__)


class SoundPackManagerCommunityMixin:
    def _on_browse_community(self, event) -> None:
        """Open the community packs browser."""
        if not self.community_service:
            # Try to reinitialize
            self.community_service = self._create_community_service()
            if self.community_service:
                self.browse_community_btn.Enable(True)
            else:
                wx.MessageBox(
                    "Community packs are temporarily unavailable. Please try again later.",
                    "Community Sound Packs",
                    wx.OK | wx.ICON_WARNING,
                )
                return

        from .community_packs_dialog import CommunityPacksBrowserDialog

        def on_installed(pack_name: str) -> None:
            """Handle pack installed callback."""
            self._load_sound_packs()
            self._refresh_pack_list()

        dialog = CommunityPacksBrowserDialog(self, self.soundpacks_dir, on_installed)
        dialog.ShowModal()
        dialog.Destroy()

    def _on_share_pack(self, event) -> None:
        """Share the selected pack with the community."""
        if not self.selected_pack or self.selected_pack not in self.sound_packs:
            wx.MessageBox(
                "Please select a sound pack to share.",
                "Share Pack",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        pack_id = self.selected_pack
        pack_info = self.sound_packs[pack_id]

        if pack_id == "default":
            wx.MessageBox(
                "The default sound pack comes preinstalled and cannot be shared with the community.",
                "Share Pack",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Confirm sharing
        result = wx.MessageBox(
            f"Are you sure you want to share '{pack_info.name}' with the community?\n\n"
            "This will submit a pull request for review.",
            "Confirm Share",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            return

        # Validate pack
        from ...notifications.sound_player import validate_sound_pack

        ok, msg = validate_sound_pack(pack_info.path)
        if not ok:
            wx.MessageBox(
                f"Sound pack validation failed: {msg}",
                "Share Pack",
                wx.OK | wx.ICON_ERROR,
            )
            return

        # Show progress dialog
        from .progress_dialog import ProgressDialog

        progress = ProgressDialog(self, "Sharing Sound Pack", "Preparing submission...")
        progress.Show()

        def share_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Build pack metadata
                    pack_meta = {
                        "name": pack_info.name,
                        "author": pack_info.author,
                        "description": pack_info.description,
                        "sounds": pack_info.sounds,
                    }

                    def on_progress(pct: float, status: str) -> bool:
                        return progress.update_progress(pct, status)

                    cancel_event = asyncio.Event()

                    # Check for cancellation
                    def check_cancel():
                        if progress.is_cancelled:
                            cancel_event.set()
                            return True
                        return False

                    if check_cancel():
                        wx.CallAfter(progress.Destroy)
                        return

                    progress.update_progress(10, "Connecting to backend...")

                    from ...services.pack_submission_service import PackSubmissionService

                    # Get config_manager from app if available
                    config_manager = getattr(self.app, "config_manager", None)
                    service = PackSubmissionService(config_manager=config_manager)

                    if check_cancel():
                        wx.CallAfter(progress.Destroy)
                        return

                    pr_url = loop.run_until_complete(
                        service.submit_pack(
                            pack_info.path,
                            pack_meta,
                            on_progress,
                            cancel_event,
                        )
                    )

                    wx.CallAfter(self._on_share_success, progress, pr_url)

                finally:
                    loop.close()
            except asyncio.CancelledError:
                wx.CallAfter(progress.Destroy)
            except Exception as e:
                logger.error(f"Pack submission failed: {e}")
                wx.CallAfter(self._on_share_error, progress, str(e))

        thread = threading.Thread(target=share_thread, daemon=True)
        thread.start()

    def _on_share_success(self, progress, pr_url: str) -> None:
        """Handle share success."""
        progress.Destroy()
        result = wx.MessageBox(
            f"🎉 Your sound pack has been submitted for review!\n\n"
            f"Pull Request: {pr_url}\n\n"
            "Would you like to open the pull request in your browser?",
            "Sound Pack Shared Successfully",
            wx.YES_NO | wx.ICON_INFORMATION,
        )
        if result == wx.YES:
            import webbrowser

            webbrowser.open(pr_url)

    def _on_share_error(self, progress, error: str) -> None:
        """Handle share error."""
        progress.complete_error(error)
        wx.CallLater(3000, progress.Destroy)
