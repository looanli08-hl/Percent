from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from percent.models import FindingCategory, Fragment
from percent.web import app


@pytest.fixture()
def client():
    return TestClient(app)


def _make_fragment(source: str = "wechat", evidence: str = "said X in chat") -> Fragment:
    return Fragment(
        id=1,
        category=FindingCategory.TRAIT,
        content="test trait",
        confidence=0.85,
        source=source,
        evidence=evidence,
    )


def test_fragments_endpoint_includes_evidence(client):
    frag = _make_fragment(evidence="user said 'I love coding' at 2am")

    with patch("percent.web._require_config") as mock_cfg:
        mock_cfg.return_value.fragments_db_path.exists.return_value = True
        with patch("percent.web.FragmentStore") as MockStore:
            instance = MockStore.return_value
            instance.get_all.return_value = [frag]
            resp = client.get("/api/fragments/wechat")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["fragments"]) == 1
    assert data["fragments"][0]["evidence"] == "user said 'I love coding' at 2am"
