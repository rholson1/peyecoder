import sys
from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtWidgets import QLabel, QLineEdit, QPushButton, QSlider, QStyle, \
    QHBoxLayout, QVBoxLayout, QSizePolicy, QAction, QGridLayout, QDialog, \
    QRadioButton, QButtonGroup, QDialogButtonBox

from PySide2.QtGui import Qt, QIntValidator, QRegExpValidator
from PySide2.QtCore import QRect, QRegExp

import timecode

import PIL.Image, PIL.ImageTk
import time
import math

from video_reader import BufferedVideoReader
from audio_player import VideoAudioPlayer

STATE_PLAYING = 1
STATE_PAUSED = 2


class SubjectDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('Subject Information')
        # Create widgets

        self.subject_label = QLabel('Subject Number:')
        self.subject_box = QLineEdit()

        self.sex_label = QLabel('Sex:')
        self.male_radio = QRadioButton('Male')
        self.female_radio = QRadioButton('Female')
        self.sex_layout = QHBoxLayout()
        self.sex_layout.addWidget(self.male_radio)
        self.sex_layout.addWidget(self.female_radio)
        # Group radio buttons logically in button group to create one mutually-exclusive set
        self.sex_radiogroup = QButtonGroup()
        self.sex_radiogroup.addButton(self.male_radio)
        self.sex_radiogroup.addButton(self.female_radio)

        date_regexp = QRegExp('^[0-3]?[0-9]/[0-3]?[0-9]/(?:[0-9]{2})?[0-9]{2}$')
        self.date_validator = QRegExpValidator(date_regexp)

        self.dob_label = QLabel('Date of Birth:')
        self.dob_box = QLineEdit()
        self.dob_box.setValidator(self.date_validator)
        self.dob_box.setPlaceholderText('MM/DD/YY')

        self.participation_date_label = QLabel('Participation Date:')
        self.participation_date_box = QLineEdit()
        self.participation_date_box.setValidator(self.date_validator)
        self.participation_date_box.setPlaceholderText('MM/DD/YY')

        self.trial_order_label = QLabel('Trial Order:')
        self.trial_order_box = QLabel('Drag and Drop .csv here (TBD)')

        self.coder_initials_label = QLabel('Coder initials:')
        self.coder_initials_box = QLineEdit()

        self.prescreener_initials_label = QLabel('Prescreener initials:')
        self.prescreener_initials_box = QLineEdit()

        grid = QGridLayout()
        r = 1
        grid.addWidget(self.subject_label, r, 0)
        grid.addWidget(self.subject_box, r, 1)
        r += 1
        grid.addWidget(self.sex_label, r, 0)
        grid.addLayout(self.sex_layout, r, 1)
        r += 1
        grid.addWidget(self.dob_label, r, 0)
        grid.addWidget(self.dob_box, r, 1)
        r += 1
        grid.addWidget(self.participation_date_label, r, 0)
        grid.addWidget(self.participation_date_box, r, 1)
        r += 1
        grid.addWidget(self.trial_order_label, r, 0)
        grid.addWidget(self.trial_order_box, r, 1)
        r += 1
        grid.addWidget(self.coder_initials_label, r, 0)
        grid.addWidget(self.coder_initials_box, r, 1)
        r += 1
        grid.addWidget(self.prescreener_initials_label, r, 0)
        grid.addWidget(self.prescreener_initials_box, r, 1)

        self.setLayout(grid)


class TimecodeDialog(QDialog):
    def __init__(self, parent, framerate_string):
        super().__init__(parent)
        self.framerate_string = framerate_string
        self.timecode = timecode.Timecode(framerate_string)
        self.timecode.drop_frame = False

        self.setWindowTitle('Enter Starting Timecode')

        self.timecode_box = QLineEdit('00:00:00:00')
        self.timecode_box.setInputMask('00:00:00:00')
        self.timecode_box.editingFinished.connect(self.set_timecode)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(self.timecode_box)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

    def set_timecode(self):
        self.timecode = timecode.Timecode(self.framerate_string, self.timecode_box.text())
        self.timecode.drop_frame = False


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
        self.audio = VideoAudioPlayer()

        self.timecode = None  # Timecode object used to translate from frames to SMTP timecode
        self.timecode_offset = 0  # Frame difference between position and displayed timecode

        self.settings = {'Occluders': [QRect(10, 10, 200, 100), QRect(600, 200, 50, 80)]}  # proof of concept occluders

        # Create layouts to place inside widget
        control_layout = self.build_playback_widgets()
        step_layout = self.build_step_widgets()

        layout = QVBoxLayout()
        layout.addWidget(self.image_frame)
        layout.addLayout(control_layout)
        layout.addLayout(step_layout)

        # Create a widget for window contents
        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)
        #wid.keyPressEvent = self.test_keypress_event
        wid.keyReleaseEvent = self.handle_keypress  # works for arrows, unlike keyPressEvent

        wid.setLayout(layout)

        self.build_menu()
        self.open_subject_dialog()

    def build_playback_widgets(self):
        """ Create play button and position slider controls"""
        self.play_button = QPushButton()
        self.play_button.setEnabled(False)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_state)
        self.play_button.setFocusPolicy(Qt.NoFocus)

        self.position_slider = QSlider(QtCore.Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.setPosition)

        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.position_slider)
        return control_layout

    def build_step_widgets(self):
        """ Create controls for stepping through video (prev, next, step size) and timecode display """
        # Widgets for stepping through video
        self.prev_button = QPushButton()
        self.prev_button.setEnabled(False)
        self.prev_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.prev_button.clicked.connect(self.prev_frame)
        self.prev_button.setFocusPolicy(Qt.NoFocus)

        self.next_button = QPushButton()
        self.next_button.setEnabled(False)
        self.next_button.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.next_button.clicked.connect(self.next_frame)
        self.next_button.setFocusPolicy(Qt.NoFocus)

        self.step_label = QLabel('Step')
        self.step_box = QLineEdit(str(self.step))
        self.step_box.setFixedWidth(32)
        step_validator = QIntValidator(1, 99)
        self.step_box.setValidator(step_validator)
        self.step_box.editingFinished.connect(self.update_step)

        # Timecode display
        self.timecode_label = QLabel('00:00:00;00')
        self.timecode_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        monospace_font = QtGui.QFont('nonexistent')
        monospace_font.setStyleHint(QtGui.QFont.TypeWriter)
        self.timecode_label.setFont(monospace_font)

        step_layout = QtWidgets.QHBoxLayout()
        step_layout.addWidget(self.prev_button)
        step_layout.addWidget(self.next_button)
        step_layout.addWidget(self.step_label)
        step_layout.addWidget(self.step_box)
        step_layout.addStretch()
        step_layout.addWidget(self.timecode_label)
        return step_layout

    def build_menu(self):
        """Create the menu bar and global fixed actions"""

        # Create open action
        open_action = QAction(QtGui.QIcon('open.png'), '&Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Open movie')
        open_action.triggered.connect(self.open_file)

        # Create exit action
        exit_action = QAction(QtGui.QIcon('exit.png'), '&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close)

        # Create menu bar and add action
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(open_action)
        file_menu.addAction(exit_action)

    def handle_keypress(self, e):
        if e.key() == Qt.Key_Right:
            self.next_frame()
        elif e.key() == Qt.Key_Left:
            self.prev_frame()
        elif e.key() == Qt.Key_BracketLeft:
            self.prev_step()
        elif e.key() == Qt.Key_BracketRight:
            self.next_step()
        elif e.key() == Qt.Key_Space:
            self.toggle_state()
        elif e.key() == Qt.Key_Plus:
            pass
        elif e.key() == Qt.Key_Minus:
            pass
        elif e.key() == Qt.Key_Enter:
            pass
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            pass
        elif e.key() == self.settings.get('Toggle Trial Status Key', None):
            pass  # Toggle Trial Status
        elif e.key() in self.settings.get('Response Keys', {}):
            pass  # handle reponse keys

    def open_subject_dialog(self):
        self.subject_dialog = SubjectDialog(self)
        self.subject_dialog.show()

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

    def change_frame(self, offset):
        # Change position in video, moving OFFSET frames relative to current position
        if not self.vid:
            return

        if self.state == STATE_PLAYING:
            self.toggle_state()
        if offset > 0:
            self.vid.next(offset)
        elif offset < 0:
            self.vid.prev(-offset)  # note minus sign!
        self.positionChanged(self.vid.frame_number)
        self.show_frame()

    def next_frame(self):
        # Advance to next frame of video
        self.change_frame(1)

    def prev_frame(self):
        # Move to previous frame of video
        self.change_frame(-1)

    def next_step(self):
        # Step forward in video
        self.change_frame(self.step)

    def prev_step(self):
        # Step backward in video
        self.change_frame(-self.step)

    def show_frame(self):
        """ Display the current frame of video"""
        if not self.vid:
            return

        frame = self.vid.frame
        image = PIL.Image.fromarray(frame)

        image = QtGui.QImage(image.tobytes(), image.width, image.height, QtGui.QImage.Format_RGB888)

        # Draw occluders in image
        painter = QtGui.QPainter(image)
        for occluder in self.settings.get('Occluders', []):
            painter.fillRect(occluder, QtCore.Qt.red)
        painter.end()

        # rescale image to fit window, keeping aspect ratio unchanged
        image_scaled = image.scaled(self.image_frame.width(), self.image_frame.height(),
                                    QtCore.Qt.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)

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

        # prompt for starting timecode
        timecode_dialog = TimecodeDialog(self, framerate_string)
        timecode_dialog.exec_()
        self.timecode_offset = timecode_dialog.timecode.frames + 1
        self.update_timecode()

    def open_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Movie") #, QtCore.QDir.homePath())

        if filename != '':
            self.video_source = filename

            self.initialize_video()
            self.audio.set_video_source(self.video_source)
            self.enable_controls()

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
            self.audio.stop()
        else:
            self.play_button.setIcon(
                    self.style().standardIcon(QStyle.SP_MediaPause))
            self.state = STATE_PLAYING
            self.play()
            self.audio.play()

    def update_timecode(self):
        # Update timecode display to match current frame number
        self.timecode.frames = self.vid.frame_number + 1 + self.timecode_offset
        self.timecode_label.setText(str(self.timecode))

    def positionChanged(self, position):
        self.position_slider.setValue(position)
        self.update_timecode()
        self.audio.seek(position)

    def durationChanged(self, duration):
        self.position_slider.setRange(0, duration - 1)

    def setPosition(self, position):
        self.vid.goto_framenumber(position)
        self.update_timecode()
        self.show_frame()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self.show_frame()  # update (and resize) the display of the current frame


if __name__ == "__main__":

    app = QtWidgets.QApplication([])

    widget = MainWindow()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec_())