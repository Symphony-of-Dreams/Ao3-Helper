from PyQt6.QtWidgets import (
    QWidget,
)

from main_window import MainWindow


def test_main_window_smoke_test(qtbot, db_connection):
    """
    Test di base ("smoke test") per verificare che la finestra principale
    si avvii senza errori e contenga i widget essenziali.
    """

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()

    assert window.fics_table is not None
    assert window.url_input is not None
    assert window.add_button is not None
    assert window.search_input is not None
    assert window.detail_title is not None

    right_widget = window.findChild(QWidget, "right_widget")
    assert right_widget is not None
    assert not right_widget.isVisible()
