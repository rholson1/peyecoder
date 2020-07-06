import sys
from PySide2 import QtWidgets
from peyecoder.gui import MainWindow

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    widget = MainWindow()
    widget.resize(800, 600)
    widget.show()
    sys.exit(app.exec_())
