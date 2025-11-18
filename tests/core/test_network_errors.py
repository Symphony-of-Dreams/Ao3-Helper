from unittest.mock import MagicMock, patch

import AO3

from ao3_helper.core.ao3_manager import AO3Client


@patch("time.sleep")
@patch("ao3_helper.core.ao3_manager.AO3.Work")
def test_fetch_fic_data_handles_429_retry(mock_work_cls, mock_sleep):
    """
    Verifica che fetch_fic_data (che ha il decoratore @retry) gestisca
    correttamente un errore 429 (Rate Limit) riprovando l'operazione.
    """

    mock_work_instance = MagicMock()

    mock_work_instance.title = "Resilient Fic"
    mock_work_instance.authors = [MagicMock(username="TestAuthor")]
    mock_work_instance.nchapters = 1
    mock_work_instance.expected_chapters = 1
    mock_work_instance.fandoms = ["Fandom A"]
    mock_work_instance.tags = []
    mock_work_instance.categories = []
    mock_work_instance.relationships = []
    mock_work_instance.characters = []
    mock_work_instance.series = []
    mock_work_instance.language = "en"
    mock_work_instance.words = 1000
    mock_work_instance.hits = 100
    mock_work_instance.kudos = 10
    mock_work_instance.bookmarks = 5
    mock_work_instance.comments = 0
    mock_work_instance.date_published = None
    mock_work_instance.date_updated = None
    mock_work_instance.rating = "General"
    mock_work_instance.url = "https://archiveofourown.org/works/123"

    mock_work_cls.return_value = mock_work_instance

    mock_fail_response = MagicMock()
    mock_fail_response.status_code = 429

    error_429 = AO3.utils.HTTPError("HTTP 429 Rate limited")
    error_429.response = mock_fail_response

    mock_work_instance.reload.side_effect = [error_429, None]

    with patch("ao3_helper.core.ao3_manager.AO3Client._create_session", return_value=None):
        client = AO3Client()
    client.session = None

    result = client.fetch_fic_data("https://archiveofourown.org/works/123")

    assert result is not None

    assert result.title == "Resilient Fic"

    assert mock_work_instance.reload.call_count == 2

    assert mock_sleep.called
