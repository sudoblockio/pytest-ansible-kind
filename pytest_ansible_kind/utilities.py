from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pytest


def default_kind_config_from_pytest(request: pytest.FixtureRequest) -> str | None:
    """
    Resolve the KIND config path from CLI / ini.

    Precedence:
    1. --kind-config CLI option
    2. kind_config in [pytest] section of pytest.ini

    If neither is set or the value is empty, returns None (KIND defaults).
    If the path is relative, it is resolved against pytest's rootpath.
    """
    cfg = request.config

    path_opt = cfg.getoption("kind_config")
    path_ini = (cfg.getini("kind_config") or "").strip()
    raw_path = path_opt or path_ini

    if not raw_path:
        return None

    p = Path(raw_path)
    if not p.is_absolute():
        p = Path(cfg.rootpath) / raw_path

    return str(p)


def infer_project_dir_from_request(request: pytest.FixtureRequest) -> str:
    """
    Infer the Ansible project directory from the test file location.

    Walks up from the current test file until it finds a directory named
    ``tests`` and returns its parent. If no such directory is found,
    falls back to two levels up from the test file.
    """
    test_path = Path(str(request.node.path)).resolve()
    cur = test_path.parent

    while True:
        if cur.name == "tests":
            return str(cur.parent)

        parent = cur.parent
        if parent == cur:
            # Reached filesystem root, fall back to <test_file>/../..
            return str(test_path.parent.parent)
        cur = parent


def resolve_project_dir_and_shutdown(
    request: pytest.FixtureRequest,
) -> Tuple[str, bool]:
    """
    Resolve the effective project directory and shutdown flag from pytest config.

    Precedence for project_dir:
    1. --kind-project-dir CLI option
    2. kind_project_dir in [pytest] section
    3. Inferred from the test file path via infer_project_dir_from_request.

    Precedence for shutdown:
    1. --kind-shutdown CLI flag (True/False by presence)
    2. kind_shutdown in [pytest] section (parsed as bool, default false)
    """
    cfg = request.config

    # Shutdown resolution
    shutdown_flag: bool | None = cfg.getoption("kind_shutdown")
    shutdown_ini_raw = (cfg.getini("kind_shutdown") or "false").strip().lower()
    shutdown_ini = shutdown_ini_raw in ("1", "true", "yes", "on")
    shutdown = shutdown_flag if shutdown_flag is not None else shutdown_ini

    # Project dir resolution
    proj_cli = cfg.getoption("kind_project_dir")
    proj_ini = (cfg.getini("kind_project_dir") or "").strip()

    if proj_cli:
        project_dir = str(Path(proj_cli).resolve())
    elif proj_ini:
        project_dir = str(Path(proj_ini).resolve())
    else:
        project_dir = infer_project_dir_from_request(request)

    return project_dir, shutdown
