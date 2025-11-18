from unittest.mock import MagicMock, patch

import pytest

from src.ao3_helper.ui.filter_manager import FilterManager


@pytest.fixture
def mock_main_window():
    main_window = MagicMock()

    main_window.library_service = MagicMock()

    main_window.search_input = MagicMock()
    main_window.search_input.text.return_value = ""

    main_window.search_combo = MagicMock()
    main_window.search_combo.currentIndex.return_value = 0

    main_window.status_filter_combo = MagicMock()
    main_window.status_filter_combo.currentIndex.return_value = 0
    main_window.status_filter_combo.currentText.return_value = "All"

    main_window.saved_filters_combo = MagicMock()
    main_window._update_fics_table = MagicMock()
    main_window.library_button = MagicMock()
    main_window.current_view_filter = "all"
    return main_window


def test_load(mock_main_window):
    """Test that load uses the service to get filters."""
    mock_main_window.library_service.get_saved_filters.return_value = [{"name": "Filter 1"}]

    filter_manager = FilterManager(mock_main_window)
    filter_manager.load()

    mock_main_window.library_service.get_saved_filters.assert_called_once()

    assert mock_main_window.saved_filters_combo.addItem.call_count == 2


def test_trigger_search(mock_main_window):
    """Test search trigger via service."""
    mock_main_window.search_input.text.return_value = "test"

    mock_main_window.search_combo.currentIndex.return_value = 1
    mock_main_window.status_filter_combo.currentIndex.return_value = 1

    mock_main_window.library_service.get_all_fics.return_value = []

    filter_manager = FilterManager(mock_main_window)
    filter_manager.trigger_search()

    mock_main_window.library_service.get_all_fics.assert_called_once()


def test_save_current_filter(mock_main_window):
    """Test saving via service."""

    mock_main_window.search_input.text.return_value = "test"
    mock_main_window.search_combo.currentIndex.return_value = 1

    with patch("src.ao3_helper.ui.filter_manager.QInputDialog.getText", return_value=("Name", True)):
        with patch("src.ao3_helper.ui.filter_manager.QMessageBox"):
            filter_manager = FilterManager(mock_main_window)
            with patch.object(filter_manager, "load"):
                filter_manager.save_current_filter()

            mock_main_window.library_service.save_filter.assert_called_once()


def test_apply_advanced_filter(mock_main_window):
    """Test applying advanced filter via service."""
    filters = {"conditions": {"title": "A"}}
    filter_manager = FilterManager(mock_main_window)
    with patch.object(filter_manager, "clear_search"):
        filter_manager.apply_advanced_filter(filters, False)

    mock_main_window.library_service.get_all_fics.assert_called_with(view_filter="all", filters=filters)
