import pytest

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Any, Callable, Generator

import yaml
from ansible_runner import Runner, RunnerConfig

DEFAULT_KIND_NAME = "test-kind"


def require_bins(*bins: str) -> None:
    missing = [b for b in bins if shutil.which(b) is None]
    if missing:
        raise RuntimeError("Missing required binaries: " + ", ".join(missing))


def _addoption_safe(group, *args, **kwargs) -> bool:
    """
    Try to add a CLI option; if another plugin already registered it,
    swallow the ValueError so we can coexist.
    """
    try:
        group.addoption(*args, **kwargs)
        return True
    except ValueError:
        return False


def _addini_safe(
    parser, name: str, help_text: str, *, default: str | None = None
) -> bool:
    """
    Try to add an INI key; if already present, ignore.
    """
    try:
        parser.addini(name, help_text, default=default)
        return True
    except ValueError:
        return False


def pytest_addoption(parser):
    """
    Register classic kind options. If another plugin already registered them,
    we do not error; we just reuse them at runtime.
    """
    # INI options
    _addini_safe(
        parser, "kind_shutdown", "shut down kind after tests or not", default="false"
    )
    _addini_safe(parser, "kind_workers", "number of worker nodes for kind", default="0")
    _addini_safe(parser, "kind_image", "kind node image (optional)", default="")
    _addini_safe(
        parser,
        "kind_project_dir",
        "Base project dir containing roles/ and tests/. If empty, inferred from test path.",
        default="",
    )

    # CLI options
    k = parser.getgroup("kind")
    _addoption_safe(
        k, "--kind-name", action="store", default="kind", help="kind cluster name"
    )
    _addoption_safe(
        k, "--kind-wait", action="store", default="120s", help="kind create --wait"
    )

    # If flag is present => do NOT shutdown (store_false), else follow INI default.
    _addoption_safe(
        k, "--kind-shutdown", action="store_false", default=None, help="do not shutdown"
    )

    # Multi-worker controls
    _addoption_safe(
        k, "--kind-workers", type=int, action="store", default=None, help="worker count"
    )
    _addoption_safe(k, "--kind-image", action="store", default=None, help="node image")

    # Project dir override
    _addoption_safe(
        k,
        "--kind-project-dir",
        action="store",
        default=None,
        help="ansible project dir",
    )


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
    # NOTE: image can be applied via CLI; if you want per-node images, extend here.
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
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(_kind_out(["get", "kubeconfig", f"--name={name}"]))
    return p


def _parse_ini_bool(val: str) -> bool:
    v = (val or "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"Invalid boolean for kind_shutdown: {val!r}")


def _infer_project_dir_from_request(request) -> str:
    """
    Linux/macOS only:
    - Walk up from the test file until a directory named 'tests' is found.
    - Use its parent as the project_dir.
    - If not found before filesystem root, fall back to parent-of-test-file.
    """
    test_file = os.path.abspath(str(request.fspath))
    cur = os.path.dirname(test_file)

    while True:
        if os.path.basename(cur) == "tests":
            return os.path.dirname(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            # hit filesystem root: fall back to the test file's parent
            return os.path.dirname(os.path.dirname(test_file))
        cur = parent


def _resolve_playbook_path(project_dir: str, playbook: str) -> str:
    """
    Minimal and Ansible-aligned:
    - If 'playbook' is absolute and exists -> use it.
    - Else treat 'playbook' as relative to 'project_dir' and require it to exist.
    """
    if os.path.isabs(playbook):
        if os.path.exists(playbook):
            return playbook
        raise FileNotFoundError(f"playbook not found: {playbook!r}")

    candidate = os.path.join(project_dir, playbook)
    if os.path.exists(candidate):
        return candidate

    raise FileNotFoundError(
        f"playbook not found relative to project_dir. "
        f"project_dir={project_dir!r}, playbook={playbook!r}, tried={candidate!r}"
    )


def extract_play_hosts(playbook_path: str) -> list[str]:
    """
    Minimal parser to extract unique `hosts` patterns from a playbook.
    Returns an ordered list of unique host patterns (strings). Empty if none.
    """
    with open(playbook_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    plays: list[dict[str, Any]]
    if isinstance(data, list):
        plays = [p for p in data if isinstance(p, dict)]
    elif isinstance(data, dict):
        plays = [data]
    else:
        return []

    seen: set[str] = set()
    out: list[str] = []
    for p in plays:
        h = p.get("hosts")
        if isinstance(h, str):
            hv = h.strip()
            if hv and hv not in seen:
                seen.add(hv)
                out.append(hv)
    return out


@contextmanager
def kind_runner(
    *,
    name: str = DEFAULT_KIND_NAME,
    shutdown: bool = True,
    wait: str = "120s",
    workers: int = 0,
    image: str | None = None,
    default_project_dir: str | None = None,
) -> Generator[
    Callable[[str, str | None, dict[str, Any] | None, str | None], str], None, None
]:
    # Minimal input validation
    assert isinstance(shutdown, bool), "kind_shutdown must resolve to a boolean"
    assert isinstance(workers, int) and workers >= 0, (
        "kind_workers must be a non-negative integer"
    )
    assert isinstance(name, str) and name, "kind_name must be a non-empty string"
    assert isinstance(wait, str) and wait, "kind_wait must be a non-empty string"
    if image is not None:
        assert isinstance(image, str) and image, (
            "kind_image must be a non-empty string when provided"
        )

    _ensure_kind(name=name, wait=wait, workers=workers, image=image)
    kubeconfig = _kubeconfig_path(name)

    def _runner(
        playbook: str,
        project_dir: str | None = None,
        extravars: dict[str, Any] | None = None,
        inventory_file: str | None = None,  # Optional override
    ) -> str:
        """
        Inventory override rules:
        - if inventory_file is provided, pass-through (exact override).
        - else, adopt playbook hosts and map each alias to local execution
          by generating a temporary INI inventory with ansible_connection=local.
        """
        project_dir = project_dir or default_project_dir
        resolved_playbook = _resolve_playbook_path(project_dir, playbook)

        temp_inv_path: str | None = None
        try:
            if inventory_file:
                inventory_arg = inventory_file
            else:
                patterns = extract_play_hosts(resolved_playbook)
                host_aliases = patterns or ["localhost"]
                # Write small INI inventory that forces local connection for each alias.
                with tempfile.NamedTemporaryFile(
                    "w", delete=False, prefix="kind-inv-", suffix=".ini"
                ) as tf:
                    for alias in host_aliases:
                        tf.write(f"{alias} ansible_connection=local\n")
                    temp_inv_path = tf.name
                inventory_arg = temp_inv_path

            rcfg = RunnerConfig(
                playbook=resolved_playbook,
                project_dir=project_dir,
                inventory=inventory_arg,
                extravars=extravars or {},
                envvars={"KUBECONFIG": kubeconfig},
                private_data_dir=project_dir,
                roles_path=os.path.join(project_dir, "roles"),
                artifact_dir=os.path.join(project_dir, ".artifacts"),
            )
            rcfg.prepare()
            status, rc = Runner(config=rcfg).run()

            if not (status == "successful" and rc == 0):
                raise RuntimeError(f"play failed: status={status}, rc={rc}")

            return kubeconfig
        finally:
            if temp_inv_path and os.path.exists(temp_inv_path):
                try:
                    os.unlink(temp_inv_path)
                except OSError:
                    pass  # non-fatal cleanup

    try:
        yield _runner
    finally:
        if shutdown:
            subprocess.run(["kind", "delete", "cluster", f"--name={name}"], check=False)


@pytest.fixture(scope="module")
def kind_run(request):
    # Read options by dest names (shared with any provider of the same CLI flags)
    name = request.config.getoption("kind_name")
    wait = request.config.getoption("kind_wait")

    # Shutdown precedence: CLI flag (store_false) overrides INI boolean
    shutdown_flag = request.config.getoption("kind_shutdown")  # may be None or False
    shutdown_ini = _parse_ini_bool(request.config.getini("kind_shutdown"))
    shutdown = shutdown_flag if shutdown_flag is not None else shutdown_ini
    assert isinstance(shutdown, bool), "kind_shutdown must resolve to a boolean"

    # Workers precedence: CLI overrides INI, default 0
    workers_cli = request.config.getoption("kind_workers")
    try:
        workers_ini = int(request.config.getini("kind_workers") or 0)
    except ValueError as e:
        raise ValueError("kind_workers INI must be an integer") from e
    workers = workers_cli if workers_cli is not None else workers_ini
    assert isinstance(workers, int) and workers >= 0, (
        "kind_workers must be a non-negative integer"
    )

    # Image precedence: CLI overrides INI, default None
    image_cli = request.config.getoption("kind_image")
    image_ini = (request.config.getini("kind_image") or "").strip()
    image = image_cli if image_cli else (image_ini if image_ini else None)
    if image is not None:
        assert isinstance(image, str) and image, (
            "kind_image must be a non-empty string when provided"
        )

    assert isinstance(name, str) and name, "kind_name must be a non-empty string"
    assert isinstance(wait, str) and wait, "kind_wait must be a non-empty string"

    # Project dir precedence: CLI (--kind-project-dir) > INI (kind_project_dir) > inferred
    proj_cli = request.config.getoption("kind_project_dir")
    proj_ini = (request.config.getini("kind_project_dir") or "").strip()
    if proj_cli:
        default_project_dir = os.path.abspath(proj_cli)
    elif proj_ini:
        default_project_dir = os.path.abspath(proj_ini)
    else:
        default_project_dir = _infer_project_dir_from_request(request)

    # One assertion to enforce expected ansible layout (sibling tests/ and roles/)
    assert (
        os.path.isdir(default_project_dir)
        and os.path.isdir(os.path.join(default_project_dir, "tests"))
        and os.path.isdir(os.path.join(default_project_dir, "roles"))
    ), (
        f"Invalid ansible project layout. Expected sibling 'tests' and 'roles' "
        f"under project_dir; resolved project_dir={default_project_dir!r}"
    )

    with kind_runner(
        name=name,
        wait=wait,
        shutdown=shutdown,
        workers=workers,
        image=image,
        default_project_dir=default_project_dir,
    ) as run:
        yield run
