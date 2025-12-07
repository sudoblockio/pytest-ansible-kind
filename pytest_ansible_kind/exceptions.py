from __future__ import annotations


class KindError(Exception):
    """Base exception for pytest-ansible-kind errors."""


class KindBinaryMissingError(KindError):
    """Raised when required binaries (kind, kubectl, ansible-playbook) are missing."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing required binaries: {', '.join(missing)}")


class KindClusterError(KindError):
    """Raised when a KIND cluster operation fails."""

    def __init__(
        self,
        message: str,
        cmd: str | list[str] | None = None,
        returncode: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        parts = [message]
        if cmd:
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            parts.append(f"Command: {cmd_str}")
        if returncode is not None:
            parts.append(f"Exit code: {returncode}")
        if stdout:
            parts.append("--- stdout ---")
            parts.append(stdout.rstrip())
        if stderr:
            parts.append("--- stderr ---")
            parts.append(stderr.rstrip())
        super().__init__("\n".join(parts))


class KindConfigError(KindError):
    """Raised when KIND cluster config is invalid or missing."""

    def __init__(self, message: str, config_path: str | None = None) -> None:
        self.config_path = config_path
        if config_path:
            message = f"{message}: {config_path!r}"
        super().__init__(message)


class PlaybookNotFoundError(KindError):
    """Raised when an Ansible playbook cannot be found."""

    def __init__(
        self, playbook: str, project_dir: str | None = None, tried: str | None = None
    ) -> None:
        self.playbook = playbook
        self.project_dir = project_dir
        self.tried = tried
        if project_dir:
            msg = (
                f"Playbook not found relative to project_dir. "
                f"project_dir={project_dir!r}, playbook={playbook!r}"
            )
            if tried:
                msg += f", tried={tried!r}"
        else:
            msg = f"Playbook not found: {playbook!r}"
        super().__init__(msg)


class PlaybookFailedError(KindError):
    """Raised when an Ansible playbook execution fails."""

    def __init__(
        self, playbook: str, status: str, rc: int, output: str | None = None
    ) -> None:
        self.playbook = playbook
        self.status = status
        self.rc = rc
        self.output = output
        msg = f"Playbook failed: {playbook!r}, status={status}, rc={rc}"
        if output:
            msg += f"\n--- output ---\n{output.rstrip()}"
        super().__init__(msg)


class InventoryNotFoundError(KindError):
    """Raised when an inventory file cannot be found."""

    def __init__(self, inventory: str, project_dir: str | None = None) -> None:
        self.inventory = inventory
        self.project_dir = project_dir
        if project_dir:
            msg = f"Inventory not found: {inventory!r} (project_dir={project_dir!r})"
        else:
            msg = f"Inventory not found: {inventory!r}"
        super().__init__(msg)


class ProjectDirError(KindError):
    """Raised when project directory is invalid or has bad structure."""

    def __init__(self, message: str, project_dir: str | None = None) -> None:
        self.project_dir = project_dir
        if project_dir:
            message = f"{message}: {project_dir!r}"
        super().__init__(message)
