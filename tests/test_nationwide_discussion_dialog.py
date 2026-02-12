"""Tests for NationwideDiscussionDialog structure and exports."""

from __future__ import annotations

import ast

import pytest


class TestNationwideDiscussionDialogStructure:
    """Test the dialog module structure using AST parsing (no wx required)."""

    @pytest.fixture
    def module_ast(self):
        """Parse the module AST."""
        path = "src/accessiweather/ui/dialogs/nationwide_discussion_dialog.py"
        with open(path) as f:
            return ast.parse(f.read())

    def _get_class_node(self, tree: ast.Module, name: str) -> ast.ClassDef | None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == name:
                return node
        return None

    def _get_function_node(self, tree: ast.Module, name: str) -> ast.FunctionDef | None:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return node
        return None

    def test_class_exists(self, module_ast):
        """AC1: NationwideDiscussionDialog class exists."""
        cls = self._get_class_node(module_ast, "NationwideDiscussionDialog")
        assert cls is not None, "NationwideDiscussionDialog class not found"

    def test_class_inherits_wx_dialog(self, module_ast):
        """Dialog inherits from wx.Dialog."""
        cls = self._get_class_node(module_ast, "NationwideDiscussionDialog")
        assert cls is not None
        base_names = []
        for base in cls.bases:
            if isinstance(base, ast.Attribute):
                base_names.append(f"{base.value.id}.{base.attr}")  # type: ignore[union-attr]
            elif isinstance(base, ast.Name):
                base_names.append(base.id)
        assert any("Dialog" in b for b in base_names)

    def test_convenience_function_exists(self, module_ast):
        """AC9: show_nationwide_discussion_dialog function exists."""
        func = self._get_function_node(module_ast, "show_nationwide_discussion_dialog")
        assert func is not None

    def test_has_create_widgets_method(self, module_ast):
        """Dialog has _create_widgets method."""
        cls = self._get_class_node(module_ast, "NationwideDiscussionDialog")
        assert cls is not None
        methods = [n.name for n in ast.walk(cls) if isinstance(n, ast.FunctionDef)]
        assert "_create_widgets" in methods

    def test_has_close_handler(self, module_ast):
        """AC8: Dialog has close button handler."""
        cls = self._get_class_node(module_ast, "NationwideDiscussionDialog")
        assert cls is not None
        methods = [n.name for n in ast.walk(cls) if isinstance(n, ast.FunctionDef)]
        assert "_on_close" in methods

    def test_has_set_discussion_text_method(self, module_ast):
        """Dialog has set_discussion_text helper."""
        cls = self._get_class_node(module_ast, "NationwideDiscussionDialog")
        assert cls is not None
        methods = [n.name for n in ast.walk(cls) if isinstance(n, ast.FunctionDef)]
        assert "set_discussion_text" in methods


class TestDialogSourceContent:
    """Verify widget names and tab structure by inspecting source text."""

    @pytest.fixture
    def source(self):
        with open("src/accessiweather/ui/dialogs/nationwide_discussion_dialog.py") as f:
            return f.read()

    def test_notebook_created(self, source):
        """AC2: wx.Notebook is used for tabs."""
        assert "wx.Notebook" in source

    @pytest.mark.parametrize(
        "tab_name",
        ["WPC", "SPC", "NHC", "CPC"],
    )
    def test_tab_pages_added(self, source, tab_name):
        """AC2: All four tab pages are added."""
        assert f'AddPage(self.{tab_name.lower()}_panel, "{tab_name}")' in source

    @pytest.mark.parametrize(
        "attr_name",
        [
            "wpc_short_range",
            "wpc_medium_range",
            "wpc_extended",
            "wpc_qpf",
        ],
    )
    def test_wpc_text_controls(self, source, attr_name):
        """AC3: WPC tab has all required text controls."""
        assert f"self.{attr_name}" in source

    @pytest.mark.parametrize(
        "attr_name",
        ["spc_day1", "spc_day2", "spc_day3"],
    )
    def test_spc_text_controls(self, source, attr_name):
        """AC4: SPC tab has all required text controls."""
        assert f"self.{attr_name}" in source

    @pytest.mark.parametrize(
        "attr_name",
        ["nhc_atlantic", "nhc_east_pacific"],
    )
    def test_nhc_text_controls(self, source, attr_name):
        """AC5: NHC tab has all required text controls."""
        assert f"self.{attr_name}" in source

    @pytest.mark.parametrize(
        "attr_name",
        ["cpc_6_10_day", "cpc_8_14_day"],
    )
    def test_cpc_text_controls(self, source, attr_name):
        """AC6: CPC tab has all required text controls."""
        assert f"self.{attr_name}" in source

    @pytest.mark.parametrize(
        "name_str",
        [
            "WPC Short Range Forecast Discussion",
            "WPC Medium Range Forecast Discussion",
            "WPC Extended Forecast Discussion",
            "WPC QPF Discussion",
            "SPC Day 1 Convective Outlook",
            "SPC Day 2 Convective Outlook",
            "SPC Day 3 Convective Outlook",
            "NHC Atlantic Tropical Weather Outlook",
            "NHC East Pacific Tropical Weather Outlook",
            "CPC 6-10 Day Outlook",
            "CPC 8-14 Day Outlook",
        ],
    )
    def test_accessible_names(self, source, name_str):
        """AC7: All text controls have name= parameter for accessibility."""
        assert f'name="{name_str}"' in source

    def test_close_button(self, source):
        """AC8: Close button exists."""
        assert "wx.ID_CLOSE" in source

    def test_readonly_style(self, source):
        """All text controls are read-only."""
        assert "wx.TE_READONLY" in source

    def test_default_size(self, source):
        """Dialog has 800x600 default size."""
        assert "800, 600" in source


class TestDialogPackageExport:
    """Test that the dialog is properly exported from the package."""

    def test_exported_in_init(self):
        """AC9: show_nationwide_discussion_dialog is in __init__.py exports."""
        init_path = "src/accessiweather/ui/dialogs/__init__.py"
        with open(init_path) as f:
            content = f.read()
        assert "show_nationwide_discussion_dialog" in content

    def test_in_all_list(self):
        """show_nationwide_discussion_dialog is in __all__."""
        init_path = "src/accessiweather/ui/dialogs/__init__.py"
        with open(init_path) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "__all__"
                        and isinstance(node.value, ast.List)
                    ):
                        elements = [
                            elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)
                        ]
                        assert "show_nationwide_discussion_dialog" in elements
                        return
        pytest.fail("__all__ not found or doesn't contain the function")
