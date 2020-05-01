from PySide2 import QtCore, QtWidgets, QtGui
import datetime
import sys


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.press = QtWidgets.QLabel('')
        self.release = QtWidgets.QLabel('')
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.press)
        layout.addWidget(self.release)

        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)
        wid.setLayout(layout)

    def keyPressEvent(self, e:QtGui.QKeyEvent):
        super().keyPressEvent(e)
        self.press.setText('\n'.join(['press {} at {}'.format(e.key(), datetime.datetime.now().timestamp()), *self.press.text().split('\n')[:10]]))

    def keyReleaseEvent(self, e: QtGui.QKeyEvent):
        super().keyReleaseEvent(e)
        self.release.setText('\n'.join(['release {} at {}'.format(e.key(), datetime.datetime.now().timestamp()), *self.release.text().split('\n')[:10]]))

if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    widget = MainWindow()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec_())