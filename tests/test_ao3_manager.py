
from unittest.mock import MagicMock, patch

import constants as const

from ao3_manager import AO3Client



@patch("ao3_manager.security_manager")
@patch("ao3_manager.AO3.Session")
def test_ao3_client_initialization_success(mock_ao3_session, mock_security_manager):
    """
    Verifica che AO3Client si inizializzi correttamente quando vengono fornite
    credenziali valide, simulando un login di successo.
    """
    with patch("ao3_manager.config_manager") as mock_config:
        mock_config.get.return_value = "test_user"

        mock_security_manager.get_password.return_value = "test_pass"

        client = AO3Client()

        mock_ao3_session.assert_called_once_with("test_user", "test_pass")
        assert client.session is not None


@patch("ao3_manager.AO3.Session")
def test_ao3_client_initialization_guest_mode(mock_ao3_session):
    """
    Verifica che AO3Client proceda come guest se le credenziali non sono configurate.
    """
    with patch("ao3_manager.config_manager") as mock_config:
        mock_config.get.return_value = const.CONFIG_DEFAULT_USER

        client = AO3Client()

        mock_ao3_session.assert_not_called()
        assert client.session is None


def test_fetch_fic_data_processes_work_correctly():
    """
    Verifica che fetch_fic_data prenda un oggetto 'Work' simulato e lo processi
    correttamente in un dizionario. Questo è il test più importante.
    """
    mock_work = MagicMock()
    mock_work.url = "https://archiveofourown.org/works/123"
    mock_work.title = "Mock Fic Title"
    mock_author = MagicMock()
    mock_author.username = "MockAuthor"
    mock_work.authors = [mock_author]
    mock_work.summary = "A summary."
    mock_work.rating = ["General Audiences"]
    mock_work.fandoms = ["Test Fandom"]
    mock_work.tags = ["Tag1", "Tag2"]
    mock_work.words = 5000
    mock_work.categories = ["M/M"]
    mock_work.relationships = ["Char A/Char B"]
    mock_work.characters = ["Char A", "Char B"]
    mock_work.nchapters = 10
    mock_work.expected_chapters = 10  # Per simulare una fic completa

    with patch("ao3_manager.AO3") as mock_ao3_lib:
        mock_ao3_lib.Work.return_value = mock_work

        client = AO3Client()
        client.session = None

        result = client.fetch_fic_data("https://archiveofourown.org/works/123")

        assert result is not None
        assert result["title"] == "Mock Fic Title"
        assert result["author"] == "MockAuthor"
        assert result["fandoms"] == "Test Fandom"
        assert result["rating"] == "General Audiences"
        assert result["word_count"] == 5000
        assert result["is_complete"] is True

        mock_ao3_lib.Work.assert_called_once_with(123, session=None)
        mock_work.reload.assert_called_once()
