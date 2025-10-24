from PyQt6.QtWidgets import (
    QWidget,
)

from main import MainWindow


# La fixture 'qtbot' viene iniettata automaticamente da pytest-qt
def test_main_window_smoke_test(qtbot, db_connection):
    """
    Test di base ("smoke test") per verificare che la finestra principale
    si avvii senza errori e contenga i widget essenziali.
    """
    # Crea la finestra in un ambiente di test
    window = MainWindow()
    qtbot.addWidget(window)  # Registra il widget per la pulizia automatica
    window.show()
    # Verifica che la finestra sia visibile
    assert window.isVisible()

    # Verifica l'esistenza di alcuni widget critici
    assert window.fics_table is not None
    assert window.url_input is not None
    assert window.add_button is not None
    assert window.search_input is not None
    assert window.detail_title is not None

    # Verifica che il pannello dei dettagli sia inizialmente nascosto
    right_widget = window.findChild(QWidget, "right_widget")
    assert right_widget is not None
    assert not right_widget.isVisible()
