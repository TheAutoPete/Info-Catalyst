import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path():
    path = Path("tests") / ".tmp" / f"pytest-local-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
