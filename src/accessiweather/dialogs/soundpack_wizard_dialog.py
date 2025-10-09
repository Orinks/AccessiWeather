"""Wizard dialog for creating a new sound pack.

Extracted from SoundPackManagerDialog to a dedicated module.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

logger = logging.getLogger(__name__)


@dataclass
class WizardState:
    """State container for the wizard UI flow."""

    pack_name: str = ""
    author: str = ""
    description: str = ""
    selected_alert_keys: list[str] | None = None
    # Mapping from alert key -> staged file path
    sound_mappings: dict[str, str] | None = None


class SoundPackWizardDialog:
    """Guided wizard for creating a new sound pack.

    Parameters
    ----------
    - app: Toga app instance
    - soundpacks_dir: directory where packs will be created
    - friendly_categories: list[(display_name, technical_key)] to show in steps
    - create_pack_callback: callable(state: WizardState) -> pack_id
    - on_complete: callback invoked with new_pack_id or None

    """

    def __init__(
        self,
        app: toga.App,
        soundpacks_dir: Path,
        friendly_categories: list[tuple[str, str]],
        create_pack_callback,
        on_complete,
    ) -> None:
        """Initialize the wizard dialog with app, directories, data and callbacks."""
        self.app = app
        self.soundpacks_dir = soundpacks_dir
        self.friendly_categories = friendly_categories
        self.create_pack_callback = create_pack_callback
        self.on_complete = on_complete

        self.current_step = 1
        self.total_steps = 4
        self.state = WizardState(selected_alert_keys=[], sound_mappings={})

        import tempfile as _tempfile

        self._tempfile = _tempfile
        self.staging_dir = Path(self._tempfile.mkdtemp(prefix="aw_soundpack_wizard_"))

        # Build window
        self.window = toga.Window(
            title="Create Sound Pack (Wizard)", size=(600, 500), resizable=False
        )

        self.root_box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        self.header_label = toga.Label(
            "Step 1 of 4: Pack Details", style=Pack(margin_bottom=10, font_weight="bold")
        )
        self.content_box = toga.Box(style=Pack(direction=COLUMN, flex=1))
        self.nav_row = toga.Box(style=Pack(direction=ROW, margin_top=10))
        self._focus_target = None

        self.prev_btn = toga.Button(
            "Previous", on_press=self._go_previous, enabled=False, style=Pack(margin_right=10)
        )
        self.next_btn = toga.Button("Next", on_press=self._go_next, style=Pack(margin_right=10))
        self.cancel_btn = toga.Button("Cancel", on_press=self._cancel)

        self.root_box.add(self.header_label)
        self.root_box.add(self.content_box)
        nav_spacer = toga.Box(style=Pack(flex=1))
        self.nav_row.add(nav_spacer)
        self.nav_row.add(self.prev_btn)
        self.nav_row.add(self.next_btn)
        self.nav_row.add(self.cancel_btn)
        self.root_box.add(self.nav_row)

        self.window.content = self.root_box
        self._render_step()

    def show(self) -> None:
        self.app.windows.add(self.window)
        self.window.show()

    # Navigation helpers
    def _go_previous(self, _):
        if self.current_step > 1:
            self.current_step -= 1
            self._render_step()

    def _go_next(self, _):
        if not self._validate_current_step():
            return
        if self.current_step < self.total_steps:
            self.current_step += 1
            self._render_step()
        else:
            # Finalize
            try:
                new_pack_id = self.create_pack_callback(self.state)
                self.window.close()
                if self.on_complete:
                    self.on_complete(new_pack_id)
                # Cleanup staging directory on success
                with contextlib.suppress(Exception):
                    import shutil as _shutil

                    _shutil.rmtree(self.staging_dir)
            except Exception as e:
                logger.error(f"Failed to create pack from wizard: {e}")
                self.app.main_window.error_dialog("Create Error", f"Failed to create pack: {e}")

    def _cancel(self, _):
        try:
            any_changes = bool(
                self.state.pack_name
                or self.state.author
                or self.state.description
                or self.state.selected_alert_keys
                or self.state.sound_mappings
            )
            if any_changes and not self.app.main_window.question_dialog(
                "Cancel Wizard", "Discard changes and close the wizard?"
            ):
                return
            self.window.close()
            if self.on_complete:
                self.on_complete(None)
        finally:
            with contextlib.suppress(Exception):
                import shutil

                shutil.rmtree(self.staging_dir)

    def _render_step(self) -> None:
        titles = {
            1: "Pack Details",
            2: "Select Alert Types",
            3: "Assign Sounds",
            4: "Preview & Finalize",
        }
        self.header_label.text = (
            f"Step {self.current_step} of {self.total_steps}: {titles.get(self.current_step, '')}"
        )
        self.prev_btn.enabled = self.current_step > 1
        self.next_btn.text = "Next" if self.current_step < self.total_steps else "Create Pack"

        # Replace the entire content container to ensure old controls are removed
        with contextlib.suppress(Exception):
            self.root_box.remove(self.content_box)
        self.content_box = toga.Box(style=Pack(direction=COLUMN, flex=1))
        # Insert after header_label
        try:
            self.root_box.insert(1, self.content_box)
        except Exception:
            # Fallback: add then reorder not strictly necessary
            self.root_box.add(self.content_box)
        # Reset focus target
        self._focus_target = None

        if self.current_step == 1:
            self._build_step1()
        elif self.current_step == 2:
            self._build_step2()
        elif self.current_step == 3:
            self._build_step3()
        else:
            self._build_step4()

        # Defer focus to first control of the step for screen readers
        async def _defer_focus(widget):
            await asyncio.sleep(0.1)
            with contextlib.suppress(Exception):
                if widget is not None:
                    widget.focus()

        try:
            asyncio.create_task(_defer_focus(self._focus_target))
        except Exception:
            with contextlib.suppress(Exception):
                if self._focus_target is not None:
                    self._focus_target.focus()

    # Step 1: Pack details
    def _build_step1(self) -> None:
        form = toga.Box(style=Pack(direction=COLUMN))
        form.add(toga.Label("Pack name (required):"))
        self.name_input = toga.TextInput(
            value=self.state.pack_name or "",
            placeholder="e.g., My Weather Sounds",
            style=Pack(margin_bottom=8),
        )
        form.add(self.name_input)
        # Set focus to the first input for step 1
        self._focus_target = self.name_input
        form.add(toga.Label("Author (optional):"))
        self.author_input = toga.TextInput(
            value=self.state.author or "", style=Pack(margin_bottom=8)
        )
        form.add(self.author_input)
        form.add(toga.Label("Description (optional):"))
        self.desc_input = toga.MultilineTextInput(
            value=self.state.description or "", style=Pack(flex=1, height=120)
        )
        form.add(self.desc_input)

        hint = toga.Label(
            "We'll generate a folder name from your pack name and ensure it's unique.",
            style=Pack(margin_top=8, font_style="italic"),
        )
        form.add(hint)

        self.content_box.add(form)

    def _validate_current_step(self) -> bool:
        if self.current_step == 1:
            self.state.pack_name = (self.name_input.value or "").strip()
            self.state.author = (self.author_input.value or "").strip()
            self.state.description = (self.desc_input.value or "").strip()
            if not self.state.pack_name:
                self.app.main_window.info_dialog(
                    "Missing Name", "Please enter a pack name to continue."
                )
                return False
            slug = self.state.pack_name.strip().lower().replace(" ", "_").replace("-", "_")
            conflict = (self.soundpacks_dir / slug).exists()
            if conflict:
                self.app.main_window.info_dialog(
                    "Name In Use",
                    "A pack with a similar folder name already exists. You can still continue; we'll make it unique.",
                )
            return True
        if self.current_step == 2:
            if not getattr(self, "category_checks", None):
                self.state.selected_alert_keys = []
            else:
                self.state.selected_alert_keys = [
                    key for key, chk in self.category_checks if chk.value
                ]
            if not self.state.selected_alert_keys:
                self.app.main_window.info_dialog(
                    "Choose Alerts", "Select at least one alert type to continue."
                )
                return False
            return True
        if self.current_step == 3:
            return True
        if self.current_step == 4:
            return True
        return True

    # Step 2: Alert selection
    def _build_step2(self) -> None:
        outer = toga.Box(style=Pack(direction=COLUMN, flex=1))
        help_lbl = toga.Label("Choose the alert categories you want sounds for.")
        outer.add(help_lbl)
        scroll = toga.ScrollContainer(style=Pack(flex=1, margin_top=8))
        inner = toga.Box(style=Pack(direction=COLUMN, padding=(4, 8)))

        self.category_checks: list[tuple[str, toga.Switch]] = []
        first_switch = None
        for display, key in self.friendly_categories:
            row = toga.Box(style=Pack(direction=ROW, margin_bottom=4))
            chk = toga.Switch(display)
            if first_switch is None:
                first_switch = chk
            chk.value = key in (self.state.selected_alert_keys or [])
            row.add(chk)
            inner.add(row)
            self.category_checks.append((key, chk))
        # Focus the first switch if available
        if first_switch is not None:
            self._focus_target = first_switch

        scroll.content = inner
        outer.add(scroll)

        actions = toga.Box(style=Pack(direction=ROW, margin_top=8))

        def _select_common(_):
            common = {
                "tornado_warning",
                "thunderstorm_warning",
                "flood_warning",
                "heat_advisory",
                "alert",
                "notify",
            }
            for key, chk in self.category_checks:
                chk.value = key in common

        def _clear_all(_):
            for _, chk in self.category_checks:
                chk.value = False

        actions.add(
            toga.Button("Select Common", on_press=_select_common, style=Pack(margin_right=8))
        )
        actions.add(toga.Button("Clear All", on_press=_clear_all))
        outer.add(actions)

        self.content_box.add(outer)

    # Step 3: Sound assignment
    def _build_step3(self) -> None:
        outer = toga.Box(style=Pack(direction=COLUMN, flex=1))
        help_lbl = toga.Label(
            "Assign a sound file to each selected alert. You can leave some blank; defaults will be used."
        )
        outer.add(help_lbl)
        scroll = toga.ScrollContainer(style=Pack(flex=1, margin_top=8))
        inner = toga.Box(style=Pack(direction=COLUMN, padding=(4, 8)))

        self.mapping_rows = []
        selected = self.state.selected_alert_keys or []
        first_focus_set = False
        for key in selected:
            friendly = next(
                (d for d, k in self.friendly_categories if k == key),
                key.replace("_", " ").title(),
            )
            row = toga.Box(style=Pack(direction=ROW, margin_bottom=6))
            label = toga.Label(friendly + ":", style=Pack(width=220, margin_top=6))
            file_display = toga.TextInput(readonly=True, style=Pack(flex=1, margin_right=8))
            existing = (self.state.sound_mappings or {}).get(key)
            if existing:
                from pathlib import Path as _Path

                file_display.value = _Path(existing).name

            def _choose_file_factory(alert_key: str, display: toga.TextInput, friendly_name: str):
                def _handler(_):
                    def _apply(__, path=None):
                        if not path:
                            return
                        try:
                            import shutil as _shutil
                            from pathlib import Path as _Path

                            src = _Path(path)
                            if not src.exists():
                                return
                            dest = self.staging_dir / src.name
                            if src.resolve() != dest.resolve():
                                with contextlib.suppress(Exception):
                                    _shutil.copy2(src, dest)
                            self.state.sound_mappings[alert_key] = str(dest)
                            display.value = dest.name
                        except Exception as e:
                            logger.error(f"Failed to stage file: {e}")
                            self.app.main_window.error_dialog(
                                "File Error", f"Failed to add file: {e}"
                            )

                    self.app.main_window.open_file_dialog(
                        title=f"Choose sound for {friendly_name}",
                        file_types=["wav", "mp3", "ogg", "flac"],
                        on_result=_apply,
                    )

                return _handler

            def _preview_factory(alert_key: str, display_name: str):
                def _handler(_):
                    try:
                        from pathlib import Path as _Path

                        from ..notifications.sound_player import play_sound_file

                        src = self.state.sound_mappings.get(alert_key)
                        if not src:
                            self.app.main_window.info_dialog(
                                "No Sound", f"No sound chosen for {display_name}."
                            )
                            return
                        play_sound_file(_Path(src))
                    except Exception as e:
                        logger.error(f"Failed to preview: {e}")
                        self.app.main_window.error_dialog(
                            "Preview Error", f"Failed to preview: {e}"
                        )

                return _handler

            choose_btn = toga.Button(
                "Choose File",
                on_press=_choose_file_factory(key, file_display, friendly),
                style=Pack(margin_right=8),
            )
            # Placeholder Record control (disabled) with hint label
            record_btn = toga.Button("Record", enabled=False, style=Pack(margin_right=8))
            record_hint = toga.Label(
                "Recording coming soon",
                style=Pack(margin_top=6, margin_left=4, font_style="italic"),
            )
            preview_btn = toga.Button("Preview", on_press=_preview_factory(key, friendly))

            row.add(label)
            row.add(file_display)
            row.add(choose_btn)
            row.add(record_btn)
            row.add(preview_btn)
            row.add(record_hint)
            inner.add(row)
            self.mapping_rows.append((key, file_display))
            if not first_focus_set:
                self._focus_target = choose_btn
                first_focus_set = True

        scroll.content = inner
        outer.add(scroll)
        self.content_box.add(outer)

    # Step 4: Preview & finalize
    def _build_step4(self) -> None:
        outer = toga.Box(style=Pack(direction=COLUMN, flex=1))
        meta = toga.Label(f"Pack: {self.state.pack_name}  |  Author: {self.state.author}")
        outer.add(meta)
        desc = toga.Label(self.state.description or "")
        outer.add(desc)
        outer.add(toga.Label(f"Sounds selected: {len(self.state.sound_mappings or {})}"))

        table_scroll = toga.ScrollContainer(style=Pack(flex=1, margin_top=8))
        inner = toga.Box(style=Pack(direction=COLUMN, padding=(4, 8)))
        for key in self.state.selected_alert_keys or []:
            from pathlib import Path as _Path

            friendly = next((d for d, k in self.friendly_categories if k == key), key)
            file_name = (
                _Path(self.state.sound_mappings.get(key, "")).name
                if self.state.sound_mappings and key in self.state.sound_mappings
                else "(default)"
            )
            row = toga.Box(style=Pack(direction=ROW, margin_bottom=4))
            row.add(toga.Label(f"{friendly}:", style=Pack(width=240)))
            row.add(toga.Label(file_name, style=Pack(flex=1)))

            def _preview_factory2(alert_key: str, display_name: str):
                def _handler(_):
                    try:
                        from pathlib import Path as _Path

                        from ..notifications.sound_player import _play_sound_file

                        src = self.state.sound_mappings.get(alert_key)
                        if src:
                            _play_sound_file(_Path(src))
                        else:
                            self.app.main_window.info_dialog(
                                "No Sound", f"No custom sound chosen for {display_name}."
                            )
                    except Exception as e:
                        logger.error(f"Failed to preview: {e}")
                        self.app.main_window.error_dialog(
                            "Preview Error", f"Failed to preview: {e}"
                        )

                return _handler

            row.add(toga.Button("Preview", on_press=_preview_factory2(key, friendly)))
            inner.add(row)
        table_scroll.content = inner
        outer.add(table_scroll)

        def _test_pack(_):
            try:
                from pathlib import Path as _Path

                from ..notifications.sound_player import play_sound_file

                async def _runner():
                    for key in (self.state.selected_alert_keys or [])[:5]:
                        src = self.state.sound_mappings.get(key)
                        if src:
                            play_sound_file(_Path(src))
                            # Small delay to avoid overlap with async playback backends
                            await asyncio.sleep(0.4)

                # Run playback sequence without blocking UI
                asyncio.create_task(_runner())
            except Exception as e:
                logger.error(f"Failed to test pack: {e}")
                self.app.main_window.error_dialog("Test Error", f"Failed to test pack: {e}")

        test_button = toga.Button(
            "Test Pack", on_press=_test_pack, style=Pack(margin_top=8, width=120)
        )
        outer.add(test_button)

        # Focus Test Pack button on step 4 start
        self._focus_target = test_button

        self.content_box.add(outer)
