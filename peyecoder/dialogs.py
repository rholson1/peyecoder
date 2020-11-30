from PySide2 import QtGui
from PySide2.QtWidgets import QLabel, QLineEdit, QPushButton, \
    QHBoxLayout, QVBoxLayout, QGridLayout, QDialog, QFileDialog, \
    QRadioButton, QButtonGroup, QDialogButtonBox, QCheckBox, QPlainTextEdit, QFrame, \
    QTableWidget, QHeaderView, QTableWidgetItem, QSizePolicy, QMessageBox

from PySide2.QtGui import Qt, QIntValidator, QRegExpValidator, QKeySequence
from PySide2.QtCore import QRect, QRegExp, Signal

from dateutil import parser
from urllib.parse import urlparse
from urllib.request import url2pathname

import timecode
import os
import re

from peyecoder.models import Occluders, Subject
from peyecoder.panels import LogTable
from peyecoder.file_utils import load_datafile
from peyecoder.export import export, INVERT_RESPONSE, INVERT_TRIAL_ORDER


def get_save_filename(parent, caption, filter, default_suffix=''):
    """ Use a custom save dialog instead of the convenience function to support default suffix"""
    dialog = QFileDialog(parent, caption=caption, filter=filter)
    dialog.setAcceptMode(QFileDialog.AcceptSave)
    dialog.setFileMode(QFileDialog.AnyFile)
    if default_suffix:
        dialog.setDefaultSuffix(default_suffix)
    if dialog.exec_():
        filenames = dialog.selectedFiles()
        if filenames:
            return filenames[0]
    return ''


class FileDropTarget(QLabel):
    dropped = Signal(str, name='dropped')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.filename = ''

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        data = event.mimeData()
        if data.hasFormat('text/uri-list'):
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        file_url = event.mimeData().text().strip()  # works with Nautilus, but not Thunar
        if not file_url:
            file_url = event.mimeData().urls()[0].url()  # works with Thunar and Nautilus
        self.filename = url2pathname(urlparse(file_url).path)
        event.acceptProposedAction()
        self.dropped.emit(self.filename)


class SubjectDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('Subject Information')
        # Create widgets

        self.subject_label = QLabel('Subject Number:')
        self.subject_box = QLineEdit()
        self.subject_box.editingFinished.connect(self.sync_fields)

        self.sex_label = QLabel('Sex:')
        self.male_radio = QRadioButton('Male')
        self.female_radio = QRadioButton('Female')
        self.sex_layout = QHBoxLayout()
        self.sex_layout.addWidget(self.male_radio)
        self.sex_layout.addWidget(self.female_radio)
        # Group radio buttons logically in button group to create one mutually-exclusive set
        self.sex_radiogroup = QButtonGroup()
        self.sex_radiogroup.addButton(self.male_radio, id=1)
        self.sex_radiogroup.addButton(self.female_radio, id=2)
        self.sex_radiogroup.buttonClicked.connect(self.sync_fields)

        date_regexp = QRegExp('^[0-3]?[0-9]/[0-3]?[0-9]/(?:[0-9]{2})?[0-9]{2}$')
        self.date_validator = QRegExpValidator(date_regexp)

        self.dob_label = QLabel('Date of Birth:')
        self.dob_box = QLineEdit()
        self.dob_box.setValidator(self.date_validator)
        self.dob_box.setPlaceholderText('MM/DD/YY')
        self.dob_box.editingFinished.connect(self.update_age)
        self.dob_box.editingFinished.connect(self.sync_fields)

        self.participation_date_label = QLabel('Participation Date:')
        self.participation_date_box = QLineEdit()
        self.participation_date_box.setValidator(self.date_validator)
        self.participation_date_box.setPlaceholderText('MM/DD/YY')
        self.participation_date_box.editingFinished.connect(self.update_age)
        self.participation_date_box.editingFinished.connect(self.sync_fields)

        self.age_label = QLabel('Age:')
        self.months_label = QLabel(' Months')

        self.trial_order_label = QLabel('Trial Order:')
        self.trial_order_box = FileDropTarget('Drop trial order file here')
        self.trial_order_box.dropped.connect(self.update_trial_order)

        self.ps1_label = QLabel('Primary Prescreener:')
        self.ps1_box = QLineEdit()
        self.ps1_box.editingFinished.connect(self.sync_fields)
        self.ps1_checkbox = QCheckBox('Completed')
        self.ps1_checkbox.stateChanged.connect(self.sync_fields)

        self.ps2_label = QLabel('Secondary Prescreener:')
        self.ps2_box = QLineEdit()
        self.ps2_box.editingFinished.connect(self.sync_fields)
        self.ps2_checkbox = QCheckBox('Completed')
        self.ps2_checkbox.stateChanged.connect(self.sync_fields)

        self.coder_label = QLabel('Coder:')
        self.coder_box = QLineEdit()
        self.coder_box.editingFinished.connect(self.sync_fields)

        self.checked_label = QLabel('Checked by:')
        self.checked_box = QLineEdit()
        self.checked_box.editingFinished.connect(self.sync_fields)

        self.notes_label = QLabel('Notes:')
        self.notes_box = QPlainTextEdit()
        self.notes_box.textChanged.connect(self.sync_fields)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self.accept)

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
        grid.addWidget(self.age_label, r, 0)
        grid.addWidget(self.months_label, r, 1)
        r += 1
        grid.addWidget(self.trial_order_label, r, 0)
        grid.addWidget(self.trial_order_box, r, 1)
        r += 1
        grid.addWidget(self.ps1_label, r, 0)
        grid.addWidget(self.ps1_box, r, 1)
        grid.addWidget(self.ps1_checkbox, r, 2)
        r += 1
        grid.addWidget(self.ps2_label, r, 0)
        grid.addWidget(self.ps2_box, r, 1)
        grid.addWidget(self.ps2_checkbox, r, 2)
        r += 1
        grid.addWidget(self.coder_label, r, 0)
        grid.addWidget(self.coder_box, r, 1)
        r += 1
        grid.addWidget(self.checked_label, r, 0)
        grid.addWidget(self.checked_box, r, 1)
        r += 1
        grid.addWidget(self.notes_label, r, 0)
        grid.addWidget(self.notes_box, r, 1)

        layout = QVBoxLayout()
        layout.addLayout(grid)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        self.update_from_dict(self.parent().subject.to_dict())

    def update_trial_order(self, filename):
        """ When a trial order file is dragged into the subject dialog, read the file into TrialOrder object"""
        self.parent().subject.trial_order.read_trial_order(filename)
        self.trial_order_box.setText(self.parent().subject.trial_order.name())
        self.sync_fields()

    def update_age(self):
        try:
            dob = parser.parse(self.dob_box.text(), dayfirst=False).date()
            participation_date = parser.parse(self.participation_date_box.text(), dayfirst=False).date()
            age_days = (participation_date - dob).days
            age_months = age_days / 30.44
            self.months_label.setText('{:0.1f} Months'.format(age_months))
        except:
            self.months_label.setText('-- Months')

    def sync_fields(self, *args):
        # Update parent.subject from Subject Dialog fields
        d = {
            'Number': self.subject_box.text(),
            'Sex': self.sex_radiogroup.checkedId() == 1,  # True for Male, False, for Female
            'Birthday': self.dob_box.text(),
            'Date of Test': self.participation_date_box.text(),
            'Order': self.parent().subject.trial_order.name(),
            'Primary PS': self.ps1_box.text(),
            'Primary PS Complete': self.ps1_checkbox.isChecked(),
            'Secondary PS': self.ps2_box.text(),
            'Secondary PS Complete': self.ps2_checkbox.isChecked(),
            'Coder': self.coder_box.text(),
            'Checked By': self.checked_box.text(),
            'Unused Trials': [],
            'Notes': self.notes_box.toPlainText()
        }

        self.parent().subject.update_from_dict(d)

        # When the subject info dialog is first opened, sync_fields is called even if nothing has been entered by the
        # user.  To avoid unnecessary prompts to save when nothing has been changed, only mark the record dirty if
        # a datafile has been loaded.
        if self.parent().filename:
            self.parent().subject.dirty = True
        self.parent().update_info_panel()
        self.parent().update_log()

    def update_from_dict(self, d):
        self.subject_box.setText(str(d.get('Number', '')))
        if 'Sex' in d:
            self.male_radio.setChecked(d['Sex'])
            self.female_radio.setChecked(not d['Sex'])
        self.dob_box.setText(d.get('Birthday', ''))
        self.participation_date_box.setText(d.get('Date of Test', ''))
        self.trial_order_box.setText(self.parent().subject.trial_order.name())
        self.ps1_box.setText(d.get('Primary PS', ''))
        self.ps1_checkbox.setChecked(d.get('Primary PS Complete', False))
        self.ps2_box.setText(d.get('Secondary PS', ''))
        self.ps2_checkbox.setChecked(d.get('Secondary PS Complete', False))
        self.coder_box.setText(d.get('Coder', ''))
        self.checked_box.setText(d.get('Checked By', ''))
        # self.unused_trials_box...
        self.notes_box.insertPlainText(d.get('Notes', ''))

        # update calculated control
        self.update_age()


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

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.timecode_box)
        layout.addWidget(self.button_box)

        self.setLayout(layout)

    def set_timecode(self):
        self.timecode.set_timecode(self.timecode_box.text())


class OccluderDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('Occluders')

        self.top_label = QLabel('Enter desired occluder coordinates in pixel units\n'
                                'measured from upper left corner of the video frame')

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(('x', 'y', 'w', 'h'))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.add_row_button = QPushButton('Add')
        self.add_row_button.clicked.connect(self.add_row)

        self.save_occluders_button = QPushButton('Save')
        self.save_occluders_button.clicked.connect(self.save_occluders)

        self.delete_row_button = QPushButton('Delete')
        self.delete_row_button.clicked.connect(self.delete_current_row)

        self.buttons = QHBoxLayout()
        self.buttons.addWidget(self.delete_row_button)
        self.buttons.addWidget(self.add_row_button)
        self.buttons.addWidget(self.save_occluders_button)


        self.layout = QVBoxLayout()
        self.layout.addWidget(self.top_label)
        self.layout.addWidget(self.table)
        self.layout.addLayout(self.buttons)
        #self.layout.addWidget(self.add_row_button)
        #self.layout.addWidget(self.save_occluders_button)

        self.setLayout(self.layout)

        self.load_occluders()
        self.add_row()

    def load_occluders(self):
        for rect in self.parent().subject.occluders:
            row = self.table.rowCount()
            self.add_row()
            for col, item in enumerate(rect.getRect()):
                self.table.setItem(row, col, QTableWidgetItem(str(item)))

    def save_occluders(self):
        occluders = []
        for r in range(self.table.rowCount()):
            try:
                r = QRect(*[int(self.table.item(r, c).text()) for c in range(4)])
                occluders.append(r)
            except (AttributeError, ValueError):
                # AttributeError occurs for blank cells
                # ValueError occurs for cells containing non-integer text
                pass
        self.parent().subject.occluders = Occluders(occluders)
        self.parent().subject.dirty = True
        self.parent().vid.reload_buffer()
        self.parent().show_frame()

    def add_row(self):
        self.table.setRowCount(self.table.rowCount() + 1)

    def delete_current_row(self):
        # require that _something_ is selected to indicate intent
        if len(self.table.selectedRanges()) > 0:
            self.table.removeRow(self.table.currentRow())


class KeyTableWidget(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(('Key', 'Response'))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.data = []
        self.cellChanged.connect(self.cell_changed)

    def from_dict(self, d):
        self.data = [{
            'keycode': k,
            'text': QKeySequence(k).toString(),
            'response': v
        } for k, v in d.items()]
        self.update()

    def to_dict(self):
        return {d['keycode']: d['response'] for d in self.data}

    def update(self):
        """update table using values in self.data"""
        self.cellChanged.disconnect(self.cell_changed)

        self.setRowCount(len(self.data))
        for row, d in enumerate(self.data):
            item = QTableWidgetItem(d['text'])
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 0, item)
            self.setItem(row, 1, QTableWidgetItem(d['response']))

        self.cellChanged.connect(self.cell_changed)

    def cell_changed(self, row, column):
        """Cell (row, column) changed.  Its new value is self.item(row, column).text()"""
        if column == 1:
            self.data[row]['response'] = self.item(row, column).text()

    def add_row(self):
        self.data.append({})
        row = self.rowCount()
        self.setRowCount(row + 1)
        item = QTableWidgetItem('')
        item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.setItem(row, 0, item)
        self.setItem(row, 1, QTableWidgetItem(''))

    def delete_row(self):
        row = self.currentRow()
        self.removeRow(row)
        del self.data[row]

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if self.currentColumn() == 0:
            row = self.currentRow()
            text = QKeySequence(event.key()).toString()
            self.data[row] = {
                'keycode': event.key(),
                'text': text,
                'response': self.item(row, 1).text()
            }
            item = QTableWidgetItem(text)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 0, item)
        else:
            super().keyPressEvent(event)


class KeyWidget(QLineEdit):
    def __init__(self):
        super().__init__()
        self._key = None

    def set_key(self, key):
        self._key = key
        self.setText(QKeySequence(key).toString())

    def get_key(self):
        return self._key

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        self.set_key(event.key())


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('Settings')

        step_label = QLabel('Step')
        self.step_box = QLineEdit(str(self.parent().subject.settings['Step']))
        self.step_box.setFixedWidth(32)
        step_validator = QIntValidator(1, 99)
        self.step_box.setValidator(step_validator)
        step_layout = QHBoxLayout()
        step_layout.addWidget(self.step_box)
        step_layout.addWidget(QLabel('frames'))

        response_label = QLabel('Response Keys')
        self.key_table = KeyTableWidget()
        self.add_row_button = QPushButton('Add row')
        self.add_row_button.clicked.connect(self.key_table.add_row)
        self.del_row_button = QPushButton('Delete row')
        self.del_row_button.clicked.connect(self.key_table.delete_row)
        row_layout = QHBoxLayout()
        row_layout.addWidget(self.add_row_button)
        row_layout.addWidget(self.del_row_button)
        table_layout = QVBoxLayout()
        table_layout.addWidget(self.key_table)
        table_layout.addLayout(row_layout)

        toggle_label = QLabel('Toggle Trial Status')
        self.toggle_box = KeyWidget()

        grid = QGridLayout()
        grid.addWidget(step_label, 0, 0)
        grid.addLayout(step_layout, 0, 1)
        grid.addWidget(response_label, 1, 0, alignment=Qt.AlignTop)
        grid.addLayout(table_layout, 1, 1)
        grid.addWidget(toggle_label, 2, 0)
        grid.addWidget(self.toggle_box, 2, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(grid)

        layout.addWidget(self.button_box)

        self.setLayout(layout)

    def load_settings(self):
        d = self.parent().subject.settings
        self.step_box.setText(str(d.get('Step', '')))
        self.key_table.from_dict(d['Response Keys'])
        self.toggle_box.set_key(d.get('Toggle Trial Status Key'))

    def save_settings(self):
        d = self.parent().subject.settings
        d['Step'] = int(self.step_box.text())
        d['Response Keys'] = self.key_table.to_dict()
        d['Toggle Trial Status Key'] = self.toggle_box.get_key()
        # Update step label on main form
        self.parent().step_label.setText('Step: {}'.format(d['Step']))
        # update code responses to reflect current response keys
        self.parent().code_tab.set_responses(list(d['Response Keys'].values()))
        self.parent().subject.dirty = True

    def show(self):
        super().show()
        self.load_settings()

    def accept(self):
        self.button_box.setFocus()  # in case a cell is in edit mode
        self.save_settings()
        super().accept()


class CodeComparisonDialog(QDialog):
    """Dialog to show code from a second coding session to allow comparison"""
    def __init__(self, parent, filename=''):
        super().__init__(parent)

        self.frames = []

        self.subject = Subject()
        layout = QVBoxLayout()
        layout.addWidget(self.build_table())
        self.setLayout(layout)

        if filename:
            self.load_data(filename)

    def build_table(self):
        self.logtable = LogTable()
        self.logtable.setColumnCount(4)
        self.logtable.setAlternatingRowColors(True)
        self.logtable.setHorizontalHeaderLabels(self.logtable.Labels.Code)

        self.logtable.setMinimumWidth(400)
        self.logtable.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        #self.logtable.itemSelectionChanged.connect(self.select_code_row)

        return self.logtable

    def load_data(self, filename):
        self.frames = []
        self.setWindowTitle(os.path.basename(filename))
        self.subject = Subject()
        self.subject.from_plist(load_datafile(filename))

        self.update_table()

    def update_table(self):
        self.logtable.load_data(self.subject.events.render(self.subject.timecode_offsets, self.parent().timecode))
        self.frames = [e.frame for e in self.subject.events]

    def scroll_to_frame(self, frame):
        # Scroll to and highlight the row closest to the supplied frame number
        d = [abs(f - frame) for f in self.frames]
        row = d.index(min(d))
        self.logtable.scrollToItem(self.logtable.item(row, 0))

        self.logtable.clearSelection()
        for c in range(4):
            self.logtable.item(row, c).setSelected(True)


class ReportDialog(QDialog):
    """Dialog to show a reliability report"""
    def __init__(self, parent, text=None):
        super().__init__(parent)
        self.setWindowTitle('Reliability Report')
        self.textedit = QPlainTextEdit()

        layout = QVBoxLayout()
        layout.addWidget(self.textedit)
        self.setLayout(layout)
        if text:
            self.set_text(text)

    def set_text(self, text):
        self.textedit.setPlainText(text)


class ExportDialog(QDialog):
    """Dialog for creating CSV output"""
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Export CSV')

        self.format_label = QLabel('Export Format:')
        self.wide_radio = QRadioButton('Wide (iCoder) Format')
        self.long_radio = QRadioButton('Long Format')
        self.format_radiogroup = QButtonGroup()
        self.format_radiogroup.addButton(self.wide_radio, id=1)
        self.format_radiogroup.addButton(self.long_radio, id=2)
        self.wide_radio.setChecked(True)  # default wide

        self.invert_label = QLabel('Left-Right Inversion:')
        self.invert_trial_order_radio = QRadioButton('Invert Target Side and Images (iCoder)')
        self.invert_response_radio = QRadioButton('Invert Responses')
        self.invert_radiogroup = QButtonGroup()
        self.invert_radiogroup.addButton(self.invert_trial_order_radio, id=INVERT_TRIAL_ORDER)
        self.invert_radiogroup.addButton(self.invert_response_radio, id=INVERT_RESPONSE)
        self.invert_trial_order_radio.setChecked(True)  # default to iCoder-style inversion

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.export_csv)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.format_label)
        layout.addWidget(self.wide_radio)
        layout.addWidget(self.long_radio)
        layout.addWidget(self.invert_label)
        layout.addWidget(self.invert_trial_order_radio)
        layout.addWidget(self.invert_response_radio)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

    def export_csv(self):
        filename = get_save_filename(self, "Save CSV File", filter="CSV Files (*.csv)", default_suffix='csv')
        if filename != '':
            export_format = {1: 'wide', 2: 'long'}[self.format_radiogroup.checkedId()]
            export(filename, self.parent().subject, format=export_format, invert_rl=self.invert_radiogroup.checkedId())
            self.accept()
        else:
            self.reject()


class ReplaceDialog(QDialog):
    """Dialog for find/replace responses"""
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Replace Response')
        self.find_label = QLabel('Find:')
        self.find_box = QLineEdit()
        self.entire_checkbox = QCheckBox('Entire response')
        self.case_checkbox = QCheckBox('Match case')
        self.replace_label = QLabel('Replace:')
        self.replace_box = QLineEdit()
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        find_layout = QHBoxLayout()
        find_layout.addWidget(self.find_label)
        find_layout.addWidget(self.find_box)
        check_layout = QHBoxLayout()
        check_layout.addWidget(self.entire_checkbox)
        check_layout.addWidget(self.case_checkbox)
        replace_layout = QHBoxLayout()
        replace_layout.addWidget(self.replace_label)
        replace_layout.addWidget(self.replace_box)
        layout = QVBoxLayout()
        layout.addLayout(find_layout)
        layout.addLayout(check_layout)
        layout.addLayout(replace_layout)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def accept(self):

        f = self.find_box.text().strip()
        r = self.replace_box.text().strip()
        entire_match = self.entire_checkbox.isChecked()
        case_match = self.case_checkbox.isChecked()

        if f and r:
            for event in self.parent().subject.events:
                if case_match:
                    if entire_match:
                        if event.response == f:
                            event.response = r
                    else:
                        if f in event.response:
                            event.response = event.response.replace(f, r)
                else:
                    if entire_match:
                        if event.response.lower == f.lower():
                            event.response = r
                    else:
                        # Use regex for case-insensitive replacement
                        event.response = re.sub(re.escape(f), r, event.response, flags=re.IGNORECASE)
            self.parent().update_log()
            super().accept()
        else:
            QMessageBox.warning(self, 'peyecoder', 'Both "find" and "replace" fields must contain text.', QMessageBox.Ok)
