import os

import pytest
from fastapi import HTTPException

from utils.safe_path import safe_join


def test_safe_join_stays_inside_root(tmp_path):
    root = tmp_path / "uploads"
    root.mkdir()
    assert safe_join(str(root), "corals", "3", "a.jpg") == os.path.join(os.path.realpath(root), "corals", "3", "a.jpg")
    outside = tmp_path / "secret"
    outside.mkdir()
    (root / "lien").symlink_to(outside)
    for parts in (("..", "secret"), ("/etc/passwd",), ("corals", "../../secret"), ("lien", "x"), ()):
        with pytest.raises(HTTPException) as err:
            safe_join(str(root), *parts)
        assert err.value.status_code == 400
