import os
from kubernetes import client, config


def test_override_hosts_inventory_default(collection_path, kind_run):
    """
    No inventory_file provided:
    - plugin adopts hosts from playbook (localhost + connection: local)
    """
    kubeconfig = kind_run(
        playbook=os.path.join(collection_path, "tests", "playbook-override-hosts.yaml"),
        project_dir=collection_path,
    )

    assert isinstance(kubeconfig, str) and os.path.isfile(kubeconfig)
    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "test-ns" in ns_names


def test_with_inventory(collection_path, kind_run):
    """
    inventory_file provided:
    - playbook hosts 'clusters' are resolved via inventory.ini
    """
    kubeconfig = kind_run(
        playbook=os.path.join(collection_path, "tests", "playbook-localhost.yaml"),
        project_dir=collection_path,
        inventory_file=os.path.join(collection_path, "tests", "inventory.ini"),
    )

    assert isinstance(kubeconfig, str) and os.path.isfile(kubeconfig)
    config.load_kube_config(config_file=kubeconfig)
    v1 = client.CoreV1Api()
    ns_names = {ns.metadata.name for ns in v1.list_namespace().items}
    assert "test-ns" in ns_names
