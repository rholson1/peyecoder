
from models import Subject
import csv
from dateutil import parser
from math import ceil


def frame2ms(f):
    """Convert a frame number to a time in ms, assuming 30 frames per second"""
    return f * 100 / 3


def ms2frames(ms):
    """Convert a time (in ms) to frames, rounding up"""
    return ceil(ms * 3 / 100)


def age_months(date_of_birth, date_of_interest):
    """Compute age in months given a birth date and a second date"""
    try:
        d0 = parser.parse(date_of_birth, dayfirst=False).date()
        d1 = parser.parse(date_of_interest, dayfirst=False).date()
    except:
        # probably missing one of the dates
        return 0

    age_days = (d1 - d0).days
    age_months_number = age_days / 30.44
    return age_months_number


def compute_accuracy(target, response):
    """Compute accuracy given a target side and a response
    Assume:
    target is one of R, L, N
    response is one of right, left, center, away, off
    """
    if target in ('R', 'L'):
        if (target == 'R' and response == 'right') or (target == 'L' and response == 'left'):
            accuracy = 1
        elif target in ('R', 'L') and response == 'center':
            accuracy = 0.5
        else:
            accuracy = 0
    else:
        accuracy = 'N/A'
    return accuracy


def export(filename, s: Subject, format='long'):
    """Export subject data to a .csv file
    :param s: subject object
    :param filename: full path to the destination file
    :param format: 'wide' or 'long' format for the export file
    """
    if format == 'long':
        export_long(filename, s)
    elif format == 'wide':
        export_wide(filename, s)


def export_long(filename, s: Subject):
    """Export subject data to a .csv file
    :param s: subject object
    :param filename: full path to the destination file
    """
    fields = ('Sub Num', 'Months', 'Sex', 'Trial Order', 'Trial Number', 'Prescreen Notes',
              'Left Image', 'Center Image', 'Right Image', 'Target Side', 'Condition',
              'Time', 'Time Centered', 'Accuracy')

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, dialect='excel')
        writer.writeheader()

        # one row per frame
        data = {
            'Sub Num': s['Number'],
            'Months': '{:0.1f}'.format(age_months(s['Birthday'], s['Date of Test'])),
            'Sex': s['Sex'],
            'Trial Order': s.trial_order.name(),
            'Prescreen Notes': s['Notes']
        }

        for trial, events in s.events.trials().items():
            trial_info = s.trial_order.data.get(trial, {})
            data.update({
                'Trial Number': trial,
                'Left Image': trial_info.get('Left Image', ''),
                'Center Image': trial_info.get('Center Image', ''),
                'Right Image': trial_info.get('Right Image', ''),
                'Target Side': trial_info.get('Target Side', ''),
                'Condition': trial_info.get('Condition', '')
            })
            critical_onset = trial_info.get('Critical Onset', 0)
            # round critical onset to nearest frame
            critical_onset = frame2ms(ms2frames(critical_onset))

            trial_frames = int(trial_info.get('Trial End', 0) / 100 * 3)
            event_start = 0
            for e in range(len(events)):
                try:
                    event_end = events[e + 1].frame - events[0].frame
                except IndexError:
                    event_end = trial_frames

                accuracy = compute_accuracy(data['Target Side'], events[e].response)

                for frame in range(event_start, event_end):
                    data.update({
                        'Time': '{:.2f}'.format(frame2ms(frame)),
                        'Time Centered': '{:.2f}'.format(frame2ms(frame) - critical_onset),
                        'Accuracy': accuracy
                    })
                    writer.writerow(data)
                event_start = event_end


def export_wide(filename, s: Subject):
    """Export subject data to a .csv file in "wide" format (the old iCoder style)
    :param s: subject object
    :param filename: full path to the destination file
    """
    columns = ['Sub Num', 'Months', 'Sex', 'Order', 'Tr Num', 'Prescreen Notes',
               'L-image', 'C-image', 'R-image', 'Target Side', 'Target Image', 'Condition',
               'CritOnset']
    # remaining columns are for each frame
    # F0 = critical onset
    # F33 = next frame
    # F-33 = previous frame


    # Use critical onset and trial duration from the first trial to prepare headers
    trials = s.trial_order.data.keys()
    first_trial = sorted(list(trials))[0]
    trial_info = s.trial_order.data.get(first_trial, {})
    critical_onset = trial_info.get('Critical Onset', 0)
    # round critical onset to nearest frame
    critical_onset_frames = ms2frames(critical_onset)
    critical_onset = frame2ms(critical_onset_frames)

    trial_frames = int(trial_info.get('Trial End', 0) / 100 * 3)

    # base number of frames on coded frames
    max_trial_frames = max([events[-1].frame - events[0].frame for trial, events in s.events.trials().items()])



    frame_columns = ['F{:.0f}'.format(frame2ms(f - critical_onset_frames)) for f in range(max_trial_frames)]

    fields = columns + frame_columns

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, dialect='excel')
        writer.writeheader()

        for trial, events in s.events.trials().items():
            trial_info = s.trial_order.data.get(trial, {})
            data = {
                'Sub Num': s['Number'],
                'Months': '{:0.1f}'.format(age_months(s['Birthday'], s['Date of Test'])),
                'Sex': s['Sex'],
                'Order': s.trial_order.name(),
                'Tr Num': trial,
                'Prescreen Notes': s['Notes'],
                'L-image': trial_info.get('Left Image', ''),
                'C-image': trial_info.get('Center Image', ''),
                'R-image': trial_info.get('Right Image', ''),
                'Target Side': trial_info.get('Target Side', ''),
                'Condition': trial_info.get('Condition', ''),
                'CritOnset': trial_info.get('Critical Onset', 0)
            }

            event_start = 0
            for e in range(len(events)):
                try:
                    event_end = events[e + 1].frame - events[0].frame
                except IndexError:
                    event_end = trial_frames

                accuracy = compute_accuracy(data['Target Side'], events[e].response)

                for frame in range(event_start, event_end):
                    frame_ms = frame2ms(frame) - critical_onset
                    data['F{:.0f}'.format(frame_ms)] = accuracy
                event_start = event_end
            writer.writerow(data)
