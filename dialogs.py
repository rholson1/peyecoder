from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtWidgets import QLabel, QLineEdit, QPushButton, QSlider, QStyle, \
    QHBoxLayout, QVBoxLayout, QSizePolicy, QAction, QGridLayout, QDialog, \
    QRadioButton, QButtonGroup, QDialogButtonBox, QTabWidget, QCheckBox, QPlainTextEdit, QFrame, \
    QTableWidget, QHeaderView, QTableWidgetItem, QSplitter

from PySide2.QtGui import Qt, QIntValidator, QRegExpValidator, QKeySequence
from PySide2.QtCore import QRect, QRegExp, Signal

from dateutil import parser
from urllib.parse import urlparse
from urllib.request import url2pathname

import timecode

from models import Occluders


class FileDropTarget(QLabel):
    dropped = Signal(str, name='dropped')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.filename = ''

    def dragEnterEvent(self, event:QtGui.QDragEnterEvent):
        data = event.mimeData()
        if data.hasFormat('text/uri-list'):
            event.acceptProposedAction()


    def dropEvent(self, event:QtGui.QDropEvent):
        #file_url = event.mimeData().text().strip()  # works with Nautilus, but not Thunar
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

        self.offsets_label = QLabel('Resynchronization:')
        self.offsets_box = QLabel('')

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
        grid.addWidget(self.offsets_label, r, 0)
        grid.addWidget(self.offsets_box, r, 1)
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
        self.parent().trial_order.read_trial_order(filename)
        self.trial_order_box.setText(self.parent().trial_order.name())
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
            'Order': self.parent().trial_order.name(),
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
        self.parent().update_info_panel()

    def update_from_dict(self, d):
        self.subject_box.setText(str(d.get('Number', '')))
        if 'Sex' in d:
            self.male_radio.setChecked(d['Sex'])
        self.dob_box.setText(d.get('Birthday', ''))
        self.participation_date_box.setText(d.get('Date of Test', ''))
        self.trial_order_box.setText(self.parent().trial_order.name())
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

        self.add_row_button = QPushButton('Add Occluder')
        self.add_row_button.clicked.connect(self.add_row)

        self.save_occluders_button = QPushButton('Save Occluders')
        self.save_occluders_button.clicked.connect(self.save_occluders)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.top_label)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.add_row_button)
        self.layout.addWidget(self.save_occluders_button)

        self.setLayout(self.layout)

        self.load_occluders()
        self.add_row()

    def load_occluders(self):
        for rect in self.parent().occluders:
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
        self.parent().occluders = Occluders(occluders)

    def add_row(self):
        self.table.setRowCount(self.table.rowCount() + 1)


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

    def keyPressEvent(self, event:QtGui.QKeyEvent):
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

    def keyPressEvent(self, event:QtGui.QKeyEvent):
        self.set_key(event.key())


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('Settings')

        step_label = QLabel('Step')
        self.step_box = QLineEdit(str(self.parent().settings['Step']))
        self.step_box.setFixedWidth(32)
        step_validator = QIntValidator(1, 99)
        self.step_box.setValidator(step_validator)
        #self.step_box.textChanged.connect(self.parent().update_step)
        step_layout = QHBoxLayout()
        #step_layout.addWidget(step_label)
        step_layout.addWidget(self.step_box)
        step_layout.addWidget(QLabel('frames'))

        response_label = QLabel('Response Keys')
        self.key_table = KeyTableWidget()
        #self.key_table.cellChanged.connect(self.key_table.cellChangeda)
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
        #layout.addWidget(response_label)
        #layout.addWidget(self.key_table)
        #layout.addWidget(self.add_row_button)

        layout.addWidget(self.button_box)

        self.setLayout(layout)

    def load_settings(self):
        d = self.parent().settings
        self.step_box.setText(str(d.get('Step', '')))
        self.key_table.from_dict(d['Response Keys'])
        self.toggle_box.set_key(d.get('Toggle Trial Status Key'))

    def save_settings(self):
        d = self.parent().settings
        d['Step'] = int(self.step_box.text())
        d['Response Keys'] = self.key_table.to_dict()
        d['Toggle Trial Status Key'] = self.toggle_box.get_key()

    def show(self):
        super().show()
        self.load_settings()

    def accept(self):
        self.save_settings()
        super().accept()


