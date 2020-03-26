# Data models for peyecoder

from PySide2.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QSpinBox, QComboBox, \
    QRadioButton, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem




class Subject:
    def __init__(self):
        pass


class Timecode:
    def __init__(self, hour=0, minute=0, second=0, frame=0):
        self.hour = hour
        self.minute = minute
        self.second = second
        self.frame = frame


class Reason:
    def __init__(self, trial=0, include=False, reason=''):
        self.trial = trial
        self.include = include
        self.reason = reason

    def values(self):
        return self.trial, self.include, self.reason

    def __str__(self):
        return 'Trial: {}, Code: {}, Reason: {}'.format(self.trial, self.include, self.reason)


class Event:
    def __init__(self, trial=0, status='', response=''):
        self.trial = trial
        self.status = status
        self.response = response

    def values(self):
        return self.trial, self.status, self.response

    def __str__(self):
        return 'Trial: {}, Status: {}, Response: {}'.format(self.trial, self.status, self.response)


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

        reason_label = QLabel('Reason:')
        self.reason_box = QComboBox()
        self.reason_box.addItems(self.REASONS)

        self.code_radio = QRadioButton('Code')
        self.nocode_radio = QRadioButton('Do Not Code')
        radio_layout = QVBoxLayout()
        radio_layout.addWidget(self.code_radio)
        radio_layout.addWidget(self.nocode_radio)

        record_button = QPushButton('Record Reason')
        record_button.clicked.connect(self.record_reason)

        layout = QHBoxLayout()
        layout.addWidget(trial_label)
        layout.addWidget(self.trial_box)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_box)
        layout.addLayout(radio_layout)
        layout.addStretch()
        layout.addWidget(record_button)

        self.setLayout(layout)

    def record_reason(self):
        reason = Reason(trial=self.trial_box.value(),
                        include=self.code_radio.isChecked(),
                        reason=self.reason_box.currentText())
        self.callback(reason)


class Code(QWidget):
    TRIAL_STATUS = ('On', 'Off')

    def __init__(self, callback):
        super().__init__()

        self.callback = callback

        trial_label = QLabel('Trial:')
        self.trial_box = QSpinBox()
        self.trial_box.setFixedWidth(64)

        trial_status_label = QLabel('Trial Status:')
        self.trial_status = QComboBox()
        self.trial_status.addItems(self.TRIAL_STATUS)

        response_label = QLabel('Response:')
        self.response_box = QComboBox()

        record_button = QPushButton('Record Event')
        record_button.clicked.connect(self.record_event)

        layout = QHBoxLayout()
        layout.addWidget(trial_label)
        layout.addWidget(self.trial_box)
        layout.addWidget(trial_status_label)
        layout.addWidget(self.trial_status)
        layout.addWidget(response_label)
        layout.addWidget(self.response_box)
        layout.addStretch()
        layout.addWidget(record_button)

        self.setLayout(layout)

    def set_responses(self, responses):
        self.response_box.clear()
        self.response_box.addItems(responses)

    def record_event(self):
        event = Event(trial=self.trial_box.value(),
                      status=self.trial_status.currentText(),
                      response=self.response_box.currentText())
        self.callback(event)


class LogTable(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verticalHeader().setVisible(False)

    def add_row(self, obj):
        new_row = self.rowCount() + 1
        self.setRowCount(new_row)
        for col, v in enumerate(obj.values()):
            a = QTableWidgetItem(str(v))
            self.setItem(new_row - 1, col, a)


