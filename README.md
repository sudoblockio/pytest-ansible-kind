# pytest-ansible-kind

Pytest plugin for running Ansible playbooks against a local KIND Kubernetes cluster.

## Simple Usage

```python
from kubernetes import client
from pytest_ansible_kind import KindRunner

def test_namespace_created(kind_runner: KindRunner):
    api_client = kind_runner("playbooks/create-namespace.yaml")
    v1 = client.CoreV1Api(api_client)
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "my-namespace" in ns_names
```

## With Custom Cluster Config

```python
def test_multi_node_cluster(kind_runner: KindRunner):
    api_client = kind_runner(
        "playbooks/deploy-app.yaml",
        kind_config="tests/multi-node.yaml",
    )
    v1 = client.CoreV1Api(api_client)
    nodes = v1.list_node().items
    assert len(nodes) == 3
```

```yaml
# tests/multi-node.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: multi-node
nodes:
  - role: control-plane
  - role: worker
  - role: worker
```

## With Inventory and Extra Variables

```python
def test_with_inventory(kind_runner: KindRunner):
    api_client = kind_runner(
        "playbooks/configure-cluster.yaml",
        inventory_file="tests/inventory.ini",
        extravars={"namespace": "production", "replicas": 3},
    )
    apps = client.AppsV1Api(api_client)
    deploy = apps.read_namespaced_deployment("my-app", "production")
    assert deploy.spec.replicas == 3
```

## Configuration

pytest.ini:

```ini
[pytest]
kind_config = tests/my-cluster.yaml
kind_shutdown = true
kind_project_dir = .
```

CLI:

```
pytest --kind-config tests/my-cluster.yaml --kind-shutdown
```

## Cluster Lifecycle

- Clusters are reused if they already exist
- Set `kind_shutdown = true` to delete after tests
- Cluster name is derived from config YAML or defaults to "kind"
