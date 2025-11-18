import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QWidget
from src.ao3_helper.ui.ui_components import TagCompleter, NumericTableWidgetItem

@pytest.fixture
def mock_completer():
    completer = TagCompleter()
    widget = QWidget()
    widget.text = MagicMock()
    completer.setWidget(widget)
    return completer

@patch("PyQt6.QtWidgets.QCompleter.pathFromIndex")
def test_tag_completer_path_from_index(mock_path_from_index, mock_completer):
    """Test that TagCompleter pathFromIndex works correctly."""
    mock_completer.widget().text.return_value = "tag1, tag2"
    mock_path_from_index.return_value = "tag3"
    assert mock_completer.pathFromIndex(MagicMock()) == "tag1, tag3"

def test_tag_completer_split_path(mock_completer):
    """Test that TagCompleter splitPath works correctly."""
    assert mock_completer.splitPath("tag1, tag2, t") == ["t"]
    assert mock_completer.splitPath("tag1") == ["tag1"]

def test_numeric_table_widget_item_lt():
    """Test that NumericTableWidgetItem __lt__ works correctly."""
    item1 = NumericTableWidgetItem("10")
    item2 = NumericTableWidgetItem("2")
    item3 = NumericTableWidgetItem("abc")
    assert (item1 < item2) is False
    assert (item2 < item1) is True
    assert (item1 < item3) is True

