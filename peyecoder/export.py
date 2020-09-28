
from peyecoder.models import Subject
import csv
from dateutil import parser
from math import floor

INVERT_TRIAL_ORDER = 1
INVERT_RESPONSE = 2
INVERSION = {INVERT_TRIAL_ORDER: 'Trial Order', INVERT_RESPONSE: 'Response'}


def frame2ms(f, frame_rate=30):
    """Convert a frame number to a time in ms"""
    return f * 1000 / frame_rate


def ms2frames(ms, frame_rate=30):
    """Convert a time (in ms) to frames, rounding down"""
    return floor(ms * frame_rate / 1000)


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
    if target in ('R', 'L', 'N'):
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
    else:
        # Nonstandard coding
        if target.lower() == response.lower():
            accuracy = 1
        elif response.lower() == 'away':
            accuracy = '-'
        elif response.lower() == 'off':
            accuracy = '.'
        else:
            accuracy = 0
    return accuracy


def export(filename, s: Subject, format='long', invert_rl=INVERT_TRIAL_ORDER):
    """Export subject data to a .csv file
    :param s: subject object
    :param filename: full path to the destination file
    :param format: 'wide' or 'long' format for the export file
    :param invert_rl: controls which L-R elements get inverted in output file
    """
    if format == 'long':
        export_long(filename, s, invert_rl)
    elif format == 'wide':
        export_wide(filename, s, invert_rl)


def export_long(filename, s: Subject, invert_rl):
    """Export subject data to a .csv file
    :param s: subject object
    :param filename: full path to the destination file
    :param invert_rl: controls which L-R elements get inverted in output file
    """
    fields = ('Sub Num', 'Months', 'Sex', 'Trial Order', 'Trial Number', 'Prescreen Notes',
              'Left Image', 'Center Image', 'Right Image', 'Target Side', 'Inversion', 'Condition',
              'Time', 'Time Centered', 'Response', 'Accuracy')

    frame_rate = round(s['Framerate'])

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, dialect='excel')
        writer.writeheader()

        # one row per frame
        data = {
            'Sub Num': s['Number'],
            'Months': '{:0.1f}'.format(age_months(s['Birthday'], s['Date of Test'])),
            'Sex': s.get_sex_display(),
            'Trial Order': s.trial_order.name(),
            'Prescreen Notes': s['Notes'],
            'Inversion': INVERSION[invert_rl]
        }

        trial_events = s.events.trials()
        unused = s.trial_order.unused + s.reasons.unused()
        prescreen_reasons = s.reasons.unused_reasons()

        for trial_info in s.trial_order.data:
            trial_number = trial_info['Trial Number']
            if trial_number in unused:
                continue

            critical_onset_rounded = frame2ms(ms2frames(trial_info['Critical Onset'], frame_rate), frame_rate)
            events = trial_events.get(trial_number, [])

            if invert_rl == INVERT_TRIAL_ORDER:
                target_side = trial_info.inverted_target()
                l_image = trial_info['Right Image']
                r_image = trial_info['Left Image']
            else:
                target_side = trial_info['Target Side']
                l_image = trial_info['Left Image']
                r_image = trial_info['Right Image']

            data.update({
                'Trial Number': trial_number,
                'Left Image': l_image,
                'Center Image': trial_info.get('Center Image', ''),
                'Right Image': r_image,
                'Target Side': target_side,
                'Condition': trial_info.get('Condition', ''),
                'Prescreen Notes': prescreen_reasons.get(trial_number, '')
            })

            trial_frames = int(trial_info.get('Trial End', 0) / 100 * 3)
            event_start = 0
            for e in range(len(events)):
                try:
                    event_end = events[e + 1].frame - events[0].frame
                except IndexError:
                    event_end = trial_frames

                if invert_rl == INVERT_RESPONSE:
                    response = events[e].inverted_response()
                else:
                    response = events[e].response

                accuracy = compute_accuracy(data['Target Side'], response)

                for frame in range(event_start, event_end):
                    data.update({
                        'Time': '{:.2f}'.format(frame2ms(frame, frame_rate)),
                        'Time Centered': '{:.2f}'.format(frame2ms(frame, frame_rate) - critical_onset_rounded),
                        'Response': response,
                        'Accuracy': accuracy
                    })
                    writer.writerow(data)
                event_start = event_end


def export_wide(filename, s: Subject, invert_rl):
    """Export subject data to a .csv file in "wide" format (the old iCoder style)
    :param s: subject object
    :param filename: full path to the destination file
    :param invert_rl: controls which L-R elements get inverted in output file
    """
    columns = ['Sub Num', 'Months', 'Sex', 'Order', 'Tr Num', 'Prescreen Notes',
               'L-image', 'C-image', 'R-image', 'Target Side', 'Target Image', 'Inversion', 'Condition',
               'CritOnset']

    frame_rate = round(s['Framerate'])

    # remaining columns are for each frame
    # ...
    # F-33 : frame before critical onset
    # F0   : critical onset
    # F33  : next frame
    # ...

    # critical onset frames for each trial in trial order (trials may be repeated)
    trial_cof = [(trial['Trial Number'], ms2frames(trial['Critical Onset'], frame_rate)) for trial in s.trial_order.data]
    if trial_cof:
        max_pre_onset = max([cof for t, cof in trial_cof])
        # number of frames coded for each trial
        trial_frames = {t: events[-1].frame - events[0].frame for t, events in s.events.trials().items()}
        # frames after critical onset coded for each trial
        post_onset_frames = [trial_frames.get(t, 0) - cof for t, cof in trial_cof]
        max_post_onset = max(post_onset_frames)

        frame_columns = ['F{:.0f}'.format(frame2ms(f - max_pre_onset, frame_rate)) for f in range(max_pre_onset + max_post_onset)]
    else:
        frame_columns = []

    fields = columns + frame_columns

    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, dialect='excel')
        writer.writeheader()

        trial_events = s.events.trials()
        unused = s.trial_order.unused + s.reasons.unused()
        prescreen_reasons = s.reasons.unused_reasons()
        for trial_info in s.trial_order.data:
            trial_number = trial_info['Trial Number']
            if trial_number in unused:
                continue
            critical_onset_rounded = frame2ms(ms2frames(trial_info['Critical Onset'], frame_rate), frame_rate)
            events = trial_events.get(trial_number, [])

            if invert_rl == INVERT_TRIAL_ORDER:
                target_side = trial_info.inverted_target()
                l_image = trial_info['Right Image']
                r_image = trial_info['Left Image']
            else:
                target_side = trial_info['Target Side']
                l_image = trial_info['Left Image']
                r_image = trial_info['Right Image']

            target_image = l_image if target_side == 'L' else r_image

            data = {
                'Sub Num': s['Number'],
                'Months': '{:0.1f}'.format(age_months(s['Birthday'], s['Date of Test'])),
                'Sex': s.get_sex_display(),
                'Order': s.trial_order.name(),
                'Tr Num': trial_number,
                'Prescreen Notes': prescreen_reasons.get(trial_number, ''),
                'L-image': l_image,
                'C-image': trial_info['Center Image'],
                'R-image': r_image,
                'Target Side': target_side,
                'Target Image': target_image,
                'Inversion': INVERSION[invert_rl],
                'Condition': trial_info['Condition'],
                'CritOnset': trial_info['Critical Onset']
            }

            event_start = 0
            for e in range(len(events)):
                try:
                    event_end = events[e + 1].frame - events[0].frame
                except IndexError:
                    event_end = trial_frames.get(trial_number, 0)

                if invert_rl == INVERT_RESPONSE:
                    response = events[e].inverted_response()
                else:
                    response = events[e].response
                accuracy = compute_accuracy(data['Target Side'], response)

                for frame in range(event_start, event_end):
                    frame_ms = frame2ms(frame, frame_rate) - critical_onset_rounded
                    data['F{:.0f}'.format(frame_ms)] = accuracy
                event_start = event_end
            writer.writerow(data)
