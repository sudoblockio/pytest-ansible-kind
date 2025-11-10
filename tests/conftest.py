import os
import pytest


@pytest.fixture(scope="function", autouse=True)
def cd_test_dir():
    # cd into .../tests so relative paths in tests are simple
    os.chdir(os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="function", autouse=True)
def collection_path():
    # Base directory that contains roles/ and tests/
    return os.path.dirname(os.path.dirname(__file__))
