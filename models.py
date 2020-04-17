# Data models for peyecoder

from PySide2.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QSpinBox, QComboBox, \
    QRadioButton, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QCheckBox, \
    QButtonGroup

from PySide2.QtGui import Qt
from PySide2.QtCore import QRect

from sortedcontainers import SortedDict, SortedList
from functools import total_ordering
from collections import Counter

from timecode import Timecode
import csv


class Subject:
    fieldnames = ('Birthday', 'Coder', 'Date of Test', 'Number', 'Order',
                  'Primary PS', 'Secondary PS', 'Checked By',
                  'Primary PS Complete', 'Secondary PS Complete',
                  'Sex', 'Unused Trials', 'Notes')

    def __init__(self):
        self._d = {}

    def update_from_dict(self, d):
        for f in self.fieldnames:
            self._d[f] = d.get(f, '')

    def to_dict(self):
        return self._d


class Reason:
    def __init__(self, trial=0, include=False, reason=''):
        self.trial = trial
        self.include = include
        self.reason = reason

    def values(self):
        return [self.trial, self.include, self.reason]

    def __str__(self):
        return 'Trial: {}, Code: {}, Reason: {}'.format(self.trial, self.include, self.reason)


class Reasons:
    """Store lists of Reasons for prescreeners 1 and 2, and provide methods for rendering lists to display"""
    def __init__(self, prescreener_1=None, prescreener_2=None):
        self.ps = [
            SortedDict(prescreener_1),
            SortedDict(prescreener_2)
        ]

    def add_reason(self, reason: Reason, ps):
        """
        Store a reason for a prescreener.  One reason can be stored per trial for each prescreener.
        :param reason: Reason to be stored
        :param ps: Prescreener number (1 or 2)
        """
        assert ps in (1, 2)
        self.ps[ps - 1][reason.trial] = reason

    def delete_reason(self, trial, ps=0):
        """
        Delete reason(s) associated with a particular trial number.
        :param trial: Trial number
        :param ps: Prescreener number (1 or 2), or 0 (default) for both
        """
        assert ps in (0, 1, 2)
        if ps == 0:
            ps = (1, 2)
        else:
            ps = (ps,)

        for n in ps:
            self.ps[n - 1].pop(trial, 0)

    def change_trial(self, trial, delta, ps=0):
        """
        Update the trial number in a reason for a particular trial
        :param trial:
        :param delta:
        :param ps:
        """
        assert ps in (0, 1, 2)
        if ps == 0:
            ps = (1, 2)
        else:
            ps = (ps,)

        new_trial = trial + delta
        old_trial = trial

        for n in ps:
            if new_trial in self.ps[n-1]:
                raise Exception('The requested trial number change conflicts with an existing item.')
            try:
                self.ps[n-1][new_trial] = self.ps[n-1].pop(old_trial)
                self.ps[n-1][new_trial].trial = new_trial
            except KeyError:
                pass

    def render(self, ps=0):
        """
        Return a data set that can be displayed in a LogTable
        :param ps: Prescreener number (1 or 2), or 0 (default) for both
        """
        assert ps in (0, 1, 2)
        # Just return the list of reasons if a single prescreener
        if ps in (1, 2):
            return [[r.trial, r.include, r.reason] for r in self.ps[ps - 1].values()]

        # Return a compiled list of reasons if both prescreeners
        data = []
        if ps == 0:
            trials = list(set(self.ps[0]).union(self.ps[1]))
            for t in trials:
                p1 = self.ps[0].get(t, Reason(t, '', ''))
                p2 = self.ps[1].get(t, Reason(t, '', ''))
                data.append([t, p1.include, p1.reason, p2.include, p2.reason])
        return data

    def unused(self):
        """List of trials prescreened out by prescreener 1"""
        return [v.trial for v in self.ps[0].values() if not v.include]


@total_ordering
class Event:
    def __init__(self, trial=0, status='', response='', frame=0):
        self.trial = trial
        self._status = status
        self.response = response
        self.frame = frame

    @property
    def status(self):
        if self._status:
            return 'on'
        else:
            return 'off'

    def values(self):
        return [self.trial, self.status, self.response, self.frame]

    def __eq__(self, other):
        return self.frame == other.frame

    def __lt__(self, other):
        return self.frame < other.frame

    def __str__(self):
        return 'Trial: {}, Status: {}, Response: {}, Frame: {}'.format(self.trial, self.status, self.response, self.frame)


# This version of Events only allows one event per timecode
class EventsA:
    def __init__(self):
        self.events = SortedDict()

    def add_event(self, event):
        self.events[event.frame] = event

    def delete_event(self, index):
        self.events.popitem(index)

    def render(self, offsets, timecode):
        """
        Return data suitable for display in LogTable
        :param offsets: Offsets object which contains frame offsets used to generate timecodes that match video
        :param timecode: Timecode object (with predefined framerate, drop_frame) used to generate timecode strings
        """
        data = []
        for event in self.events:
            timecode.frames = event.frame + 1 + offsets.get_offset(event.frame)
            data.append([event.trial, event.status, event.response, str(timecode)])
        return data


# This version of Events allows multiple events per timecode; they are ordered by frame number
class Events:
    def __init__(self, events=None):
        self.events = SortedList(events)

    def add_event(self, event):
        self.events.add(event)

    def delete_event(self, index):
        self.events.pop(index)

    def change_trial(self, index, delta):
        self.events[index].trial += delta

    def render(self, offsets, timecode):
        """
        Return data suitable for display in LogTable
        :param offsets: Offsets object which contains frame offsets used to generate timecodes that match video
        :param timecode: Timecode object (with predefined framerate, drop_frame) used to generate timecode strings
        """
        data = []
        for event in self.events:
            timecode.frames = event.frame + 1 + offsets.get_offset(event.frame)
            data.append([event.trial, event.status, event.response, str(timecode)])
        return data

    def to_plist(self):
        data = {}
        for n, event in enumerate(self.events):
            data['Response {}'.format(n)] = {
                'Trial': event.trial,
                'Trial Status': event.status,
                'Type': event.response,
                'Frame': event.frame
            }
        return data

    @staticmethod
    def from_plist(data, framerate_string='29.97'):

        timecode = Timecode(framerate_string)
        timecode.drop_frame = False

        events = []
        for e in data.values():
            if 'Timecode' in e:
                # convert iCoder-style timecode to frame number
                timecode.set_timecode('{}:{}:{}:{}'.format(
                    e['Timecode']['Hour'],
                    e['Timecode']['Minute'],
                    e['Timecode']['Second'],
                    e['Timecode']['Frame'])
                )
                e['Frame'] = timecode.frames - 1

            events.append(
                Event(trial=e['Trial'],
                      status=e['Trial Status'],
                      response=e['Type'],
                      frame=e['Frame'])
            )
        return Events(events)

    def error_items(self, unused_trials):
        """ Check for errors and return a list of row numbers (which should be highlighted) and
        corresponding error messages"""
        all_error_rows = []
        msg = []
        # 1. Check for coding entries with a trial number in unused
        error_rows = [i for i, e in enumerate(self.events) if e.trial in unused_trials]
        if error_rows:
            all_error_rows += error_rows
            msg.append('Code entry for unused trial')

        # 2. Check for duplicate entries (same timestamp)
        frame_counter = Counter([e.frame for e in self.events])
        duplicate_frames = [k for k, v in frame_counter.items() if v > 1]
        error_rows = [i for i, e in enumerate(self.events) if e.frame in duplicate_frames]
        if error_rows:
            all_error_rows += error_rows
            msg.append('Entries have the same timestamp')

        return all_error_rows, msg


    def __getitem__(self, item):
        return self.events.__getitem__(item)

    def __getattr__(self, item):
        return getattr(self.events, item)


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
        self.radio_primary = QRadioButton('Primary')
        self.radio_secondary = QRadioButton('Secondary')
        self.radio_primary.setChecked(True)
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
                      status=self.trial_status.currentText(),
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
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setFocusPolicy(Qt.NoFocus)

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
        #self.setRowCount(len(self.data))
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


class Offsets(SortedDict):
    """Class to store frame offsets for timecodes in a video"""
    def get_offset(self, frame):
        """Given a frame number, determine the corresponding offset"""
        offset = 0
        for k, v in self.items():
            if k > frame:
                return offset
            offset = v
        return offset

    def to_plist(self):
        return {str(k): v for k, v in self.items()}

    @staticmethod
    def from_plist(data):
        return Offsets({int(k): v for k, v in data.items()})


# Occluders is basically a list of QRect objects
class Occluders:
    def __init__(self, occluders=None):
        """
        :param occluders: list of QRect objects
        """
        self.occluders = occluders if occluders else []

    @staticmethod
    def from_dictlist(d):
        return Occluders([QRect(*[r[x] for x in 'xywh']) for r in d])

    def to_dictlist(self):
        return [dict(zip('xywh', r.getRect())) for r in self.occluders]

    def __iter__(self):
        return self.occluders.__iter__()


class TrialOrder:
    def __init__(self):
        self.data = []
        self.unused = []

    def name(self):
        if self.data:
            return self.data[0]['Name']
        else:
            return 'No Trial Order loaded'

    def calc_unused(self):
        self.unused = [d['Trial Number'] for d in self.data if d['Used'] == 'no']

    def read_trial_order(self, filename):
        """ Read data from a trial order file"""
        data = []

        with open(filename, 'r', newline='') as f:
            dialect = csv.Sniffer().sniff(f.read(1024), delimiters=',\t')
            f.seek(0)
            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                #try:
                data.append({
                    'Name': row.get('Name', ''),
                    'Trial Number': int(row.get('Trial Number', 0) or row.get('trial number', 0)),
                    'Sound Stimulus': row.get('Sound Stimulus', ''),
                    'Left Image': row.get('Left Image', ''),
                    'Center Image': row.get('Center Image', ''),
                    'Right Image': row.get('Right Image', ''),
                    'Target Side': row.get('Target Side', '') or row.get('target side', ''),
                    'Condition': row.get('Condition', '') or row.get('condition', ''),
                    'Used': row.get('Used', ''),
                    'Trial End': int(row.get('Trial End', 0) or row.get('TrEnd', 0)),
                    'Critical Onset': int(row.get('Critical Onset', 0) or row.get('CritOnset', 0))
                })
                #except ValueError:
                 #   pass
        self.data = data
        self.calc_unused()
