import sys
import time
import math

from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtWidgets import QLabel, QPushButton, QSlider, QStyle, \
    QHBoxLayout, QVBoxLayout, QSizePolicy, QAction, QGridLayout, QDialog, \
    QTabWidget, QSplitter, QScrollArea, QMessageBox
from PySide2.QtGui import Qt
from PySide2.QtCore import QObject, QEvent, Signal

import timecode
import os
import sys
from functools import partial

from peyecoder.video_reader import BufferedVideoReader
from peyecoder.audio_player import VideoAudioPlayer
from peyecoder.panels import Prescreen, Code, LogTable
from peyecoder.models import Subject, Occluders
from peyecoder.file_utils import load_datafile, save_datafile, intify_keys
from peyecoder.dialogs import SubjectDialog, TimecodeDialog, OccluderDialog, SettingsDialog, CodeComparisonDialog, \
    ReportDialog, ExportDialog, get_save_filename, ReplaceDialog
from peyecoder.reliability import reliability_report
from peyecoder import version

STATE_PLAYING = 1
STATE_PAUSED = 2

TAB_PRESCREEN = 0
TAB_CODE = 1


class JumpSlider(QSlider):
    """ This subclass of QSlider supports jumping to a position on the slider by clicking on it (while continuing to
    allow dragging the slider).  Clicking on the slider results in the firing of a new signal 'clicked'.
    Inspired by https://stackoverflow.com/questions/11132597/qslider-mouse-direct-jump
    """
    clicked = Signal(int)

    def mousePressEvent(self, ev):
        """ Jump to click position """
        v = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), ev.x(), self.width())
        self.setValue(v)
        super().mousePressEvent(ev)
        self.clicked.emit(v)


class MainEventFilter(QObject):
    def eventFilter(self, obj, event):
        # if event.type() == QEvent.KeyPress:
        #     print('key pressed: {}, obj={}'.format(event.key(), obj))

        if event.type() == QEvent.MouseButtonPress:
            if obj != LogTable:
                self.parent().logtable.clearSelection()

        return QObject.eventFilter(self, obj, event)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, argv):
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
        self.replace_dialog = None

        self.subject = Subject(self)

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

        scrollable_message = QScrollArea()
        scrollable_message.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scrollable_message.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollable_message.setWidgetResizable(True)
        scrollable_message.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        scrollable_message.setWidget(self.message_box)

        layout3 = QVBoxLayout()
        layout3.addWidget(splitter)
        layout3.addWidget(tab_widget)
        layout3.addLayout(info_grid)

        container2 = QtWidgets.QWidget()
        container2.setLayout(layout3)

        splitter2 = QSplitter()
        splitter2.setOrientation(Qt.Vertical)
        splitter2.addWidget(container2)
        splitter2.addWidget(scrollable_message)
        splitter2.setCollapsible(0, False)
        splitter2.setCollapsible(1, False)
        splitter2.splitterMoved.connect(self.splitter_moved)

        self.setCentralWidget(splitter2)

        # Use event filter to cause mouse clicks away from the log table to
        # clear the selection (removes focus to fix key handling)
        eventfilter = MainEventFilter(self)
        self.installEventFilter(eventfilter)

        self.build_menu()

        self.reset_state()

        # If a filename has been passed as a command line argument, try to open it
        if len(argv) > 1:
            if os.path.isfile(argv[1]):
                self.open_data_file(argv[1])

    def prompt_save(self):
        proceed = True
        if self.subject.dirty:
            ret = QMessageBox.warning(self, 'Peyecoder', 'Do you want to save changes?',
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                      defaultButton=QMessageBox.Save)
            if ret == QMessageBox.Save:
                # save and, if successful, close
                proceed = self.save_datafile()
            else:
                proceed = ret != QMessageBox.Cancel

        return proceed

    def closeEvent(self, event):
        if self.prompt_save():
            event.accept()
        else:
            event.ignore()

    def load_defaults(self):
        """Load default.vcx if present in working directory."""
        if getattr(sys, 'frozen', False):
            # running in a bundle
            defaultdir = os.path.dirname(sys.executable)
        else:
            defaultdir = os.getcwd()

        filename = os.path.join(defaultdir, 'default.vcx')
        if os.path.isfile(filename):
            data = load_datafile(filename)
            d = data['Subject']

            if 'Occluders' in d:
                self.subject.occluders = Occluders.from_dictlist(d['Occluders'])
            if 'Settings' in d:
                if 'Response Keys' in d['Settings']:
                    d['Settings']['Response Keys'] = intify_keys(d['Settings']['Response Keys'])
                self.subject.settings.update(d['Settings'])

            print('Loaded settings from {}'.format(filename))
        else:
            print('No settings file detected: {}'.format(filename))

    def reset_state(self):
        """Initialize state or reset to initial state"""

        if not self.prompt_save():
            return

        self.subject = Subject(self)
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

        # reset coding controls
        self.prescreen_tab.trial_box.setValue(1)
        self.code_tab.trial_box.setValue(1)
        self.tab_widget.setCurrentIndex(TAB_CODE)  # setting the current tab also updates the log table

        self.reset_info_panel()

        self.load_defaults()

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

        self.position_slider = JumpSlider(QtCore.Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.setPosition)
        self.position_slider.clicked.connect(self.setPosition)
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
        self.logtable.setStyleSheet("QTableWidget::item:selected{background-color: palette(Highlight); color: palette(HighlightedText);};")
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

        return self.tab_widget

    def change_tab(self, index):
        self.active_tab = index
        self.update_log()

    def update_log(self, preserve_highlight=False):
        """Update data and labels in log file"""
        if preserve_highlight:
            rows = self.logtable.selected_rows()
        if self.active_tab == TAB_PRESCREEN:
            self.logtable.set_prescreen_labels(self.prescreen_tab.prescreener())
            self.logtable.load_data(self.subject.reasons.render(self.prescreen_tab.prescreener()))
            error_rows, error_trials = self.subject.reasons.error_items(self.prescreen_tab.prescreener())
            # Only display error messages and redden rows if "display both coders" is checked
            if error_trials and (self.prescreen_tab.prescreener() == 0):
                self.logtable.redden_rows(error_rows)
                self.message_box.setText('Mismatch between prescreener 1 and prescreener 2 for trials {}'.format(error_trials))
            else:
                self.message_box.setText('')
        elif self.active_tab == TAB_CODE:
            self.logtable.set_code_labels()
            self.logtable.load_data(self.subject.events.render(self.subject.timecode_offsets, self.timecode))

            errors, err_msg = self.subject.events.error_items(self.subject.trial_order.unused + self.subject.reasons.unused(),
                                                              self.subject.trial_order.max_trial)
            self.logtable.redden_rows(errors)
            self.message_box.setText('\n'.join(err_msg))
        if preserve_highlight:
            self.logtable.itemSelectionChanged.disconnect(self.select_code_row)
            self.logtable.select_rows(rows)

            self.logtable.itemSelectionChanged.connect(self.select_code_row)

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
        self.subject.dirty = True

    def add_event(self, event):
        event.frame = self.vid.frame_number
        self.subject.events.add_event(event)
        self.update_log(preserve_highlight=True)
        # Scroll to the newly-added item
        row = self.subject.events.absolute_index(event)
        self.logtable.scroll_to_row(row)
        self.subject.dirty = True

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
        self.subject.dirty = True

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

        prescreen_action = QAction('Pre-Screen', self)
        prescreen_action.setShortcut('Ctrl+Shift+P')
        prescreen_action.triggered.connect(partial(self.tab_widget.setCurrentIndex, TAB_PRESCREEN))

        code_action = QAction('Code', self)
        code_action.setShortcut('Ctrl+Shift+C')
        code_action.triggered.connect(partial(self.tab_widget.setCurrentIndex, TAB_CODE))

        next_step_action = QAction('Skip &forward', self)
        next_step_action.setShortcut(']')
        next_step_action.setShortcutContext(Qt.WidgetShortcut)  # prevent menu item from intercepting this keypress
        next_step_action.triggered.connect(self.next_step)

        prev_step_action = QAction('Skip &backward', self)
        prev_step_action.setShortcut('[')
        prev_step_action.setShortcutContext(Qt.WidgetShortcut)
        prev_step_action.triggered.connect(self.prev_step)

        increment_action = QAction('Increment Trial', self)
        increment_action.setShortcut('+')
        increment_action.setShortcutContext(Qt.WidgetShortcut)
        increment_action.triggered.connect(partial(self.change_trial, 1))

        decrement_action = QAction('Decrement Trial', self)
        decrement_action.setShortcut('-')
        decrement_action.setShortcutContext(Qt.WidgetShortcut)
        decrement_action.triggered.connect(partial(self.change_trial, -1))

        increment_selected_action = QAction('Increment Selected Trials', self)
        increment_selected_action.setShortcut('Alt++')
        increment_selected_action.setShortcutContext(Qt.WidgetShortcut)
        increment_selected_action.triggered.connect(partial(self.change_selected_trials, 1))

        decrement_selected_action = QAction('Decrement Selected Trials', self)
        decrement_selected_action.setShortcut('Alt+-')
        decrement_selected_action.setShortcutContext(Qt.WidgetShortcut)
        decrement_selected_action.triggered.connect(partial(self.change_selected_trials, -1))

        help_url_action = QAction('Online Help', self)
        help_url_action.triggered.connect(self.open_help_url)

        about_box_action = QAction('About peyecoder', self)
        about_box_action.setMenuRole(QAction.NoRole)
        about_box_action.triggered.connect(self.show_about_box)

        export_action = QAction('E&xport CSV', self)
        export_action.setShortcut('Ctrl+e')
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
        self.open_occluders_action.setShortcut('Ctrl+b')
        self.open_occluders_action.setStatusTip('Open Occluder Window')
        self.open_occluders_action.triggered.connect(self.open_occluder_dialog)

        self.open_settings_action = QAction('&Settings', self)
        self.open_settings_action.setShortcut('Ctrl+,')
        self.open_settings_action.setStatusTip('Open Settings Window')
        self.open_settings_action.setMenuRole(QAction.NoRole)
        self.open_settings_action.triggered.connect(self.open_settings_dialog)

        self.open_replace_action = QAction('&Replace Responses', self)
        self.open_replace_action.setStatusTip('Find/Replace Responses')
        self.open_replace_action.triggered.connect(self.open_replace_dialog)

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
        edit_menu.addAction(self.open_subject_action)
        edit_menu.addAction(self.open_occluders_action)
        edit_menu.addAction(self.open_settings_action)
        edit_menu.addAction(self.open_replace_action)

        controls_menu = menu_bar.addMenu('&Controls')
        controls_menu.addAction(prescreen_action)
        controls_menu.addAction(code_action)
        controls_menu.addSeparator()
        controls_menu.addAction(self.synchronize_action)
        controls_menu.addSeparator()
        controls_menu.addAction(next_step_action)
        controls_menu.addAction(prev_step_action)
        controls_menu.addSeparator()
        controls_menu.addAction(increment_action)
        controls_menu.addAction(decrement_action)
        controls_menu.addAction(increment_selected_action)
        controls_menu.addAction(decrement_selected_action)

        help_menu = menu_bar.addMenu('&Help')
        help_menu.addAction(help_url_action)
        help_menu.addAction(about_box_action)

    def open_help_url(self):
        target = 'https://rholson1.github.io/peyecoder/'
        url = QtCore.QUrl(target)
        if not QtGui.QDesktopServices.openUrl(url):
            QMessageBox.warning(self, 'Open URL', 'Unable to open {}'.format(target))

    def show_about_box(self):
        QMessageBox.about(self, 'About peyecoder',
                          ('<center>peyecoder {}</center>'
                           '<p>This work was supported in part by a core grant to the Waisman Center from the '
                           'National Institute of Child Health and Human Development (U54 HD090256), in '
                           'part by a grant to Susan Ellis Weismer from the National Institute on Deafness '
                           'and Other Communication Disorders (R01 DC017974), and in part by a grant to '
                           'Casey Lew-Williams from the National Institute of Child Health and Human Development (R01 HD095912).</p>'
                           '<p>To cite, see <a href="https://doi.org/10.5281/zenodo.3939233">https://doi.org/10.5281/zenodo.3939233</a></p>'
                           ).format(version))

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
            if e.modifiers() & Qt.AltModifier:
                if self.logtable.has_selection():
                    self.change_selected_trials(1)
            else:
                self.change_trial(1)
        elif e.key() == Qt.Key_Minus:
            if e.modifiers() & Qt.AltModifier:
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
            next_row = max(selected_rows) - len(selected_rows) + 1  # identify the row after the last row to be deleted
            self.logtable.delete_selected()
            self.delete_data_rows(selected_rows)
            self.update_log()  # necessary only to update row highlighting if error status has changed

            # Disconnect self.select_code_row before highlighting next row -- don't want to change position in video
            self.logtable.itemSelectionChanged.disconnect(self.select_code_row)
            self.logtable.select_rows([next_row])  # highlight the row after the last deleted row
            self.logtable.itemSelectionChanged.connect(self.select_code_row)
            self.update_info_panel()
        elif e.key() == self.subject.settings.get('Toggle Trial Status Key', None):
            # toggle between 0 and 1
            self.code_tab.trial_status.setCurrentIndex(not self.code_tab.trial_status.currentIndex())
        elif e.key() in self.subject.settings.get('Response Keys', {}):
            self.code_tab.response_box.setCurrentText(self.subject.settings['Response Keys'][e.key()])

        # Clear the log table when pressing a key that results in changing the position in the video
        # if e.key() in (Qt.Key_Right, Qt.Key_Left, Qt.Key_BracketLeft, Qt.Key_BracketRight, Qt.Key_Space):
        #    self.logtable.clearSelection()
        #    self.logtable.setCurrentIndex(QtCore.QModelIndex())  # clear current index within logtable

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
        self.update_log(preserve_highlight=True)
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

    def open_replace_dialog(self):
        if not self.replace_dialog:
            self.replace_dialog = ReplaceDialog(self)
        self.replace_dialog.show()

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
        bytes_per_line = w * d
        image = QtGui.QImage(frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)

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

        # store frame rate for use when exporting data
        self.subject.set_framerate(self.vid.frame_rate)

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
            self.subject.events.remove_offset(self.subject.timecode_offsets.get_offset(0))
            try:
                self.audio.set_video_source(self.video_source, self.vid.frame_rate)
            except FileNotFoundError as e:
                # probably missing ffmpeg
                self.message_box.setText(e.strerror)
            self.enable_controls()

            # may need to re-render timestamps of existing events if video framerate is not 30 fps
            self.update_log()

    def open_datafile(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Data File", filter="Data Files (*.vcx)") #, QtCore.QDir.homePath())
        self.open_data_file(filename)

    def open_data_file(self, filename):
        if filename != '':
            self.reset_state()
            self.subject.from_plist(load_datafile(filename))
            if self.vid:
                self.subject.events.remove_offset(self.subject.timecode_offsets.get_offset(0))

            # update timecode so stored framerate used to render timecodes (if a video is not loaded)
            self.timecode = timecode.Timecode(self.subject['Framerate'])
            self.timecode.drop_frame = False

            self.update_log()
            self.update_info_panel()
            if self.subject_dialog:
                self.subject_dialog.update_from_dict(self.subject.to_dict())
            self.filename = filename
            self.setWindowTitle('peyecoder - {}'.format(os.path.basename(filename)))
            self.code_tab.set_responses(list(self.subject.settings['Response Keys'].values()))

    def save_datafile(self):
        if self.filename:
            if save_datafile(self.filename, self.subject.to_plist()):
                self.subject.dirty = False
        else:
            self.save_as_datafile()
        return not self.subject.dirty

    def save_as_datafile(self):
        filename = get_save_filename(self, "Save Data File", filter="Data Files (*.vcx)", default_suffix='vcx')
        if filename != '':
            if save_datafile(filename, self.subject.to_plist()):
                self.subject.dirty = False
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
        try:
            self.audio.seek(position)
        except:
            QMessageBox.warning(self, 'peyecoder', ('Unable to seek to the requested position in the audio.'
                                                    ' This likely means that an incorrect timecode was entered '
                                                    'when the video was opened.  Reload video and enter correct '
                                                    'starting timestamp.'), QMessageBox.Ok)
            self.subject.events.reset_offset()

        self.update_timecode()
        self.show_frame()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self.show_frame()  # update (and resize) the display of the current frame

    def splitter_moved(self, pos, index):
        """Splitter between video and log table moved"""
        self.show_frame()  # update (and resize) the display of the current frame


def run(argv):
    """Run peyecoder application"""
    app = QtWidgets.QApplication([])
    widget = MainWindow(argv)
    widget.resize(800, 600)
    widget.show()
    return app.exec_()

