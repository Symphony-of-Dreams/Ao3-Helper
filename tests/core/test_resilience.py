from unittest.mock import MagicMock, patch

import pytest

from ao3_helper.core.ao3_manager import AO3Client


@pytest.fixture
def mock_work_obj():
    w = MagicMock()
    w.title = "Test Fic"
    w.authors = [MagicMock(username="Author")]
    w.nchapters = 1
    w.expected_chapters = 1
    w.date_published = None
    w.date_updated = None
    w.rating = None
    w.fandoms = []
    w.tags = []
    w.categories = []
    w.relationships = []
    w.characters = []
    w.series = []
    w.language = "English"
    w.hits = None
    w.kudos = 0
    w.bookmarks = 0
    w.comments = 0
    w.words = 1000
    w.url = "http://example.com/works/123"
    return w


@patch("ao3_helper.core.ao3_manager.AO3.Work")
def test_fetch_data_resilience_missing_fields(mock_ao3_work_cls, mock_work_obj):
    mock_instance = mock_work_obj
    mock_ao3_work_cls.return_value = mock_instance

    client = AO3Client()
    client.session = None

    data = client.fetch_fic_data("http://example.com/works/123")

    assert data is not None
    assert data.rating == ""
    assert data.fandoms == []
    assert data.hits == 0

    if not isinstance(data, dict):

        assert data.rating == "" or data.rating is None

        assert data.fandoms == []
        assert data.hits == 0
    else:

        assert data["rating"] == "" or data["rating"] is None
        assert data["fandoms"] == "" or data["fandoms"] == []
        assert data["hits"] == 0


@patch("ao3_helper.core.ao3_manager.AO3.Work")
def test_fetch_data_deleted_work(mock_ao3_work_cls):
    mock_instance = MagicMock()
    mock_instance.title = None
    mock_ao3_work_cls.return_value = mock_instance

    client = AO3Client()
    client.session = None

    data = client.fetch_fic_data("http://example.com/works/deleted")

    assert data is None
