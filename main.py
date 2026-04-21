import sys
import os
import multiprocessing

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    from PySide6.QtWidgets import QApplication
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    multiprocessing.freeze_support()   # Windows spawn 必须加
    main()
