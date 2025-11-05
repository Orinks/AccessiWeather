#!/usr/bin/env python3
"""
Toga Backend Enforcement Checker.

Scans test files to ensure all tests that import toga are using the toga_dummy backend.
This is a CRITICAL requirement for AccessiWeather testing.

Usage:
    python scripts/find_toga_backend_issues.py
    python scripts/find_toga_backend_issues.py --fix  # Auto-fix issues (future)

Exit codes:
    0 - No issues found
    1 - Issues found or error occurred
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TogaImport:
    """Represents a toga import in a file."""

    file_path: Path
    line_number: int
    import_statement: str
    module_name: str


@dataclass
class BackendCheck:
    """Represents a backend enforcement check."""

    file_path: Path
    line_number: int
    check_type: str  # 'env_var', 'fixture', 'conftest'


@dataclass
class FileAnalysis:
    """Analysis results for a single test file."""

    file_path: Path
    has_toga_import: bool
    toga_imports: list[TogaImport]
    backend_checks: list[BackendCheck]
    is_compliant: bool
    reason: str


class TogaBackendVisitor(ast.NodeVisitor):
    """AST visitor to find toga imports and backend checks."""

    def __init__(self, file_path: Path) -> None:
        """
        Initialize the visitor with a file path.

        Args:
            file_path: Path to the file being analyzed.

        """
        self.file_path = file_path
        self.toga_imports: list[TogaImport] = []
        self.backend_checks: list[BackendCheck] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements like 'import toga'."""
        for alias in node.names:
            if "toga" in alias.name:
                self.toga_imports.append(
                    TogaImport(
                        file_path=self.file_path,
                        line_number=node.lineno,
                        import_statement=f"import {alias.name}",
                        module_name=alias.name,
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from imports like 'from toga import ...'."""
        if node.module and "toga" in node.module:
            imported_names = ", ".join(alias.name for alias in node.names)
            self.toga_imports.append(
                TogaImport(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    import_statement=f"from {node.module} import {imported_names}",
                    module_name=node.module,
                )
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignments to find os.environ['TOGA_BACKEND'] = '...'."""
        # Check for os.environ["TOGA_BACKEND"] = "toga_dummy"
        if isinstance(node.value, ast.Constant):
            for target in node.targets:
                # Check if it's environ['TOGA_BACKEND']
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and isinstance(target.value.value, ast.Name)
                    and target.value.value.id == "os"
                    and target.value.attr == "environ"
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "TOGA_BACKEND"
                ):
                    self.backend_checks.append(
                        BackendCheck(
                            file_path=self.file_path,
                            line_number=node.lineno,
                            check_type="env_var",
                        )
                    )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions to find pytest fixtures setting backend."""
        # Check for @pytest.fixture decorators with monkeypatch.setenv
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and "fixture" in decorator.id.lower():
                # Check function body for monkeypatch.setenv("TOGA_BACKEND", ...)
                for stmt in ast.walk(node):
                    if (
                        isinstance(stmt, ast.Call)
                        and isinstance(stmt.func, ast.Attribute)
                        and stmt.func.attr == "setenv"
                        and stmt.args
                        and isinstance(stmt.args[0], ast.Constant)
                        and stmt.args[0].value == "TOGA_BACKEND"
                    ):
                        self.backend_checks.append(
                            BackendCheck(
                                file_path=self.file_path,
                                line_number=node.lineno,
                                check_type="fixture",
                            )
                        )
        self.generic_visit(node)


def analyze_file(file_path: Path) -> FileAnalysis | None:
    """Analyze a single test file for toga imports and backend checks."""
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        visitor = TogaBackendVisitor(file_path)
        visitor.visit(tree)

        has_toga = len(visitor.toga_imports) > 0

        if not has_toga:
            # No toga imports, no need to check
            return None

        # Determine compliance
        has_backend_check = len(visitor.backend_checks) > 0

        # Check if conftest.py in same directory or parent has backend check
        conftest_protected = check_conftest_protection(file_path)

        is_compliant = has_backend_check or conftest_protected

        if is_compliant:
            if conftest_protected:
                reason = "Protected by conftest.py"
            else:
                reason = "Has explicit backend check"
        else:
            reason = "Missing backend enforcement"

        return FileAnalysis(
            file_path=file_path,
            has_toga_import=has_toga,
            toga_imports=visitor.toga_imports,
            backend_checks=visitor.backend_checks,
            is_compliant=is_compliant,
            reason=reason,
        )

    except SyntaxError as e:
        print(f"⚠️  Syntax error in {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}", file=sys.stderr)
        return None


def check_conftest_protection(test_file: Path) -> bool:
    """Check if there's a conftest.py that sets TOGA_BACKEND in the hierarchy."""
    # Check current directory and all parents up to tests/
    current = test_file.parent
    tests_dir = Path("tests").resolve()

    while current >= tests_dir:
        conftest = current / "conftest.py"
        if conftest.exists():
            try:
                content = conftest.read_text(encoding="utf-8")
                # Simple check: does it contain the backend assignment?
                if 'os.environ["TOGA_BACKEND"]' in content or "TOGA_BACKEND" in content:
                    return True
            except Exception:
                pass
        current = current.parent

    return False


def scan_tests_directory(tests_dir: Path = Path("tests")) -> list[FileAnalysis]:
    """Scan all test files in the tests directory."""
    analyses: list[FileAnalysis] = []

    for test_file in tests_dir.rglob("test_*.py"):
        analysis = analyze_file(test_file)
        if analysis:  # Only include files with toga imports
            analyses.append(analysis)

    return analyses


def generate_report(analyses: list[FileAnalysis]) -> str:
    """Generate a markdown report of the analysis."""
    violations = [a for a in analyses if not a.is_compliant]
    compliant = [a for a in analyses if a.is_compliant]

    report = ["# Toga Backend Enforcement Report\n"]
    report.append(f"**Total files with toga imports:** {len(analyses)}\n")
    report.append(f"**Compliant files:** {len(compliant)} ✅\n")
    report.append(f"**Violations found:** {len(violations)} ❌\n")
    report.append("\n---\n")

    if violations:
        report.append("\n## ❌ Violations (Files Without Backend Enforcement)\n")
        report.append("\nThese files import toga but do not have backend enforcement:\n\n")

        for analysis in violations:
            report.append(f"### `{analysis.file_path}`\n")
            report.append(f"- **Status:** ❌ {analysis.reason}\n")
            report.append(f"- **Toga imports:** {len(analysis.toga_imports)}\n")
            report.append("- **Import locations:**\n")
            for imp in analysis.toga_imports:
                report.append(f"  - Line {imp.line_number}: `{imp.import_statement}`\n")
            report.append("\n**Fix:** Add this at the top of the file:\n")
            report.append("```python\n")
            report.append("import os\n")
            report.append('os.environ["TOGA_BACKEND"] = "toga_dummy"\n')
            report.append("```\n\n")
    else:
        report.append("\n## ✅ All Files Compliant!\n")
        report.append(
            "\nAll test files that import toga are properly configured to use toga_dummy.\n"
        )

    if compliant:
        report.append("\n## ✅ Compliant Files\n")
        report.append("\nThese files properly enforce toga_dummy backend:\n\n")
        for analysis in compliant:
            check_info = ""
            if analysis.backend_checks:
                check_info = f" (Line {analysis.backend_checks[0].line_number})"
            report.append(f"- `{analysis.file_path}` - {analysis.reason}{check_info}\n")

    report.append("\n---\n")
    report.append("\n## Summary\n")
    if violations:
        report.append(f"\n⚠️  **Action Required:** {len(violations)} file(s) need to be fixed.\n")
        report.append("\nRun the following command to see this report:\n")
        report.append("```bash\n")
        report.append("python scripts/find_toga_backend_issues.py\n")
        report.append("```\n")
    else:
        report.append("\n✅ **All tests are properly configured!**\n")
        report.append("\nAll test files that import toga are using the toga_dummy backend.\n")

    return "".join(report)


def main() -> int:
    """Run the main backend enforcement check."""
    print("🔍 Scanning test files for toga backend issues...\n")

    tests_dir = Path("tests")
    if not tests_dir.exists():
        print(f"❌ Tests directory not found: {tests_dir}", file=sys.stderr)
        return 1

    analyses = scan_tests_directory(tests_dir)

    if not analyses:
        print("ℹ️  No test files found that import toga.")
        return 0

    report = generate_report(analyses)

    # Save report
    report_file = Path(".artiforge/reports/toga-backend-check.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding="utf-8")

    # Print summary to console
    print(report)

    print(f"\n📄 Full report saved to: {report_file}")

    # Return exit code based on violations
    violations = [a for a in analyses if not a.is_compliant]
    if violations:
        print(f"\n❌ Found {len(violations)} violation(s).")
        return 1

    print("\n✅ All toga imports are properly configured!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
