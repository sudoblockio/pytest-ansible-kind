from __future__ import annotations

import os

import pytest


def default_kind_config_from_pytest(request: pytest.FixtureRequest) -> str | None:
    cfg = request.config
    path_opt = cfg.getoption("kind_config")
    path_ini = (cfg.getini("kind_config") or "").strip()
    raw_path = path_opt or path_ini
    if not raw_path:
        return None

    if not os.path.isabs(raw_path):
        raw_path = os.path.join(str(cfg.rootpath), raw_path)

    return raw_path


# TODO: Fix this typing -> Was Any before
def infer_project_dir_from_request(request: pytest.FixtureRequest) -> str:
    test_file = os.path.abspath(str(request.fspath))  # Fix this
    cur = os.path.dirname(test_file)
    while True:
        if os.path.basename(cur) == "tests":
            return os.path.dirname(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.dirname(os.path.dirname(test_file))
        cur = parent


def resolve_project_dir_and_shutdown(
    request: pytest.FixtureRequest,
) -> tuple[str, bool]:
    cfg = request.config

    shutdown_flag = cfg.getoption("kind_shutdown")
    shutdown_ini_raw = (cfg.getini("kind_shutdown") or "false").strip().lower()
    shutdown_ini = shutdown_ini_raw in ("1", "true", "yes", "on")
    shutdown = shutdown_flag if shutdown_flag is not None else shutdown_ini

    proj_cli = cfg.getoption("kind_project_dir")
    proj_ini = (cfg.getini("kind_project_dir") or "").strip()
    if proj_cli:
        project_dir = os.path.abspath(proj_cli)
    elif proj_ini:
        project_dir = os.path.abspath(proj_ini)
    else:
        project_dir = infer_project_dir_from_request(request)

    return project_dir, shutdown
