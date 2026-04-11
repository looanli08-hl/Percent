from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from percent.persona.spectrum import CardData, SpectrumResult
from percent.web import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_spectrum_returns_eligible_card(client):
    card = CardData(
        spectrum=SpectrumResult(
            dimensions={"夜行性": 85, "回复惯性": 72},
            metrics={"fragment_count": 60, "source_count": 2, "sources": ["wechat", "bilibili"], "data_span_days": 30},
            eligible=True,
        ),
        label="深夜哲学家",
        description="凌晨三点的你比白天更诚实",
        insights=["你的已读不回率 87%", "凌晨活跃度是白天的 3.2 倍", "你在 B站和微信上判若两人"],
    )

    with patch("percent.web._require_config") as mock_cfg:
        mock_cfg.return_value.fragments_db_path.exists.return_value = True
        mock_cfg.return_value.llm_provider = "deepseek"
        mock_cfg.return_value.llm_model = "deepseek-chat"
        mock_cfg.return_value.llm_api_key = "test"
        with patch("percent.web.FragmentStore") as MockStore:
            MockStore.return_value.get_all.return_value = []
            MockStore.return_value.close = MagicMock()
            with patch("percent.web.generate_card_data", return_value=card):
                resp = client.get("/api/spectrum")

    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is True
    assert data["label"] == "深夜哲学家"
    assert len(data["insights"]) == 3
    assert "夜行性" in data["dimensions"]


def test_spectrum_returns_ineligible(client):
    card = CardData(
        spectrum=SpectrumResult(eligible=False, ineligible_reason="数据不足"),
    )

    with patch("percent.web._require_config") as mock_cfg:
        mock_cfg.return_value.fragments_db_path.exists.return_value = True
        mock_cfg.return_value.llm_provider = "deepseek"
        mock_cfg.return_value.llm_model = "deepseek-chat"
        mock_cfg.return_value.llm_api_key = "test"
        with patch("percent.web.FragmentStore") as MockStore:
            MockStore.return_value.get_all.return_value = []
            MockStore.return_value.close = MagicMock()
            with patch("percent.web.generate_card_data", return_value=card):
                resp = client.get("/api/spectrum")

    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is False


def test_spectrum_no_db(client):
    with patch("percent.web._require_config") as mock_cfg:
        mock_cfg.return_value.fragments_db_path.exists.return_value = False
        resp = client.get("/api/spectrum")

    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is False
