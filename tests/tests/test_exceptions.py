"""Unit tests for exceptions and error handling in pytest-ansible-kind."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pytest_ansible_kind import (
    InventoryNotFoundError,
    KindBinaryMissingError,
    KindClusterError,
    KindConfigError,
    KindError,
    PlaybookFailedError,
    PlaybookNotFoundError,
    ProjectDirError,
)
from pytest_ansible_kind.runner import (
    _derive_name_from_cfg,
    _require_bins,
    _resolve_playbook_path,
    _run_kind_checked,
)


class TestKindError:
    """Test base KindError exception."""

    def test_kind_error_is_exception(self):
        assert issubclass(KindError, Exception)

    def test_kind_error_message(self):
        exc = KindError("test message")
        assert str(exc) == "test message"


class TestKindBinaryMissingError:
    """Test KindBinaryMissingError exception."""

    def test_inherits_from_kind_error(self):
        assert issubclass(KindBinaryMissingError, KindError)

    def test_single_missing_binary(self):
        exc = KindBinaryMissingError(["kind"])
        assert exc.missing == ["kind"]
        assert "kind" in str(exc)
        assert "Missing required binaries" in str(exc)

    def test_multiple_missing_binaries(self):
        exc = KindBinaryMissingError(["kind", "kubectl", "ansible-playbook"])
        assert exc.missing == ["kind", "kubectl", "ansible-playbook"]
        assert "kind" in str(exc)
        assert "kubectl" in str(exc)
        assert "ansible-playbook" in str(exc)

    def test_require_bins_raises_on_missing(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(KindBinaryMissingError) as exc_info:
                _require_bins("nonexistent-binary-xyz")
            assert "nonexistent-binary-xyz" in exc_info.value.missing

    def test_require_bins_passes_when_present(self):
        with patch("shutil.which", return_value="/usr/bin/test"):
            _require_bins("test-binary")


class TestKindClusterError:
    """Test KindClusterError exception."""

    def test_inherits_from_kind_error(self):
        assert issubclass(KindClusterError, KindError)

    def test_basic_message(self):
        exc = KindClusterError("cluster failed")
        assert "cluster failed" in str(exc)

    def test_with_command(self):
        exc = KindClusterError("failed", cmd=["kind", "create", "cluster"])
        assert "kind create cluster" in str(exc)

    def test_with_returncode(self):
        exc = KindClusterError("failed", returncode=1)
        assert "Exit code: 1" in str(exc)

    def test_with_stdout(self):
        exc = KindClusterError("failed", stdout="some output")
        assert "stdout" in str(exc)
        assert "some output" in str(exc)

    def test_with_stderr(self):
        exc = KindClusterError("failed", stderr="error output")
        assert "stderr" in str(exc)
        assert "error output" in str(exc)

    def test_full_error_details(self):
        exc = KindClusterError(
            message="KIND command failed",
            cmd=["kind", "create", "cluster"],
            returncode=1,
            stdout="creating cluster",
            stderr="error: already exists",
        )
        msg = str(exc)
        assert "KIND command failed" in msg
        assert "kind create cluster" in msg
        assert "Exit code: 1" in msg
        assert "creating cluster" in msg
        assert "already exists" in msg


class TestKindConfigError:
    """Test KindConfigError exception."""

    def test_inherits_from_kind_error(self):
        assert issubclass(KindConfigError, KindError)

    def test_basic_message(self):
        exc = KindConfigError("invalid config")
        assert str(exc) == "invalid config"

    def test_with_config_path(self):
        exc = KindConfigError("config not found", config_path="/path/to/config.yaml")
        assert "/path/to/config.yaml" in str(exc)
        assert exc.config_path == "/path/to/config.yaml"

    def test_derive_name_raises_on_missing_file(self):
        with pytest.raises(KindConfigError) as exc_info:
            _derive_name_from_cfg("/nonexistent/path/config.yaml")
        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.config_path == "/nonexistent/path/config.yaml"

    def test_derive_name_raises_on_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
            tf.write("invalid: yaml: content: [")
            tf.flush()
            try:
                with pytest.raises(KindConfigError) as exc_info:
                    _derive_name_from_cfg(tf.name)
                assert "Invalid YAML" in str(exc_info.value)
            finally:
                os.unlink(tf.name)

    def test_derive_name_returns_default_on_no_name(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
            tf.write("apiVersion: kind.x-k8s.io/v1alpha4\nkind: Cluster\n")
            tf.flush()
            try:
                result = _derive_name_from_cfg(tf.name)
                assert result == "kind"
            finally:
                os.unlink(tf.name)

    def test_derive_name_extracts_name(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
            tf.write("name: my-test-cluster\n")
            tf.flush()
            try:
                result = _derive_name_from_cfg(tf.name)
                assert result == "my-test-cluster"
            finally:
                os.unlink(tf.name)


class TestPlaybookNotFoundError:
    """Test PlaybookNotFoundError exception."""

    def test_inherits_from_kind_error(self):
        assert issubclass(PlaybookNotFoundError, KindError)

    def test_basic_message(self):
        exc = PlaybookNotFoundError("playbook.yaml")
        assert "playbook.yaml" in str(exc)
        assert exc.playbook == "playbook.yaml"

    def test_with_project_dir(self):
        exc = PlaybookNotFoundError("playbook.yaml", project_dir="/project")
        assert "playbook.yaml" in str(exc)
        assert "/project" in str(exc)
        assert exc.project_dir == "/project"

    def test_with_tried_path(self):
        exc = PlaybookNotFoundError(
            "playbook.yaml", project_dir="/project", tried="/project/playbook.yaml"
        )
        assert "/project/playbook.yaml" in str(exc)
        assert exc.tried == "/project/playbook.yaml"

    def test_resolve_playbook_raises_on_missing_absolute(self):
        with pytest.raises(PlaybookNotFoundError) as exc_info:
            _resolve_playbook_path("/project", "/nonexistent/playbook.yaml")
        assert exc_info.value.playbook == "/nonexistent/playbook.yaml"

    def test_resolve_playbook_raises_on_missing_relative(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(PlaybookNotFoundError) as exc_info:
                _resolve_playbook_path(tmpdir, "missing-playbook.yaml")
            assert exc_info.value.playbook == "missing-playbook.yaml"
            assert exc_info.value.project_dir == tmpdir

    def test_resolve_playbook_finds_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            playbook_path = Path(tmpdir) / "playbook.yaml"
            playbook_path.write_text("- hosts: localhost\n")
            result = _resolve_playbook_path(tmpdir, "playbook.yaml")
            assert result == str(playbook_path)


class TestPlaybookFailedError:
    """Test PlaybookFailedError exception."""

    def test_inherits_from_kind_error(self):
        assert issubclass(PlaybookFailedError, KindError)

    def test_basic_message(self):
        exc = PlaybookFailedError("playbook.yaml", status="failed", rc=1)
        assert "playbook.yaml" in str(exc)
        assert "failed" in str(exc)
        assert "rc=1" in str(exc)
        assert exc.playbook == "playbook.yaml"
        assert exc.status == "failed"
        assert exc.rc == 1

    def test_with_output(self):
        exc = PlaybookFailedError(
            "playbook.yaml", status="failed", rc=2, output="task failed"
        )
        assert "task failed" in str(exc)
        assert exc.output == "task failed"


class TestInventoryNotFoundError:
    """Test InventoryNotFoundError exception."""

    def test_inherits_from_kind_error(self):
        assert issubclass(InventoryNotFoundError, KindError)

    def test_basic_message(self):
        exc = InventoryNotFoundError("inventory.ini")
        assert "inventory.ini" in str(exc)
        assert exc.inventory == "inventory.ini"

    def test_with_project_dir(self):
        exc = InventoryNotFoundError("inventory.ini", project_dir="/project")
        assert "inventory.ini" in str(exc)
        assert "/project" in str(exc)
        assert exc.project_dir == "/project"


class TestProjectDirError:
    """Test ProjectDirError exception."""

    def test_inherits_from_kind_error(self):
        assert issubclass(ProjectDirError, KindError)

    def test_basic_message(self):
        exc = ProjectDirError("invalid project")
        assert str(exc) == "invalid project"

    def test_with_project_dir(self):
        exc = ProjectDirError("does not exist", project_dir="/bad/path")
        assert "/bad/path" in str(exc)
        assert exc.project_dir == "/bad/path"


class TestRunKindChecked:
    """Test _run_kind_checked raises proper exceptions."""

    def test_raises_kind_cluster_error_on_failure(self):
        with pytest.raises(KindClusterError) as exc_info:
            _run_kind_checked(["kind", "get", "clusters", "--nonexistent-flag-xyz"])

        exc = exc_info.value
        assert exc.cmd is not None
        assert exc.returncode is not None
        assert exc.returncode != 0
