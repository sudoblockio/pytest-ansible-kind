import pytest

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Any, Callable, Generator

from pytest_ansible_kind.ansible import run_playbook

DEFAULT_KIND_NAME = "test-kind"


def require_bins(*bins: str) -> None:
    missing = [b for b in bins if shutil.which(b) is None]
    if missing:
        raise RuntimeError("Missing required binaries: " + ", ".join(missing))


def pytest_addoption(parser):
    # INI options
    parser.addini("k8s_shutdown", "shut down kind after tests or not", default="false")
    parser.addini("k8s_workers", "number of worker nodes for kind", default="0")
    parser.addini("k8s_image", "kind node image (optional)", default="")

    # CLI options
    k = parser.getgroup("k8s")
    k.addoption("--k8s-name", action="store", default="kind")
    k.addoption("--k8s-wait", action="store", default="120s")

    # If flag is present => do NOT shutdown (store_false), else follow INI default.
    k.addoption("--k8s-shutdown", action="store_false", default=None)

    # Multi-worker controls
    k.addoption("--k8s-workers", type=int, action="store", default=None)
    k.addoption("--k8s-image", action="store", default=None)


def _kind_out(args: list[str]) -> str:
    return subprocess.check_output(["kind", *args], text=True)


def _cluster_exists(name: str) -> bool:
    clusters = [ln.strip() for ln in _kind_out(["get", "clusters"]).splitlines()]
    return name in clusters


def _render_kind_config(workers: int, image: str | None) -> str:
    lines: list[str] = [
        "kind: Cluster",
        "apiVersion: kind.x-k8s.io/v1alpha4",
        "nodes:",
        "  - role: control-plane",
    ]
    for _ in range(max(0, workers)):
        lines.append("  - role: worker")
    if image:
        pass
    return "\n".join(lines) + "\n"


def _ensure_kind(name: str, wait: str, workers: int, image: str | None) -> None:
    require_bins("kind", "kubectl", "ansible-playbook")

    if _cluster_exists(name):
        return

    cmd = ["kind", "create", "cluster", f"--name={name}", f"--wait={wait}"]

    temp_cfg_path: str | None = None
    if workers > 0:
        cfg = _render_kind_config(workers=workers, image=image)
        with tempfile.NamedTemporaryFile(
            "w", delete=False, prefix=f"{name}-", suffix=".yaml"
        ) as tf:
            tf.write(cfg)
            temp_cfg_path = tf.name
        cmd.extend(["--config", temp_cfg_path])

    if image:
        cmd.extend(["--image", image])

    try:
        subprocess.run(cmd, check=True)
    finally:
        if temp_cfg_path and os.path.exists(temp_cfg_path):
            os.unlink(temp_cfg_path)


def _kubeconfig_path(name: str) -> str:
    p = os.path.join(tempfile.gettempdir(), f"{name}-kubeconfig")
    with open(p, "w") as fh:
        fh.write(_kind_out(["get", "kubeconfig", f"--name={name}"]))
    return p


def _parse_ini_bool(val: str) -> bool:
    v = (val or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"Invalid boolean for k8s_shutdown: {val!r}")


@contextmanager
def kind_runner(
    *,
    name: str = DEFAULT_KIND_NAME,
    shutdown: bool = True,
    wait: str = "120s",
    workers: int = 0,
    image: str | None = None,
) -> Generator[Callable[[Any], str], None, None]:
    # Minimal input validation
    assert isinstance(shutdown, bool), "k8s_shutdown must resolve to a boolean"
    assert isinstance(workers, int) and workers >= 0, (
        "k8s_workers must be a non-negative integer"
    )
    assert isinstance(name, str) and name, "k8s_name must be a non-empty string"
    assert isinstance(wait, str) and wait, "k8s_wait must be a non-empty string"
    if image is not None:
        assert isinstance(image, str) and image, (
            "k8s_image must be a non-empty string when provided"
        )

    _ensure_kind(name=name, wait=wait, workers=workers, image=image)
    kubeconfig = _kubeconfig_path(name)

    def _runner(
        playbook: str,
        project_dir: str,
        extravars: dict[str, Any] | None = None,
    ) -> str:
        run_playbook(
            playbook=playbook,
            project_dir=project_dir,
            extravars=extravars or {},
            envvars={"KUBECONFIG": kubeconfig},
        )
        return kubeconfig

    try:
        yield _runner
    finally:
        if shutdown:
            subprocess.run(["kind", "delete", "cluster", f"--name={name}"], check=False)


@pytest.fixture(scope="module")
def kind_run(request):
    name = request.config.getoption("k8s_name")
    wait = request.config.getoption("k8s_wait")

    # Shutdown precedence: CLI flag (store_false) overrides INI boolean
    shutdown_flag = request.config.getoption("--k8s-shutdown")
    shutdown_ini = _parse_ini_bool(request.config.getini("k8s_shutdown"))
    shutdown = shutdown_flag if shutdown_flag is not None else shutdown_ini
    assert isinstance(shutdown, bool), "k8s_shutdown must resolve to a boolean"

    # Workers precedence: CLI overrides INI, default 0
    workers_cli = request.config.getoption("k8s_workers")
    try:
        workers_ini = int(request.config.getini("k8s_workers") or 0)
    except ValueError as e:
        raise ValueError("k8s_workers INI must be an integer") from e
    workers = workers_cli if workers_cli is not None else workers_ini
    assert isinstance(workers, int) and workers >= 0, (
        "k8s_workers must be a non-negative integer"
    )

    # Image precedence: CLI overrides INI, default None
    image_cli = request.config.getoption("k8s_image")
    image_ini = (request.config.getini("k8s_image") or "").strip()
    image = image_cli if image_cli else (image_ini if image_ini else None)
    if image is not None:
        assert isinstance(image, str) and image, (
            "k8s_image must be a non-empty string when provided"
        )

    assert isinstance(name, str) and name, "k8s_name must be a non-empty string"
    assert isinstance(wait, str) and wait, "k8s_wait must be a non-empty string"

    with kind_runner(
        name=name, wait=wait, shutdown=shutdown, workers=workers, image=image
    ) as run:
        yield run
