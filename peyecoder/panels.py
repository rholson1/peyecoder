
from PySide2.QtWidgets import QWidget, QLabel, QPushButton, QSpinBox, QComboBox, \
    QRadioButton, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QCheckBox, \
    QButtonGroup, QHeaderView

from PySide2.QtGui import Qt

from peyecoder.models import Reason, Event


class Prescreen(QWidget):
    REASONS = (
        'Inattentive',
        'Child Talking',
        'Parent Talking',
        'Parent Interference',
        'Child Not Looking Before Sound Offset',
        'Equipment Malfunction',
        'Experiment Ended Early',
        'Other'
    )

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

        trial_label = QLabel('Trial:')
        self.trial_box = QSpinBox()
        self.trial_box.setFixedWidth(64)
        self.trial_box.setValue(1)
        self.trial_box.setFocusPolicy(Qt.NoFocus)

        reason_label = QLabel('Reason:')
        self.reason_box = QComboBox()
        self.reason_box.addItems(self.REASONS)
        self.reason_box.setFocusPolicy(Qt.NoFocus)

        self.code_radio = QRadioButton('Code')
        self.nocode_radio = QRadioButton('Do Not Code')
        self.code_radio.setChecked(True)
        self.code_radio.setFocusPolicy(Qt.NoFocus)
        self.nocode_radio.setFocusPolicy(Qt.NoFocus)

        radio_layout = QVBoxLayout()
        radio_layout.addStretch()
        radio_layout.addWidget(self.code_radio)
        radio_layout.addWidget(self.nocode_radio)
        radio_layout.addStretch()
        self.group_code = QButtonGroup()
        self.group_code.addButton(self.code_radio)
        self.group_code.addButton(self.nocode_radio)

        self.record_button = QPushButton('Record Reason')
        self.record_button.clicked.connect(self.record_reason)
        self.record_button.setEnabled(False)
        self.record_button.setFocusPolicy(Qt.NoFocus)

        self.both_checkbox = QCheckBox('Display both coders')
        self.both_checkbox.setFocusPolicy(Qt.NoFocus)
        self.radio_primary = QRadioButton('Primary')
        self.radio_secondary = QRadioButton('Secondary')
        self.radio_primary.setChecked(True)
        self.radio_primary.setFocusPolicy(Qt.NoFocus)
        self.radio_secondary.setFocusPolicy(Qt.NoFocus)
        who_layout = QVBoxLayout()
        who_layout.addWidget(self.both_checkbox)
        who_layout.addWidget(self.radio_primary)
        who_layout.addWidget(self.radio_secondary)
        self.group_who = QButtonGroup()
        self.group_who.addButton(self.radio_primary, id=1)
        self.group_who.addButton(self.radio_secondary, id=2)

        layout = QHBoxLayout()
        layout.addWidget(trial_label)
        layout.addWidget(self.trial_box)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_box)
        layout.addLayout(radio_layout)

        layout.addWidget(self.record_button)
        layout.addStretch()
        layout.addLayout(who_layout)

        self.setLayout(layout)

    def record_reason(self):
        reason = Reason(trial=self.trial_box.value(),
                        include=self.code_radio.isChecked(),
                        reason=self.reason_box.currentText())
        self.callback(reason)

    def prescreener(self):
        if self.both_checkbox.isChecked():
            return 0
        else:
            return self.group_who.checkedId()


class Code(QWidget):
    TRIAL_STATUS = ('on', 'off')

    def __init__(self, callback):
        super().__init__()

        self.callback = callback

        trial_label = QLabel('Trial:')
        self.trial_box = QSpinBox()
        self.trial_box.setFixedWidth(64)
        self.trial_box.setValue(1)
        self.trial_box.setFocusPolicy(Qt.NoFocus)

        trial_status_label = QLabel('Trial Status:')
        self.trial_status = QComboBox()
        self.trial_status.addItems(self.TRIAL_STATUS)
        self.trial_status.setFocusPolicy(Qt.NoFocus)

        response_label = QLabel('Response:')
        self.response_box = QComboBox()
        self.response_box.setFocusPolicy(Qt.NoFocus)

        self.record_button = QPushButton('Record Event')
        self.record_button.clicked.connect(self.record_event)
        self.record_button.setEnabled(False)
        self.record_button.setFocusPolicy(Qt.NoFocus)

        layout = QHBoxLayout()
        layout.addWidget(trial_label)
        layout.addWidget(self.trial_box)
        layout.addWidget(trial_status_label)
        layout.addWidget(self.trial_status)
        layout.addWidget(response_label)
        layout.addWidget(self.response_box)
        layout.addStretch()
        layout.addWidget(self.record_button)

        self.setLayout(layout)

    def set_responses(self, responses):
        self.response_box.clear()
        self.response_box.addItems(responses)

    def record_event(self):
        event = Event(trial=self.trial_box.value(),
                      status=self.trial_status.currentText() == 'on',
                      response=self.response_box.currentText())
        if self.trial_status.currentText() == 'off':
            self.trial_box.setValue(self.trial_box.value() + 1)
            self.trial_status.setCurrentText('on')
        self.callback(event)


class LogTable(QTableWidget):
    class Labels:
        Code = ('Trial #', 'Trial Status', 'Response', 'Time Code')
        Prescreen1 = ('Trial #', 'PS 1 Code?', 'PS 1 Reason?')
        Prescreen2 = ('Trial #', 'PS 2 Code?', 'PS 2 Reason?')
        Prescreen12 = ('Trial #', 'PS 1 Code?', 'PS 1 Reason?', 'PS 2 Code?', 'PS 2 Reason?')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setFocusPolicy(Qt.NoFocus)
        self.setVerticalScrollMode(self.ScrollPerPixel)

        self.data = []  # list of iterables

    def add_entry(self, entry):
        """ Append an entry to the table data and to the table"""
        self.data.append(entry)
        self._add_row(entry)

    def _add_row(self, entry):
        # Add a row to the table, given an iterable
        new_row = self.rowCount()
        self.setRowCount(new_row + 1)
        for col, v in enumerate(entry):
            item = QTableWidgetItem(str(v))
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)  # Do not want ItemIsEditable
            self.setItem(new_row, col, item)

    def load_data(self, data):
        self.data = data
        # update table from self.data
        self.setRowCount(0)
        for entry in self.data:
            self._add_row(entry)

    def redden_selected(self):
        for item in self.selectedItems():
            item.setForeground(Qt.red)

    def redden_rows(self, rows):
        for r in rows:
            for c in range(self.columnCount()):
                self.item(r, c).setForeground(Qt.red)

    def delete_selected(self):
        """Delete selected rows"""
        deleted_rows = []
        for row in reversed(range(self.rowCount())):
            if self.item(row, 0).isSelected():
                self.data.pop(row)
                self.removeRow(row)
                deleted_rows.append(row)
        return deleted_rows

    def increment_selected(self):
        """Increment the value in the first cell of selected rows"""
        for row in range(self.rowCount()):
            if self.item(row, 0).isSelected():
                self.data[row][0] += 1
                self.item(row, 0).setText(str(self.data[row][0]))

    def decrement_selected(self):
        """Decrement the value in the first cell of selected rows"""
        for row in range(self.rowCount()):
            if self.item(row, 0).isSelected():
                self.data[row][0] -= 1
                self.item(row, 0).setText(str(self.data[row][0]))

    def has_selection(self):
        return len(self.selectedItems()) > 0

    def selected_rows(self):
        # Return rows as dictionary with the keys the row numbers
        # and the values the text of the first cell in the row
        rows = {}
        for row in range(self.rowCount()):
            if self.item(row, 0).isSelected():
                rows[row] = self.item(row, 0).text()
        return rows

    def set_code_labels(self):
        self.set_labels(self.Labels.Code)

    def set_prescreen_labels(self, ps):
        if ps == 0:
            self.set_labels(self.Labels.Prescreen12)
        elif ps == 1:
            self.set_labels(self.Labels.Prescreen1)
        elif ps == 2:
            self.set_labels(self.Labels.Prescreen2)

    def set_labels(self, labels):
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)

    def scroll_to_row(self, row):
        # scrolling to the item doesn't work very well for the last item, so scrollToBottom instead
        if row == self.rowCount() - 1:
            self.scrollToBottom()
        else:
            self.scrollToItem(self.item(row, 0), self.PositionAtCenter)
