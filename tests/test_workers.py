from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QObject

from ao3_helper.core.domain import FicDTO
from src.ao3_helper.workers.worker_manager import WorkerManager
from src.ao3_helper.workers.workers import AddFicWorker, BaseImportWorker


@pytest.fixture
def mock_app():
    """Fixture to create a mock application object."""
    app = QObject()
    app.db_path = ":memory:"
    app.session = MagicMock()
    app.config = {"user": {"username": "test_user", "password": "test_password"}}
    return app


@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_worker_manager_initialization(mock_qthread, mock_app):
    """Test that the WorkerManager initializes correctly."""
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    assert worker_manager.parent == mock_app
    assert worker_manager.analysis_engine == mock_analysis_engine


def test_base_import_worker_initialization():
    """Test that the BaseImportWorker initializes correctly."""
    worker = BaseImportWorker(identifier="test_worker")
    assert worker.identifier == "test_worker"


@patch("src.ao3_helper.workers.worker_manager.UpdateCheckWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_update_check(mock_qthread, mock_update_check_worker, mock_app):
    """Test that start_update_check creates a worker and starts a thread."""
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    worker_manager.start_update_check()
    mock_update_check_worker.assert_called_once()
    mock_qthread.assert_called_once()
    worker_manager.update_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.MassImportWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_mass_import(mock_qthread, mock_mass_import_worker, mock_app):
    """Test that start_mass_import creates a worker and starts a thread."""
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    test_url = "test_url"
    worker_manager.start_mass_import(test_url)
    mock_mass_import_worker.assert_called_once_with(test_url)
    mock_qthread.assert_called_once()
    worker_manager.import_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.ao3_client")
@patch("src.ao3_helper.workers.worker_manager.ImportBookmarksWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_bookmarks_import(mock_qthread, mock_bookmarks_worker, mock_ao3_client, mock_app):
    """Test that start_bookmarks_import creates a worker and starts a thread."""
    mock_ao3_client.session = True
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    worker_manager.start_bookmarks_import()
    mock_bookmarks_worker.assert_called_once()
    mock_qthread.assert_called_once()
    worker_manager.bookmarks_import_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.ao3_client")
@patch("src.ao3_helper.workers.worker_manager.ImportHistoryWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_history_import(mock_qthread, mock_history_worker, mock_ao3_client, mock_app):
    """Test that start_history_import creates a worker and starts a thread."""
    mock_ao3_client.session = True
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    worker_manager.start_history_import()
    mock_history_worker.assert_called_once()
    mock_qthread.assert_called_once()
    worker_manager.history_import_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.config_manager")
@patch("src.ao3_helper.workers.worker_manager.SyncStatusWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_status_sync(mock_qthread, mock_sync_status_worker, mock_config_manager, mock_app):
    mock_config_manager.get.return_value = "test_user"
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    test_url = "https://archiveofourown.org/works/12345"
    worker_manager.start_status_sync(test_url)
    mock_sync_status_worker.assert_called_once_with(12345, test_url, "test_user")
    mock_qthread.assert_called_once()
    worker_manager.sync_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.ImportSeriesWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_series_import(mock_qthread, mock_series_worker, mock_app):
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    test_series_id = "12345"
    worker_manager.start_series_import(test_series_id)
    mock_series_worker.assert_called_once_with(test_series_id)
    mock_qthread.assert_called_once()
    worker_manager.series_import_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.ImportCollectionWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_collection_import(mock_qthread, mock_collection_worker, mock_app):
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    test_collection = "test_collection"
    worker_manager.start_collection_import(test_collection)
    mock_collection_worker.assert_called_once_with(test_collection)
    mock_qthread.assert_called_once()
    worker_manager.collection_import_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.get_fics_for_sync")
@patch("src.ao3_helper.workers.worker_manager.config_manager")
@patch("src.ao3_helper.workers.worker_manager.TotalSyncWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_total_sync(mock_qthread, mock_total_sync_worker, mock_config_manager, mock_get_fics, mock_app):
    mock_config_manager.get.return_value = "test_user"
    mock_get_fics.return_value = [{"title": "test_fic"}]
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    with patch("src.ao3_helper.workers.worker_manager.SyncStatusWindow"):
        worker_manager.start_total_sync()
    mock_total_sync_worker.assert_called_once_with([{"title": "test_fic"}])
    mock_qthread.assert_called_once()
    worker_manager.total_sync_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.AddFicWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_single_fic_add(mock_qthread, mock_add_fic_worker, mock_app):
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    test_url = "test_url"
    worker_manager.start_single_fic_add(test_url)
    mock_add_fic_worker.assert_called_once_with(test_url, use_auth_fallback=False)
    mock_qthread.assert_called_once()
    worker_manager.add_fic_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.AuthorRecsWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_author_recs_worker(mock_qthread, mock_author_recs_worker, mock_app):
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    mock_dialog = MagicMock()
    worker_manager.start_author_recs_worker(mock_dialog)
    mock_author_recs_worker.assert_called_once_with(mock_analysis_engine)
    mock_qthread.assert_called_once()
    worker_manager.author_recs_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.worker_manager.DiscoverFicsWorker")
@patch("src.ao3_helper.workers.worker_manager.QThread")
def test_start_discovery_worker(mock_qthread, mock_discover_fics_worker, mock_app):
    mock_analysis_engine = MagicMock()
    worker_manager = WorkerManager(mock_app, mock_analysis_engine)
    search_params = {"test": "params"}
    worker_manager.start_discovery_worker(search_params)
    mock_discover_fics_worker.assert_called_once_with(mock_analysis_engine, search_params)
    mock_qthread.assert_called_once()
    worker_manager.discovery_thread.start.assert_called_once()


@patch("src.ao3_helper.workers.workers.ao3_client")
def test_add_fic_worker_success(mock_ao3_client, qtbot):
    """Test che il worker gestisca correttamente il DTO e emetta un dict."""
    url = "https://ao3.org/works/1"

    mock_dto = FicDTO(
        url=url,
        work_id=1,
        title="Test DTO",
        authors=["Author A"],
        fandoms=["Fandom A"],
        tags=["Tag 1"],
        status="To Read",
    )
    mock_ao3_client.fetch_fic_data.return_value = mock_dto

    with patch("src.ao3_helper.workers.workers.add_fic", return_value=(True, "created")):
        worker = AddFicWorker(url)

        with qtbot.waitSignal(worker.finished) as blocker:
            worker.run()

        result = blocker.args[0]
        assert isinstance(result, dict)
        assert result["title"] == "Test DTO"
        assert result["author"] == "Author A"
