
from peyecoder.models import Subject
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
    if (target == 'R' and response == 'right') or (target == 'L' and response == 'left'):
        accuracy = 1
    elif target in ('R', 'L') and response == 'center':
        accuracy = 0.5
    elif target in ('R', 'L') and response in ('right', 'left'):
        accuracy = 0
    elif response == 'away':
        accuracy = '-'
    elif response == 'off':
        accuracy = '.'
    else:
        accuracy = 'N/A'
    return accuracy


def export(filename, s: Subject, format='long', invert_rl=False):
    """Export subject data to a .csv file
    :param s: subject object
    :param filename: full path to the destination file
    :param format: 'wide' or 'long' format for the export file
    :param invert_rl: if True, invert target location in trial order
    """
    if format == 'long':
        export_long(filename, s, invert_rl)
    elif format == 'wide':
        export_wide(filename, s, invert_rl)


def export_long(filename, s: Subject, invert_rl):
    """Export subject data to a .csv file
    :param s: subject object
    :param filename: full path to the destination file
    :param invert_rl: if True, invert target location in trial order
    """
    fields = ('Sub Num', 'Months', 'Sex', 'Trial Order', 'Trial Number', 'Prescreen Notes',
              'Left Image', 'Center Image', 'Right Image', 'Target Side', 'Condition',
              'Time', 'Time Centered', 'Response', 'Accuracy')

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, dialect='excel')
        writer.writeheader()

        # one row per frame
        data = {
            'Sub Num': s['Number'],
            'Months': '{:0.1f}'.format(age_months(s['Birthday'], s['Date of Test'])),
            'Sex': s.get_sex_display(),
            'Trial Order': s.trial_order.name(),
            'Prescreen Notes': s['Notes']
        }

        trial_events = s.events.trials()
        for trial_info in s.trial_order.data:
            trial_number = trial_info['Trial Number']
            critical_onset_rounded = frame2ms(ms2frames(trial_info['Critical Onset']))
            events = trial_events.get(trial_number, [])

            data.update({
                'Trial Number': trial_number,
                'Left Image': trial_info.get('Left Image', ''),
                'Center Image': trial_info.get('Center Image', ''),
                'Right Image': trial_info.get('Right Image', ''),
                'Target Side': trial_info.inverted_target() if invert_rl else trial_info.get('Target Side', ''),
                'Condition': trial_info.get('Condition', '')
            })

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
                        'Time Centered': '{:.2f}'.format(frame2ms(frame) - critical_onset_rounded),
                        'Response': events[e].response,
                        'Accuracy': accuracy
                    })
                    writer.writerow(data)
                event_start = event_end


def export_wide(filename, s: Subject, invert_rl):
    """Export subject data to a .csv file in "wide" format (the old iCoder style)
    :param s: subject object
    :param filename: full path to the destination file
    :param invert_rl: If true, invert target location in trial order
    """
    columns = ['Sub Num', 'Months', 'Sex', 'Order', 'Tr Num', 'Prescreen Notes',
               'L-image', 'C-image', 'R-image', 'Target Side', 'Target Image', 'Condition',
               'CritOnset']

    # remaining columns are for each frame
    # ...
    # F-33 : frame before critical onset
    # F0   : critical onset
    # F33  : next frame
    # ...

    # critical onset frames for each trial in trial order (trials may be repeated)
    trial_cof = [(trial['Trial Number'], ms2frames(trial['Critical Onset'])) for trial in s.trial_order.data]
    if trial_cof:
        max_pre_onset = max([cof for t, cof in trial_cof])
        # number of frames coded for each trial
        trial_frames = {t: events[-1].frame - events[0].frame for t, events in s.events.trials().items()}
        # frames after critical onset coded for each trial
        post_onset_frames = [trial_frames.get(t, 0) - cof for t, cof in trial_cof]
        max_post_onset = max(post_onset_frames)

        frame_columns = ['F{:.0f}'.format(frame2ms(f - max_pre_onset)) for f in range(max_pre_onset + max_post_onset)]
    else:
        frame_columns = []

    fields = columns + frame_columns

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, dialect='excel')
        writer.writeheader()

        trial_events = s.events.trials()
        for trial_info in s.trial_order.data:
            trial_number = trial_info['Trial Number']
            critical_onset_rounded = frame2ms(ms2frames(trial_info['Critical Onset']))
            events = trial_events.get(trial_number, [])

            data = {
                'Sub Num': s['Number'],
                'Months': '{:0.1f}'.format(age_months(s['Birthday'], s['Date of Test'])),
                'Sex': s.get_sex_display(),
                'Order': s.trial_order.name(),
                'Tr Num': trial_number,
                'Prescreen Notes': s['Notes'],
                'L-image': trial_info['Left Image'],
                'C-image': trial_info['Center Image'],
                'R-image': trial_info['Right Image'],
                'Target Side': trial_info.inverted_target() if invert_rl else trial_info['Target Side'],
                'Condition': trial_info['Condition'],
                'CritOnset': trial_info['Critical Onset']
            }

            event_start = 0
            for e in range(len(events)):
                try:
                    event_end = events[e + 1].frame - events[0].frame
                except IndexError:
                    event_end = trial_frames.get(trial_number, 0)

                accuracy = compute_accuracy(data['Target Side'], events[e].response)

                for frame in range(event_start, event_end):
                    frame_ms = frame2ms(frame) - critical_onset_rounded
                    data['F{:.0f}'.format(frame_ms)] = accuracy
                event_start = event_end
            writer.writerow(data)
