from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AP-Blackjack-Suite-Demo")
    window = MainWindow()

    # Iniciar directamente una ronda en el controlador de mesa
    window.table_controller.deal_round()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
