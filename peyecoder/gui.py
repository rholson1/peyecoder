import sys
import time
import math

from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtWidgets import QLabel, QPushButton, QSlider, QStyle, \
    QHBoxLayout, QVBoxLayout, QSizePolicy, QAction, QGridLayout, QDialog, \
    QTabWidget, QSplitter
from PySide2.QtGui import Qt
from PySide2.QtCore import QObject, QEvent

import timecode
import os

from peyecoder.video_reader import BufferedVideoReader
from peyecoder.audio_player import VideoAudioPlayer
from peyecoder.panels import Prescreen, Code, LogTable
from peyecoder.models import Subject
from peyecoder.file_utils import load_datafile, save_datafile
from peyecoder.dialogs import SubjectDialog, TimecodeDialog, OccluderDialog, SettingsDialog, CodeComparisonDialog, \
    ReportDialog, ExportDialog, get_save_filename
from peyecoder.reliability import reliability_report

STATE_PLAYING = 1
STATE_PAUSED = 2

TAB_PRESCREEN = 0
TAB_CODE = 1


class MainEventFilter(QObject):
    def eventFilter(self, obj, event):
        # if event.type() == QEvent.KeyPress:
        #     print('key pressed: {}, obj={}'.format(event.key(), obj))

        if event.type() == QEvent.MouseButtonPress:
            if obj != LogTable:
                self.parent().logtable.clearSelection()

        return QObject.eventFilter(self, obj, event)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()

        self.setFocusPolicy(Qt.ClickFocus)

        self.frame_delay = 0  # ms delay between frames when playing video (or maybe use framerate)
        self.state = STATE_PAUSED

        self.image_frame = QLabel()
        self.image_frame.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.occluder_dialog = None
        self.subject_dialog = None
        self.settings_dialog = None
        self.code_comparison_dialog = None
        self.report_dialog = None

        self.subject = Subject()

        # Timecode object used to translate from frames to SMTP timecode
        # Initialize with default framerate; will be updated when a video is loaded
        self.timecode = timecode.Timecode('29.97')
        self.timecode.drop_frame = False

        # Create layouts to place inside widget
        control_layout = self.build_playback_widgets()
        step_layout = self.build_step_widgets()
        tab_widget = self.build_tabs()
        table_widget = self.build_table()
        info_grid = self.build_info_panel()

        self.message_box = QLabel()
        self.message_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.message_box.setStyleSheet('color: red;')

        layout = QVBoxLayout()
        layout.addWidget(self.image_frame)
        layout.addLayout(control_layout)
        layout.addLayout(step_layout)
        # Enclose the layout in a widget because children of QSplitter must be widgets, not layouts.
        container = QtWidgets.QWidget()
        container.setLayout(layout)

        splitter = QSplitter()
        splitter.addWidget(container)
        splitter.addWidget(table_widget)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.splitterMoved.connect(self.splitter_moved)

        layout3 = QVBoxLayout()
        layout3.addWidget(splitter)
        layout3.addWidget(tab_widget)
        layout3.addLayout(info_grid)
        layout3.addWidget(self.message_box)

        # Create a widget for window contents
        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)
        # wid.keyPressEvent = self.test_keypress_event
        # wid.keyReleaseEvent = self.handle_keypress  # works for arrows, unlike keyPressEvent

        wid.setLayout(layout3)

        # Use event filter to cause mouse clicks away from the log table to
        # clear the selection (removes focus to fix key handling)
        eventfilter = MainEventFilter(self)
        self.installEventFilter(eventfilter)

        self.build_menu()

        self.reset_state()

    def reset_state(self):
        """Initialize state or reset to initial state"""
        self.subject = Subject()
        self.filename = ''
        self.setWindowTitle('peyecoder')
        # reset video source
        self.video_source = ''
        self.vid = None
        if hasattr(self, 'audio'):
            del self.audio
        self.audio = VideoAudioPlayer()
        self.audio_muted = False
        self.image_frame.clear()

        # reset dialogs
        if self.occluder_dialog:
            self.occluder_dialog.close()
        if self.subject_dialog:
            self.subject_dialog.close()
        if self.settings_dialog:
            self.settings_dialog.close()
        if self.code_comparison_dialog:
            self.code_comparison_dialog.close()
        self.occluder_dialog = None
        self.subject_dialog = None
        self.settings_dialog = None
        self.code_comparison_dialog = None

        self.update_log()
        self.reset_info_panel()

        self.open_subject_dialog()

    def build_playback_widgets(self):
        """ Create play button and position slider controls"""
        self.play_button = QPushButton()
        self.play_button.setEnabled(False)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_state)
        self.play_button.setFocusPolicy(Qt.NoFocus)

        self.mute_button = QPushButton()
        self.mute_button.setIcon(self.style().standardIcon(QStyle.SP_MediaVolume))
        self.mute_button.clicked.connect(self.toggle_mute)
        self.mute_button.setFocusPolicy(Qt.NoFocus)

        self.position_slider = QSlider(QtCore.Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.setPosition)
        self.position_slider.setFocusPolicy(Qt.NoFocus)

        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.mute_button)
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

        self.step_label = QLabel('Step: {}'.format(self.subject.settings['Step']))

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
        step_layout.addStretch()
        step_layout.addWidget(self.timecode_label)
        return step_layout

    def build_info_panel(self):
        # build information display widgets for the bottom of the screen
        # info panel at bottom of screen
        subject_number_label = QLabel('Subject Number :')
        subject_number_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.subject_number_box = QLabel('')
        self.subject_number_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        order_label = QLabel('Trial Order :')
        order_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.order_label_box = QLabel('')
        self.order_label_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        unused_label = QLabel('Unused Trials :')
        unused_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.unused_box = QLabel('')
        self.unused_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        prescreened_label = QLabel('Prescreened out :')
        prescreened_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.prescreened_box = QLabel('')
        self.prescreened_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        info_grid = QGridLayout()
        info_grid.addWidget(subject_number_label, 0, 0, alignment=Qt.AlignRight)
        info_grid.addWidget(self.subject_number_box, 0, 1, alignment=Qt.AlignLeft)
        info_grid.addWidget(order_label, 0, 3, alignment=Qt.AlignRight)
        info_grid.addWidget(self.order_label_box, 0, 4, alignment=Qt.AlignLeft)
        info_grid.addWidget(unused_label, 1, 0, alignment=Qt.AlignRight)
        info_grid.addWidget(self.unused_box, 1, 1, alignment=Qt.AlignLeft)
        info_grid.addWidget(prescreened_label, 1, 3, alignment=Qt.AlignRight)
        info_grid.addWidget(self.prescreened_box, 1, 4, alignment=Qt.AlignLeft)
        info_grid.setColumnStretch(1, 2)
        info_grid.setColumnMinimumWidth(0, 160)
        info_grid.setColumnMinimumWidth(4, 200)
        return info_grid

    def build_table(self):
        self.logtable = LogTable()
        self.logtable.setColumnCount(3)
        self.logtable.setAlternatingRowColors(True)
        self.logtable.setHorizontalHeaderLabels(self.logtable.Labels.Prescreen1)

        self.logtable.setMinimumWidth(400)
        self.logtable.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.logtable.itemSelectionChanged.connect(self.select_code_row)

        return self.logtable

    def build_tabs(self):
        """Create tab control which contains prescreen and code tabs"""
        self.tab_widget = QTabWidget()
        self.prescreen_tab = Prescreen(self.add_reason)
        self.prescreen_tab.group_who.buttonClicked.connect(self.update_log)
        self.prescreen_tab.both_checkbox.stateChanged.connect(self.update_log)
        self.code_tab = Code(self.add_event)
        self.code_tab.set_responses(list(self.subject.settings['Response Keys'].values()))
        self.tab_widget.addTab(self.prescreen_tab, 'Prescreen')
        self.tab_widget.addTab(self.code_tab, 'Code')
        self.tab_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.tab_widget.currentChanged.connect(self.change_tab)
        self.tab_widget.setFocusPolicy(Qt.NoFocus)

        self.active_tab = TAB_PRESCREEN

        return self.tab_widget

    def change_tab(self, index):
        self.active_tab = index
        self.update_log()

    def update_log(self):
        """Update data and labels in log file"""
        if self.active_tab == TAB_PRESCREEN:
            self.logtable.set_prescreen_labels(self.prescreen_tab.prescreener())
            self.logtable.load_data(self.subject.reasons.render(self.prescreen_tab.prescreener()))
        elif self.active_tab == TAB_CODE:
            self.logtable.set_code_labels()
            self.logtable.load_data(self.subject.events.render(self.subject.timecode_offsets, self.timecode))

            errors, err_msg = self.subject.events.error_items(self.subject.trial_order.unused + self.subject.reasons.unused())
            self.logtable.redden_rows(errors)
            self.message_box.setText('\n'.join(err_msg))

    def select_code_row(self):
        """ When a row or rows have been selected in the code log, update the code tab widgets and the video position
        to correspond to the first selected row.
        """
        if self.active_tab == TAB_CODE:
            rows = self.logtable.selected_rows()
            if rows:
                row = sorted(rows.keys())[0]

                # update trial, status, response, frame
                self.code_tab.trial_box.setValue(self.subject.events[row].trial)
                self.code_tab.trial_status.setCurrentText(self.subject.events[row].status)
                self.code_tab.response_box.setCurrentText(self.subject.events[row].response)
                if self.vid:
                    self.update_position(self.subject.events[row].frame)
                if self.code_comparison_dialog:
                    self.code_comparison_dialog.scroll_to_frame(self.subject.events[row].frame)

    def add_reason(self, reason):
        self.subject.reasons.add_reason(reason, ps=self.prescreen_tab.group_who.checkedId())
        self.update_log()
        self.update_info_panel()

    def add_event(self, event):
        event.frame = self.vid.frame_number
        self.subject.events.add_event(event)
        self.update_log()
        # Scroll to the newly-added item
        row = self.subject.events.absolute_index(event)
        self.logtable.scroll_to_row(row)

    def delete_data_rows(self, rows):
        """Delete rows from events or reasons as appropriate """
        if self.active_tab == TAB_PRESCREEN:  # Prescreen
            # delete prescreen reasons by trial
            ps = self.prescreen_tab.prescreener()
            for row in rows:
                trial = int(rows[row])
                self.subject.reasons.delete_reason(trial, ps)
        elif self.active_tab == TAB_CODE:  # Code
            # delete code entries by row (in descending order)
            for row in reversed(sorted(rows)):
                self.subject.events.delete_event(row)

    def build_menu(self):
        """Create the menu bar and global fixed actions"""
        # Create new action
        new_action = QAction('&New', self)
        new_action.setShortcut('Ctrl+N')
        new_action.setStatusTip('Reset to initial state')
        new_action.triggered.connect(self.reset_state)

        # Create open action
        open_action = QAction(QtGui.QIcon('open.png'), '&Load movie', self)
        open_action.setShortcut('Ctrl+L')
        open_action.setStatusTip('Load movie')
        open_action.triggered.connect(self.open_video)

        # Create open datafile action
        data_open_action = QAction(QtGui.QIcon('open.png'), '&Open file', self)
        data_open_action.setShortcut('Ctrl+O')
        data_open_action.setStatusTip('Open datafile')
        data_open_action.triggered.connect(self.open_datafile)

        # Create save action
        data_save_as_action = QAction(QtGui.QIcon('save.png'), 'Save &as...', self)
        data_save_as_action.setStatusTip('Save datafile with new filename')
        data_save_as_action.triggered.connect(self.save_as_datafile)

        data_save_action = QAction(QtGui.QIcon('save.png'), '&Save', self)
        data_save_action.setShortcut('Ctrl+S')
        data_save_action.setStatusTip('Save datafile')
        data_save_action.triggered.connect(self.save_datafile)

        reliability_action = QAction('&Compare against', self)
        reliability_action.setShortcut('Ctrl+T')
        reliability_action.setStatusTip('Compare coding against another file')
        reliability_action.triggered.connect(self.open_reliability_datafile)

        export_action = QAction('E&xport CSV', self)
        export_action.setStatusTip('Export CSV')
        export_action.triggered.connect(self.export_csv)

        # Create exit action
        exit_action = QAction(QtGui.QIcon('exit.png'), '&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close)

        # Synchronize
        self.synchronize_action = QAction('&Resynchronize', self)
        self.synchronize_action.setShortcut('Ctrl+R')
        self.synchronize_action.setStatusTip('Resynchronize timestamp')
        self.synchronize_action.triggered.connect(self.resynchronize)
        self.synchronize_action.setEnabled(False)

        self.open_subject_action = QAction('Subject &Info', self)
        self.open_subject_action.setShortcut('Ctrl+I')
        self.open_subject_action.setStatusTip('Open Subject Information Window')
        self.open_subject_action.triggered.connect(self.open_subject_dialog)

        self.open_occluders_action = QAction('&Occluders', self)
        self.open_occluders_action.setStatusTip('Open Occluder Window')
        self.open_occluders_action.triggered.connect(self.open_occluder_dialog)

        self.open_settings_action = QAction('&Settings', self)
        self.open_settings_action.setStatusTip('Open Settings Window')
        self.open_settings_action.triggered.connect(self.open_settings_dialog)

        # Create menu bar and add action
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('&File')
        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addAction(data_open_action)
        file_menu.addAction(data_save_action)
        file_menu.addAction(data_save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(export_action)
        file_menu.addAction(reliability_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu('&Edit')
        edit_menu.addAction(self.synchronize_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.open_subject_action)
        edit_menu.addAction(self.open_occluders_action)
        edit_menu.addAction(self.open_settings_action)

    def resynchronize(self):
        # Prompt user to enter a new timestamp for the current frame
        new_frame_number = self.get_timecode_frames()
        if new_frame_number:
            self.subject.timecode_offsets[self.vid.frame_number] = new_frame_number - self.vid.frame_number
            self.update_timecode()
            # update log table so that timestamps are correct
            self.update_log()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        super().keyPressEvent(event)
        self.handle_keypress(event)

    def handle_keypress(self, e):
        if e.key() == Qt.Key_Right:
            self.next_frame()
        elif e.key() == Qt.Key_Left:
            self.prev_frame()
        elif e.key() == Qt.Key_Up:
            # forward up/down keypresses to the log table
            self.logtable.keyPressEvent(e)
        elif e.key() == Qt.Key_Down:
            # forward up/down keypresses to the log table
            self.logtable.keyPressEvent(e)
        elif e.key() == Qt.Key_BracketLeft:
            self.prev_step()
        elif e.key() == Qt.Key_BracketRight:
            self.next_step()
        elif e.key() == Qt.Key_Space:
            self.toggle_state()
        elif e.key() in (Qt.Key_Plus, Qt.Key_Equal):
            if self.logtable.has_selection():
                self.change_selected_trials(1)
            else:
                self.change_trial(1)
        elif e.key() == Qt.Key_Minus:
            if self.logtable.has_selection():
                self.change_selected_trials(-1)
            else:
                self.change_trial(-1)
        elif e.key() in (Qt.Key_Enter, Qt.Key_Return):
            if self.active_tab == TAB_PRESCREEN:
                self.prescreen_tab.record_reason()
            else:
                self.code_tab.record_event()
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # The order of operations is important here
            selected_rows = self.logtable.selected_rows()
            self.logtable.delete_selected()
            self.delete_data_rows(selected_rows)
            self.update_log()  # necessary only to update row highlighting if error status has changed
            self.update_info_panel()
        elif e.key() == self.subject.settings.get('Toggle Trial Status Key', None):
            # toggle between 0 and 1
            self.code_tab.trial_status.setCurrentIndex(not self.code_tab.trial_status.currentIndex())
        elif e.key() in self.subject.settings.get('Response Keys', {}):
            self.code_tab.response_box.setCurrentText(self.subject.settings['Response Keys'][e.key()])

        # Clear the log table when pressing a key that results in changing the position in the video
        if e.key() in (Qt.Key_Right, Qt.Key_Left, Qt.Key_BracketLeft, Qt.Key_BracketRight, Qt.Key_Space):
            self.logtable.clearSelection()

    def change_selected_trials(self, delta):
        rows = self.logtable.selected_rows()
        if delta > 0:
            rows = reversed(sorted(rows))
        else:
            rows = sorted(rows)

        if self.active_tab == TAB_PRESCREEN:
            # get the trial number from the log table
            for r in rows:
                trial = self.logtable.data[r][0]
                self.subject.reasons.change_trial(trial, delta, self.prescreen_tab.prescreener())
        elif self.active_tab == TAB_CODE:
            for r in rows:
                self.subject.events.change_trial(r, delta)
        self.update_log()
        self.update_info_panel()

    def change_trial(self, delta):
        if self.active_tab == TAB_PRESCREEN:
            self.prescreen_tab.trial_box.setValue(self.prescreen_tab.trial_box.value() + delta)
        elif self.active_tab == TAB_CODE:
            self.code_tab.trial_box.setValue(self.code_tab.trial_box.value() + delta)

    def open_subject_dialog(self):
        if not self.subject_dialog:
            self.subject_dialog = SubjectDialog(self)
        self.subject_dialog.show()

    def open_occluder_dialog(self):
        if not self.occluder_dialog:
            self.occluder_dialog = OccluderDialog(self)
        self.occluder_dialog.show()

    def open_settings_dialog(self):
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.show()

    def enable_controls(self):
        self.play_button.setEnabled(True)
        self.next_button.setEnabled(True)
        self.prev_button.setEnabled(True)
        self.synchronize_action.setEnabled(True)
        self.code_tab.record_button.setEnabled(True)
        self.prescreen_tab.record_button.setEnabled(True)

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
        self.update_position(self.vid.frame_number)
        self.show_frame()

    def next_frame(self):
        # Advance to next frame of video
        self.change_frame(1)

    def prev_frame(self):
        # Move to previous frame of video
        self.change_frame(-1)

    def next_step(self):
        # Step forward in video
        self.change_frame(self.subject.settings['Step'])

    def prev_step(self):
        # Step backward in video
        self.change_frame(-self.subject.settings['Step'])

    def show_frame(self):
        """ Display the current frame of video"""
        if not self.vid:
            return

        frame = self.vid.frame
        h, w, d = frame.shape
        image = QtGui.QImage(frame.data, w, h, QtGui.QImage.Format_RGB888)

        # Draw occluders in image
        painter = QtGui.QPainter(image)
        for occluder in self.subject.occluders:
            painter.fillRect(occluder, QtCore.Qt.gray)
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
        self.update_position(0)

        # Update playback speed
        if self.vid.frame_rate > 0:
            self.frame_delay = 1000 / self.vid.frame_rate
        else:
            self.frame_delay = 33.3  # fallback to assumed 30 fps

        self.show_frame()

        # prompt for starting timecode
        self.subject.timecode_offsets[0] = self.get_timecode_frames()
        self.update_timecode()

    def get_timecode_frames(self):
        # Prompt user to enter a timecode.  Return the corresponding frame number
        timecode_dialog = TimecodeDialog(self, self.timecode.framerate)
        retval = timecode_dialog.exec_()
        if retval == QDialog.Accepted:
            return timecode_dialog.timecode.frames - 1
        else:
            return 0

    def open_video(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Video") #, QtCore.QDir.homePath())

        if filename != '':
            self.video_source = filename

            self.initialize_video()
            try:
                self.audio.set_video_source(self.video_source, self.vid.frame_rate)
            except FileNotFoundError as e:
                # probably missing ffmpeg
                self.message_box.setText(e.strerror)
            self.enable_controls()

    def open_datafile(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Data File", filter="Data Files (*.vcx)") #, QtCore.QDir.homePath())
        if filename != '':
            self.subject.from_plist(load_datafile(filename))

            self.update_log()
            self.update_info_panel()
            if self.subject_dialog:
                self.subject_dialog.update_from_dict(self.subject.to_dict())
            self.filename = filename
            self.setWindowTitle('peyecoder - {}'.format(os.path.basename(filename)))

    def save_datafile(self):
        if self.filename:
            save_datafile(self.filename, self.subject.to_plist())
        else:
            self.save_as_datafile()

    def save_as_datafile(self):
        filename = get_save_filename(self, "Save Data File", filter="Data Files (*.vcx)", default_suffix='vcx')
        if filename != '':
            save_datafile(filename, self.subject.to_plist())
            self.filename = filename
            self.setWindowTitle('peyecoder - {}'.format(os.path.basename(filename)))

    def export_csv(self):
        """Open the export csv dialog"""
        export_dialog = ExportDialog(self)
        export_dialog.exec_()

    def open_reliability_datafile(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Reliability Data File", filter="Data Files (*.vcx)") #, QtCore.QDir.homePath())
        if filename != '':
            if self.code_comparison_dialog:
                self.code_comparison_dialog.load_data(filename)
            else:
                self.code_comparison_dialog = CodeComparisonDialog(self, filename)
            self.code_comparison_dialog.show()

            report = reliability_report(self.subject, self.code_comparison_dialog.subject, self.timecode)
            text = '\n'.join(report)
            if self.report_dialog:
                self.report_dialog.set_text(text)
            else:
                self.report_dialog = ReportDialog(self, text)
            self.report_dialog.show()

    def reset_info_panel(self):
        # Reset the info panel widgets
        self.subject_number_box.setText('')
        self.order_label_box.setText('')
        self.unused_box.setText('')
        self.prescreened_box.setText('')
        self.step_label.setText('Step: {}'.format(self.subject.settings['Step']))

    def update_info_panel(self):
        # Refresh the info panel widgets
        self.subject_number_box.setText(str(self.subject['Number']))
        self.order_label_box.setText(self.subject['Order'])
        self.unused_box.setText(self.subject.trial_order.get_unused_display())
        self.prescreened_box.setText(self.subject.reasons.get_unused_display())
        self.step_label.setText('Step: {}'.format(self.subject.settings['Step']))

    def play(self):
        t0 = time.perf_counter()
        self.vid.next()
        self.update_position(self.vid.frame_number)
        self.show_frame()
        if self.state == STATE_PLAYING:
            delay = self.frame_delay - (time.perf_counter() - t0) * 1000
            QtCore.QTimer.singleShot(max(math.floor(delay), 0), self.play)

    def toggle_state(self):
        if not self.vid:
            return
        if self.state == STATE_PLAYING:
            self.play_button.setIcon(
                    self.style().standardIcon(QStyle.SP_MediaPlay))
            self.state = STATE_PAUSED
            if not self.audio_muted:
                self.audio.stop()
        else:
            self.play_button.setIcon(
                    self.style().standardIcon(QStyle.SP_MediaPause))
            self.state = STATE_PLAYING
            self.play()
            if not self.audio_muted:
                self.audio.play()

    def toggle_mute(self):
        """ Callback for the audio mute button """
        self.audio_muted = not self.audio_muted
        if self.audio_muted:
            icon_style = QStyle.SP_MediaVolumeMuted
            if self.state == STATE_PLAYING:
                self.audio.stop()
        else:
            icon_style = QStyle.SP_MediaVolume
            if self.state == STATE_PLAYING:
                self.audio.play()
        self.mute_button.setIcon(self.style().standardIcon(icon_style))

    def update_timecode(self):
        # Update timecode display to match current frame number
        self.timecode.frames = self.vid.frame_number + 1 + self.subject.timecode_offsets.get_offset(self.vid.frame_number)
        self.timecode_label.setText(str(self.timecode))

    def update_position(self, position):
        self.position_slider.setValue(position)
        self.setPosition(position)

    def durationChanged(self, duration):
        self.position_slider.setRange(0, duration - 1)

    def setPosition(self, position):
        self.vid.goto_framenumber(position)
        self.audio.seek(position)
        self.update_timecode()
        self.show_frame()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self.show_frame()  # update (and resize) the display of the current frame

    def splitter_moved(self, pos, index):
        """Splitter between video and log table moved"""
        self.show_frame()  # update (and resize) the display of the current frame


def run():
    """Run peyecoder application"""
    app = QtWidgets.QApplication([])
    widget = MainWindow()
    widget.resize(800, 600)
    widget.show()
    return app.exec_()

