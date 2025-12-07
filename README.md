# pytest-ansible-kind

Pytest plugin for running Ansible playbooks against a local KIND Kubernetes cluster.

The plugin manages KIND cluster lifecycle, provides a kubeconfig to your tests, and can clean up automatically.

## Quick Example

```python
from pytest_ansible_kind import KindRunner
from kubernetes import client, config

def test_k8s_cluster(kind_runner: KindRunner):
    kubeconfig = kind_runner("playbooks/playbook.yaml")
    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "test-ns" in ns_names
```

## Cluster Name Logic

- If no name is given and no config file: defaults to "kind".
- If a config file is supplied, the name comes from the YAML (`name:` field).
- If both are missing, "kind" is assumed.
- If the YAML is invalid, the test fails with `KindConfigError`.
- If a cluster with that name exists, it is reused.
- If `shutdown` is true, it is deleted after tests.

## Pytest Options

pytest.ini:

```ini
[pytest]
kind_config = tests/my-cluster.yaml
kind_shutdown = true
kind_project_dir = .
```

CLI overrides:

```
pytest --kind-config tests/my-cluster.yaml --kind-shutdown
```

## Fixture

```python
def kind_runner(
    playbook: str,
    project_dir: str | None = None,
    extravars: dict[str, Any] | None = None,
    inventory_file: str | None = None,
    kind_config: str | None = None,
) -> str:
    """Runs the Ansible playbook and returns kubeconfig path."""
```

## Exception Handling

The plugin provides typed exceptions for better error handling:

```python
from pytest_ansible_kind import (
    KindError,              # Base exception for all plugin errors
    KindBinaryMissingError, # kind, kubectl, or ansible-playbook not found
    KindClusterError,       # KIND cluster operations failed
    KindConfigError,        # Invalid or missing KIND config YAML
    PlaybookNotFoundError,  # Ansible playbook not found
    PlaybookFailedError,    # Ansible playbook execution failed
    InventoryNotFoundError, # Inventory file not found
    ProjectDirError,        # Invalid project directory
)

def test_with_error_handling(kind_runner: KindRunner):
    try:
        kubeconfig = kind_runner("playbooks/deploy.yaml")
    except PlaybookFailedError as e:
        print(f"Playbook {e.playbook} failed: status={e.status}, rc={e.rc}")
        raise
    except KindClusterError as e:
        print(f"Cluster error: {e.returncode}")
        raise
```

## Example with Config

```yaml
# tests/my-cluster.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: my-cluster
nodes:
  - role: control-plane
  - role: worker
```

```python
from pytest_ansible_kind import KindRunner

def test_with_config(kind_runner: KindRunner):
    kubeconfig = kind_runner("tests/playbook.yaml", kind_config="tests/my-cluster.yaml")
```
