import pytest
from PyQt6.QtWidgets import QLabel

from ao3_helper.ui.dialogs.achievements_window import AchievementsWindow

SAMPLE_ACHIEVEMENTS = {
    "fic_reader_1": {"name": "Fic Reader I", "description": "Read 1 fic", "icon": "📖"},
    "fic_reader_2": {"name": "Fic Reader II", "description": "Read 10 fics", "icon": "📚"},
    "kudos_giver_1": {"name": "Kudos Giver I", "description": "Give 1 kudos", "icon": "👍"},
}


@pytest.fixture
def mock_dependencies(mocker):
    """Mocks external dependencies for AchievementsWindow."""
    mock_get_unlocked = mocker.patch("ao3_helper.ui.dialogs.achievements_window.get_unlocked_achievements")
    mocker.patch("ao3_helper.ui.dialogs.achievements_window.ACHIEVEMENTS", SAMPLE_ACHIEVEMENTS)
    return mock_get_unlocked


@pytest.fixture
def dialog(qtbot, mock_dependencies):
    """Creates an AchievementsWindow instance."""
    mock_get_unlocked = mock_dependencies
    mock_get_unlocked.return_value = {}
    dialog = AchievementsWindow()
    qtbot.addWidget(dialog)
    return dialog


def test_init_no_unlocked_achievements(dialog, mock_dependencies, qtbot):
    """Test initialization when no achievements are unlocked."""
    mock_get_unlocked = mock_dependencies
    mock_get_unlocked.return_value = {}

    dialog = AchievementsWindow()
    qtbot.addWidget(dialog)

    for i in range(dialog.grid_layout.count()):
        widget = dialog.grid_layout.itemAt(i).widget()
        assert not widget.isEnabled()
        name_label = widget.findChild(QLabel, "name_label")
        icon_label = widget.findChild(QLabel, "icon_label")
        assert name_label.text() == "???"
        assert icon_label.text() == "🔒"


def test_init_with_unlocked_achievements(dialog, mock_dependencies, qtbot):
    """Test initialization with some achievements unlocked."""
    mock_get_unlocked = mock_dependencies
    mock_get_unlocked.return_value = {"fic_reader_1": "2025-01-01"}

    dialog = AchievementsWindow()
    qtbot.addWidget(dialog)

    fic_reader_1_widget = None
    for i in range(dialog.grid_layout.count()):
        widget = dialog.grid_layout.itemAt(i).widget()
        name_label = widget.findChild(QLabel, "name_label")
        if name_label and name_label.text() == "<b>Fic Reader I</b>":
            fic_reader_1_widget = widget
            break

    assert fic_reader_1_widget is not None
    assert fic_reader_1_widget.isEnabled()
    assert fic_reader_1_widget.findChild(QLabel, "name_label").text() == "<b>Fic Reader I</b>"
    assert fic_reader_1_widget.findChild(QLabel, "icon_label").text() == "📖"
    assert fic_reader_1_widget.findChild(QLabel, "date_label").text() == "<i>2025-01-01</i>"

    fic_reader_2_widget = None
    for i in range(dialog.grid_layout.count()):
        widget = dialog.grid_layout.itemAt(i).widget()
        name_label = widget.findChild(QLabel, "name_label")
        if name_label and name_label.text() == "???":
            fic_reader_2_widget = widget
            break

    assert fic_reader_2_widget is not None
    assert not fic_reader_2_widget.isEnabled()
    assert fic_reader_2_widget.findChild(QLabel, "name_label").text() == "???"
    assert fic_reader_2_widget.findChild(QLabel, "icon_label").text() == "🔒"


def test_create_badge_widget_unlocked(qtbot):
    """Test _create_badge_widget for an unlocked achievement."""
    info = SAMPLE_ACHIEVEMENTS["fic_reader_1"]
    widget = AchievementsWindow(parent=None)._create_badge_widget(info, True, "2025-01-01")
    qtbot.addWidget(widget)

    assert widget.isEnabled()
    assert widget.findChild(QLabel, "name_label").text() == "<b>Fic Reader I</b>"
    assert widget.findChild(QLabel, "icon_label").text() == "📖"
    assert widget.findChild(QLabel, "date_label").text() == "<i>2025-01-01</i>"
    assert "Fic Reader I" in widget.toolTip()


def test_create_badge_widget_locked(qtbot):
    """Test _create_badge_widget for a locked achievement."""
    info = SAMPLE_ACHIEVEMENTS["fic_reader_2"]
    widget = AchievementsWindow(parent=None)._create_badge_widget(info, False, None)
    qtbot.addWidget(widget)

    assert not widget.isEnabled()
    assert widget.findChild(QLabel, "name_label").text() == "???"
    assert widget.findChild(QLabel, "icon_label").text() == "🔒"
    assert widget.findChild(QLabel, "date_label").text() == ""
    assert "Fic Reader II" in widget.toolTip()
