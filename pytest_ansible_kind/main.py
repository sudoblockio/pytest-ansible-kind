from __future__ import annotations

import os
from typing import Generator

import pytest

from .runner import KindRunner, kind_session


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(
        "kind_config",
        "Path to KIND cluster config (YAML). If empty, KIND defaults are used.",
        default="",
    )
    parser.addini(
        "kind_shutdown",
        "Shutdown KIND cluster when tests complete (true/false).",
        default="false",
    )
    parser.addini(
        "kind_project_dir",
        "Base project dir containing roles/ and tests/. If empty, inferred from test path.",
        default="",
    )

    group = parser.getgroup("kind")
    group.addoption(
        "--kind-config",
        action="store",
        default=None,
        help="Path to KIND cluster config (YAML). Overrides [pytest] kind_config.",
    )
    group.addoption(
        "--kind-shutdown",
        action="store_true",
        default=None,
        help="Shutdown KIND cluster when tests complete. Overrides [pytest] kind_shutdown.",
    )
    group.addoption(
        "--kind-project-dir",
        action="store",
        default=None,
        help="Ansible project dir containing roles/ and tests/. Overrides [pytest] kind_project_dir.",
    )


def _default_kind_config_from_pytest(request: pytest.FixtureRequest) -> str | None:
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
def _infer_project_dir_from_request(request: pytest.FixtureRequest) -> str:
    test_file = os.path.abspath(str(request.fspath))  # Fix this
    cur = os.path.dirname(test_file)
    while True:
        if os.path.basename(cur) == "tests":
            return os.path.dirname(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.dirname(os.path.dirname(test_file))
        cur = parent


def _resolve_project_dir_and_shutdown(
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
        project_dir = _infer_project_dir_from_request(request)

    return project_dir, shutdown


@pytest.fixture(scope="module")
def kind_runner(request: pytest.FixtureRequest) -> Generator[KindRunner, None, None]:
    project_dir, shutdown = _resolve_project_dir_and_shutdown(request)
    default_cfg_path = _default_kind_config_from_pytest(request)

    with kind_session(
        project_dir=project_dir,
        shutdown=shutdown,
        kind_cfg=default_cfg_path,
    ) as runner:
        yield runner
