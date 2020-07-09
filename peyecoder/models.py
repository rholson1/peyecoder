# Data models for peyecoder

from PySide2.QtCore import QRect, Qt

from sortedcontainers import SortedDict, SortedList
from functools import total_ordering
from collections import Counter
from itertools import groupby, accumulate
from operator import attrgetter

from timecode import Timecode
import csv

from peyecoder.file_utils import stringify_keys, intify_keys


class Subject:
    fieldnames = ('Birthday', 'Coder', 'Date of Test', 'Number', 'Order',
                  'Primary PS', 'Secondary PS', 'Checked By',
                  'Primary PS Complete', 'Secondary PS Complete',
                  'Sex', 'Unused Trials', 'Notes')

    def __init__(self):
        self._d = {}

        self.occluders = Occluders()
        self.timecode_offsets = Offsets()
        self.reasons = Reasons()
        self.events = Events()
        self.trial_order = TrialOrder()
        self.settings = {  # Set some default values
            'Step': 10,
            'Toggle Trial Status Key': int(Qt.Key_6),
            'Response Keys': {
                int(Qt.Key_1): 'left',
                int(Qt.Key_2): 'off',
                int(Qt.Key_3): 'right',
                int(Qt.Key_4): 'away',
                int(Qt.Key_5): 'center'
            }
        }

    def update_from_dict(self, d):
        for f in self.fieldnames:
            self._d[f] = d.get(f, '')

    def get_sex_display(self):
        sex = self._d.get('Sex', None)
        if sex is None:
            return 'N/A'
        elif sex:
            return 'M'
        else:
            return 'F'

    def to_dict(self):
        return self._d

    def __getitem__(self, item):
        if item == 'Order':
            return self.trial_order.name()

        return self._d.__getitem__(item)

    def to_plist(self):
        data = {}
        data['Occluders'] = self.occluders.to_dictlist()
        data['Timecode Offsets'] = self.timecode_offsets.to_plist()
        data['Pre-Screen Information'] = self.reasons.to_plist()
        data['Responses'] = self.events.to_plist()
        data['Trial Order'] = self.trial_order.to_plist()
        data['Settings'] = self.settings.copy()
        data['Settings']['Response Keys'] = stringify_keys(self.settings['Response Keys'])
        data.update(self.to_dict())

        return {'Subject': data}

    def from_plist(self, data):
        d = data['Subject']
        if 'Occluders' in d:
            self.occluders = Occluders.from_dictlist(d['Occluders'])
        if 'Timecode Offsets' in d:
            self.timecode_offsets = Offsets.from_plist(d['Timecode Offsets'])
        if 'Pre-Screen Information' in d:
            self.reasons = Reasons.from_plist(d['Pre-Screen Information'])
        if 'Responses' in d:
            self.events = Events.from_plist(d['Responses'])
        if 'Trial Order' in d:
            self.trial_order = TrialOrder.from_plist(d['Trial Order'])
        if 'Settings' in d:
            if 'Response Keys' in d['Settings']:
                d['Settings']['Response Keys'] = intify_keys(d['Settings']['Response Keys'])
            self.settings.update(d['Settings'])
        self.update_from_dict(d)


class Reason:
    def __init__(self, trial=0, include=False, reason=''):
        self.trial = trial
        self._include = include
        self.reason = reason

    def values(self):
        return [self.trial, self._include, self.reason]

    @property
    def include(self):
        if self._include is None:
            return ''
        elif self._include:
            return 'yes'
        else:
            return 'no'

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
                p1 = self.ps[0].get(t, Reason(t, None, ''))
                p2 = self.ps[1].get(t, Reason(t, None, ''))
                data.append([t, p1.include, p1.reason, p2.include, p2.reason])
        return data

    def unused(self):
        """List of trials prescreened out by prescreener 1"""
        return [v.trial for v in self.ps[0].values() if not v._include]

    def get_unused_display(self):
        return ', '.join([str(s) for s in self.unused()])

    def to_plist(self):
        """ Return data ready to write to plist file """
        def prepack(d):
            return {'Pre-Screen Entry {}'.format(k): {
                'Eliminate': not v._include,
                'Reason': v.reason,
                'Trial': v.trial
            } for k, v in d.items()}

        return {
            'Pre-Screen Array 0': prepack(self.ps[0]),
            'Pre-Screen Array 1': prepack(self.ps[1])
        }

    @staticmethod
    def from_plist(d):
        """Import data from data file"""
        return Reasons(*[{v['Trial']: Reason(v['Trial'], not v['Eliminate'], v['Reason'])
                          for v in d['Pre-Screen Array {}'.format(i)].values()}
                         for i in (0, 1)])


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
        return self.frame == other.frame and self._status == other._status

    def __lt__(self, other):
        if self.frame == other.frame:
            # If two events have the same timestamp, status 'on' should sort before 'off'
            return self._status > other._status
        else:
            return self.frame < other.frame

    def __str__(self):
        return 'Trial: {}, Status: {}, Response: {}, Frame: {}'.format(
            self.trial, self.status, self.response, self.frame)


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
                      status=e['Trial Status'] in ('on', True),
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

        # 3. Check for trial numbers that don't increase with increasing frame number
        error_rows = [i for i in range(1, len(self.events)) if self.events[i].trial < self.events[i-1].trial]
        if error_rows:
            all_error_rows += error_rows
            msg.append('Trial numbers are not increasing with increasing timestamp')

        # 4. Check for invalid sequences within trials.
        # a. must not have 2 consecutive events with a response in ('left', 'right') within a trial
        error_rows = []
        for i in range(1, len(self.events)):
            if self.events[i-1].trial == self.events[i].trial and \
                    self.events[i-1].status == self.events[i].status and \
                    self.events[i-1].response in ('left', 'right') and \
                    self.events[i].response in ('left', 'right'):
                error_rows.append(i)
        if error_rows:
            all_error_rows += error_rows
            msg.append('Cannot have consecutive "right" and/or "left" events in a trial')

        # b. must not have 2 consecutive events with the same response
        error_rows = []
        for i in range(1, len(self.events)):
            if self.events[i-1].trial == self.events[i].trial and \
                    self.events[i-1].status == self.events[i].status and \
                    self.events[i-1].response == self.events[i].response:
                error_rows.append(i)
        if error_rows:
            all_error_rows += error_rows
            msg.append('Cannot have consecutive events with the same response')

        # 5. last event in a trial should have status 'off'
        last_rows = accumulate([len(events) for t, events in self.trials().items()])
        error_rows = [r - 1 for r in last_rows if self.events[r-1].status == 'on']
        if error_rows:
            all_error_rows += error_rows
            msg.append('The last event in a trial should have status "off"')

        return all_error_rows, msg

    def __getitem__(self, item):
        return self.events.__getitem__(item)

    def __getattr__(self, item):
        return getattr(self.events, item)

    def absolute_index(self, item):
        # find index of event matching on all fields
        for i, event in enumerate(self.events):
            if item.trial == event.trial and \
                    item._status == event._status and \
                    item.response == event.response and \
                    item.frame == event.frame:
                return i
        return None

    def __len__(self):
        return len(self.events)

    def trials(self):
        """ Compute trials from the list of events"""
        return {k: list(g) for k, g in groupby(self.events, attrgetter('trial'))}

    def frames(self):
        """ Compute frames with responses from events
        Include all frames from start of first trial to end of last trial.
        """
        responses = {}
        for i in range(len(self.events) - 1):
            for f in range(self.events[i].frame, self.events[i + 1].frame):
                responses[f] = self.events[i].response
        # include the last frame
        responses[self.events[-1].frame] = self.events[-1].response
        return responses


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


class Trial(dict):
    """Subclass of dict used to represent a row of the TrialOrder table"""
    def inverted_target(self):
        """Swap left and right target side to account for difference between participant and camera perspective"""
        try:
            if self['Target Side'] in ('R', 'L'):
                return {'R': 'L', 'L': 'R'}[self['Target Side']]
            else:
                return self['Target Side']
        except KeyError:
            return 'No target to invert'


class TrialOrder:
    def __init__(self, data=None):
        self.unused = []
        if data:
            self.data = data
            self.calc_unused()
        else:
            self.data = []

    def name(self):
        if self.data:
            return self.data[0]['Name']
        else:
            return 'No Trial Order loaded'

    def get_unused_display(self):
        return ', '.join([str(s) for s in self.unused])

    def calc_unused(self):
        self.unused = [d['Trial Number'] for d in self.data if d['Used'] == 'no']

    def read_trial_order(self, filename):
        """ Read data from a trial order file"""
        data = []

        with open(filename, 'r', newline='') as f:
            dialect = csv.Sniffer().sniff(f.readline(), delimiters=',\t')
            f.seek(0)
            reader = csv.DictReader(f, dialect=dialect)

            for row in reader:
                trial_number = int(row.get('Trial Number', 0) or row.get('trial number', 0))
                data.append(Trial({
                    'Name': row.get('Name', ''),
                    'Trial Number': trial_number,
                    'Sound Stimulus': row.get('Sound Stimulus', ''),
                    'Left Image': row.get('Left Image', ''),
                    'Center Image': row.get('Center Image', ''),
                    'Right Image': row.get('Right Image', ''),
                    'Target Side': row.get('Target Side', '') or row.get('target side', ''),
                    'Condition': row.get('Condition', '') or row.get('condition', ''),
                    'Used': row.get('Used', ''),
                    'Trial End': int(row.get('Trial End', 0) or row.get('TrEnd', 0)),
                    'Critical Onset': int(row.get('Critical Onset', 0) or row.get('CritOnset', 0))
                }))

        self.data = data
        self.calc_unused()

    def to_plist(self):
        return self.data  # maybe?

    @staticmethod
    def from_plist(data):
        return TrialOrder([Trial(d) for d in data])
