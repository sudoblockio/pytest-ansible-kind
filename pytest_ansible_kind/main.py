from __future__ import annotations

from typing import Generator

import pytest

from .runner import KindRunner, kind_session
from .utilities import (
    default_kind_config_from_pytest,
    resolve_project_dir_and_shutdown,
)


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


@pytest.fixture(scope="module")
def kind_runner(request: pytest.FixtureRequest) -> Generator[KindRunner, None, None]:
    """
    Module-scoped fixture that provides a KindRunner bound to a resolved
    project directory and shutdown policy.

    - Project dir is taken from CLI, then ini, otherwise inferred from the
      location of the test file.
    - Shutdown defaults to false unless enabled via CLI or ini.
    - KIND config (if provided via CLI/ini) is resolved relative to rootpath.
    """
    project_dir, shutdown = resolve_project_dir_and_shutdown(request)
    kind_cfg = default_kind_config_from_pytest(request)

    with kind_session(
        project_dir=project_dir,
        shutdown=shutdown,
        kind_cfg=kind_cfg,
    ) as runner:
        yield runner
