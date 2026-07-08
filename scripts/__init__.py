"""Repo maintenance scripts.

This must be a regular package (not a PEP 420 namespace package): the
Windows-Toasts dependency installs its own top-level ``scripts`` package into
site-packages, and a regular package anywhere on ``sys.path`` beats a
namespace package everywhere. With this file present and the repo root
prepended via ``pythonpath`` in pytest.ini, ``from scripts.changelog_tools
import ...`` resolves to this directory.
"""
