import os

import pytest


@pytest.fixture(scope="function", autouse=True)
def cd_test_dir():
    os.chdir(os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="function", autouse=True)
def collection_path(request):
    return os.path.dirname(os.path.dirname(__file__))
