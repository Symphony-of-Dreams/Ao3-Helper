from unittest.mock import MagicMock, patch

from ao3_helper import constants as const
from ao3_helper.core.ao3_manager import AO3Client
from ao3_helper.core.domain import FicDTO


@patch("ao3_helper.core.ao3_manager.security_manager")
@patch("ao3_helper.core.ao3_manager.AO3.Session")
def test_ao3_client_initialization_success(mock_ao3_session, mock_security_manager):
    """
    Verifica che AO3Client si inizializzi correttamente quando vengono fornite
    credenziali valide, simulando un login di successo.
    """
    with patch("ao3_helper.core.ao3_manager.config_manager") as mock_config:
        mock_config.get.return_value = "test_user"

        mock_security_manager.get_password.return_value = "test_pass"

        client = AO3Client()

        mock_ao3_session.assert_called_once_with("test_user", "test_pass")
        assert client.session is not None


@patch("ao3_helper.core.ao3_manager.AO3.Session")
def test_ao3_client_initialization_guest_mode(mock_ao3_session):
    """
    Verifica che AO3Client proceda come guest se le credenziali non sono configurate.
    """
    with patch("ao3_helper.core.ao3_manager.config_manager") as mock_config:
        mock_config.get.return_value = const.CONFIG_DEFAULT_USER

        client = AO3Client()

        mock_ao3_session.assert_not_called()
        assert client.session is None


def test_fetch_fic_data_returns_dto():
    """
    Verifica che fetch_fic_data restituisca un oggetto FicDTO popolato.
    """
    mock_work = MagicMock()
    mock_work.url = "https://archiveofourown.org/works/123"
    mock_work.title = "DTO Test Fic"
    mock_work.workid = 123

    mock_author = MagicMock()
    mock_author.username = "MockAuthor"
    mock_work.authors = [mock_author]

    mock_work.summary = "Summary"
    mock_work.rating = ["General"]
    mock_work.fandoms = ["Fandom A"]
    mock_work.tags = ["Tag1"]
    mock_work.words = 100
    mock_work.categories = ["Gen"]
    mock_work.relationships = []
    mock_work.characters = []
    mock_work.nchapters = 1
    mock_work.expected_chapters = 1
    mock_work.series = []
    mock_work.date_published = None
    mock_work.date_updated = None
    mock_work.language = "en"
    mock_work.hits = 10
    mock_work.kudos = 5
    mock_work.bookmarks = 1
    mock_work.comments = 0

    with patch("ao3_helper.core.ao3_manager.AO3.Work", return_value=mock_work):
        client = AO3Client()
        client.session = None

        result = client.fetch_fic_data("https://archiveofourown.org/works/123")

        assert isinstance(result, FicDTO)
        assert result.title == "DTO Test Fic"
        assert result.authors == ["MockAuthor"]
        assert result.word_count == 100
        assert result.is_complete is True
