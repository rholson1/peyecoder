import sys
from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtWidgets import QLabel, QLineEdit, QPushButton, QSlider, QStyle, \
    QHBoxLayout, QVBoxLayout, QSizePolicy, QAction

from PySide2.QtGui import QIntValidator

import timecode

import PIL.Image, PIL.ImageTk
import time
import math

from video_reader import BufferedVideoReader

STATE_PLAYING = 1
STATE_PAUSED = 2


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.step = 1  # initial value for step
        self.frame_delay = 0  # ms delay between frames when playing video (or maybe use framerate)
        self.state = STATE_PAUSED

        self.image_frame = QLabel()
        self.image_frame.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # open video source
        self.video_source = ''  # r'm:\work\iCoder\sample_data\CueCue_108.mov'
        self.vid = None  # BufferedVideoReader(self.video_source)

        self.timecode = None  # Timecode object used to translate from frames to SMTP timecode

        # Widgets for video playback
        self.play_button = QPushButton()
        self.play_button.setEnabled(False)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_state)

        self.position_slider = QSlider(QtCore.Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.setPosition)

        # Widgets for stepping through video
        self.prev_button = QPushButton()
        self.prev_button.setEnabled(False)
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_button.clicked.connect(self.prev_frame)
        
        self.next_button = QPushButton()
        self.next_button.setEnabled(False)
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_button.clicked.connect(self.next_frame)

        self.step_label = QLabel('Step')
        self.step_box = QLineEdit(str(self.step))
        self.step_box.setFixedWidth(20)
        step_validator = QIntValidator(1, 99)
        self.step_box.setValidator(step_validator)
        self.step_box.editingFinished.connect(self.update_step)
        self.timecode_label = QLabel('00:00:00;00')
        self.timecode_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        step_layout = QtWidgets.QHBoxLayout()
        step_layout.addWidget(self.prev_button)
        step_layout.addWidget(self.next_button)
        step_layout.addWidget(self.step_label)
        step_layout.addWidget(self.step_box)
        step_layout.addStretch()
        step_layout.addWidget(self.timecode_label)

        # Create a widget for window contents
        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)
        #wid.keyPressEvent = self.test_keypress_event
        wid.keyReleaseEvent = self.test_keypress_event  # works for arrows, unlike keyPressEvent


        # Create layouts to place inside widget
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.position_slider)


        self.errorLabel = QLabel()
        self.errorLabel.setSizePolicy(QSizePolicy.Preferred,
                QSizePolicy.Maximum)

        layout = QVBoxLayout()
        layout.addWidget(self.image_frame)
        layout.addLayout(control_layout)
        layout.addLayout(step_layout)
        layout.addWidget(self.errorLabel)

        # Set widget to contain window contents
        wid.setLayout(layout)

        # Create open action
        open_action = QAction(QtGui.QIcon('open.png'), '&Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Open movie')
        open_action.triggered.connect(self.open_file)

        # Create exit action
        exit_action = QAction(QtGui.QIcon('exit.png'), '&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.exitCall)

        # Create menu bar and add action
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(open_action)
        file_menu.addAction(exit_action)

    def test_keypress_event(self, e):
        #if e.key == QtGui.QKeySequence.MoveToNextChar:
        if e.key() == QtGui.Qt.Key_Right:
            print('Right Arrow')
        print(e.key())

    def enable_controls(self):
        self.play_button.setEnabled(True)
        self.next_button.setEnabled(True)
        self.prev_button.setEnabled(True)

    def update_step(self):
        # Update self.step based on new value of step text box
        text = self.step_box.text()
        try:
            new_step = int(text)
        except ValueError:
            new_step = 1
        self.step_box.setText(str(new_step))
        self.step = new_step
        
    def next_frame(self):
        # Advance to next frame of video
        if self.state == STATE_PLAYING:
            self.toggle_state()
        self.vid.next(self.step)
        self.positionChanged(self.vid.frame_number)
        self.show_frame()
    
    def prev_frame(self):
        # Move to previous frame of video
        if self.state == STATE_PLAYING:
            self.toggle_state()
        self.vid.prev(self.step)
        self.positionChanged(self.vid.frame_number)
        self.show_frame()

    def show_frame(self):
        """ Display the current frame of video"""
        if not self.vid:
            return

        frame = self.vid.frame
        image = PIL.Image.fromarray(frame)
        image = QtGui.QImage(image.tobytes(), image.width, image.height, QtGui.QImage.Format_RGB888)

        # rescale image to fit window, keeping aspect ratio unchanged
        image_scaled = image.scaled(self.image_frame.width(), self.image_frame.height(), QtCore.Qt.KeepAspectRatio)
        self.image_frame.setPixmap(QtGui.QPixmap.fromImage(image_scaled))
        self.image_frame.repaint()

    def initialize_video(self):
        # Actions to perform when a new video has been loaded
        self.vid = BufferedVideoReader(self.video_source)

        # Create timecode object
        framerate_string = '{:.2f}'.format(self.vid.frame_rate).replace('.00', '')
        self.timecode = timecode.Timecode(framerate_string)
        self.timecode.drop_frame = False

        # Update slider control
        self.durationChanged(self.vid.frame_count)
        self.positionChanged(0)

        # Update playback speed
        if self.vid.frame_rate > 0:
            self.frame_delay = 1000 / self.vid.frame_rate
        else:
            self.frame_delay = 33.3  # fallback to assumed 30 fps

        self.show_frame()

    def open_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Movie") #,
                #QtCore.QDir.homePath())

        if filename != '':
            print(filename)
            self.video_source = filename

            self.initialize_video()
            self.enable_controls()

    def exitCall(self):
        sys.exit(app.exec_())

    def play(self):
        t0 = time.perf_counter()
        self.vid.next()
        self.positionChanged(self.vid.frame_number)
        self.show_frame()
        if self.state == STATE_PLAYING:
            delay = self.frame_delay - (time.perf_counter() - t0) * 1000
            QtCore.QTimer.singleShot(max(math.floor(delay), 0), self.play)

    def toggle_state(self):
        if self.state == STATE_PLAYING:
            self.play_button.setIcon(
                    self.style().standardIcon(QStyle.SP_MediaPlay))
            self.state = STATE_PAUSED
        else:
            self.play_button.setIcon(
                    self.style().standardIcon(QStyle.SP_MediaPause))
            self.state = STATE_PLAYING
            self.play()

    def update_timecode(self):
        # Update timecode display to match current frame number
        self.timecode.frames = self.vid.frame_number + 1
        self.timecode_label.setText(str(self.timecode))

    def positionChanged(self, position):
        self.position_slider.setValue(position)
        self.update_timecode()

    def durationChanged(self, duration):
        self.position_slider.setRange(0, duration - 1)

    def setPosition(self, position):
        self.vid.goto_framenumber(position)
        self.update_timecode()
        self.show_frame()

    def handleError(self):
        self.play_button.setEnabled(False)
        self.errorLabel.setText("Error: " + self.mediaPlayer.errorString())

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self.show_frame()  # update (and resize) the display of the current frame


if __name__ == "__main__":

    app = QtWidgets.QApplication([])

    widget = MainWindow()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec_())