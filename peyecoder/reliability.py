
from peyecoder.models import Subject
from dateutil import parser

SHIFT_AGREEMENT_THRESHOLD = 1


def normalize_response(response):
    """ Transform response so that 'off' == 'away' """
    if response == 'away':
        return 'off'
    else:
        return response


def compute_frame_agreement(s1, s2):
    """Compute percentage of frames with the same response, considering all (common) coded frames.
    'away' and 'off' responses are considered equivalent
    """
    s1_frames = s1.events.frames()
    s2_frames = s2.events.frames()

    total_frames = 0
    same_frames = 0
    for f, resp in s1_frames.items():
        try:
            resp2 = s2_frames[f]
            total_frames += 1  # only increments if a frame is in both sets of frames
        except KeyError:
            resp2 = ''
        if normalize_response(resp) == normalize_response(resp2):
            same_frames += 1
    pct_frame_agreement = same_frames / total_frames * 100 if total_frames else 0
    return pct_frame_agreement


def render_timecode(timecode, offsets, frame):
    """Render a timecode (e.g. 00:01:04.27)
    :param timecode: Timecode object (with predefined framerate, drop_frame)
    :param offsets: Offsets object which contains frame offsets so timecodes match video
    :param frame: Frame number
    """
    timecode.frames = frame + 1 + offsets.get_offset(frame)
    return str(timecode)


def timing_error(timecode, s1, s2, trial, frame_1, frame_2):
    """Generate the error message for a timing error"""
    difference = frame_1 - frame_2
    timecode_1 = render_timecode(timecode, s1.timecode_offsets, frame_1)
    timecode_2 = render_timecode(timecode, s2.timecode_offsets, frame_2)
    suffix = 's' if abs(difference) > 1 else ''
    word = 'later' if difference > 0 else 'earlier'
    diff_str = '{} frame{} {}'.format(abs(difference), suffix, word)
    return "Trial {}: Your response at {} is {} than the other subject's response at {}.".format(trial, timecode_1, diff_str, timecode_2)

def response_error(timecode, s1, s2, trial, frame_1, frame_2):
    """Generate the error message for a response error"""
    timecode_1 = render_timecode(timecode, s1.timecode_offsets, frame_1)
    timecode_2 = render_timecode(timecode, s2.timecode_offsets, frame_2)
    return "Trial {}: Your response at {} is not similar to the other subject's response at {}.".format(trial, timecode_1, timecode_2)


def reliability_report(s1: Subject, s2: Subject, timecode):
    """Create a reliability report
    :param s1: Subject object containing "your" coding
    :param s2: Subject object containing "other" coding
    :param timecode: Timecode object used to render timecodes from frame numbers
    :return: Reliability report as an array of strings
    """
    report = []

    # make sure subjects are the same:
    if not subjects_are_comparable(s1, s2):
        report.append('Subject number, birthdate, date of test, and order must all match. Cannot compare the subjects.')
        return report

    s1_trials = s1.events.trials()
    s2_trials = s2.events.trials()

    s1_trial_set = set(s1_trials.keys())
    s2_trial_set = set(s2_trials.keys())

    # s1_only = s1_trial_set.difference(s2_trial_set)
    # s2_only = s2_trial_set.difference(s1_trial_set)
    #
    # for t in s1_only:
    #     report.append('Trial {} appears only in file 1, so cannot be compared.'.format(t))
    # for t in s2_only:
    #     report.append('Trial {} appears only in file 2, so cannot be compared.'.format(t))

    common_trials = set.intersection(s1_trial_set, s2_trial_set)
    common_trials = sorted(list(common_trials))

    # Shift Agreement
    total_shifts = 0
    same_shifts = 0

    comparable = 0
    for t in common_trials:
        t1 = s1_trials[t]
        t2 = s2_trials[t]
        if len(t1) == len(t2):
            comparable += 1
            # Trials are comparable, so compute

            for i in range(len(t1)):
                if i in (0, len(t1) - 1):
                    # This is a fixed event.  Do not compare for shift agreement, but still must be identical.
                    # check for time stamp agreement: frame must be identical
                    difference = t1[i].frame - t2[i].frame
                    if difference:
                        report.append(timing_error(timecode, s1, s2, t, t1[i].frame, t2[i].frame))
                    # check for response agreement
                    if normalize_response(t1[i].response) != normalize_response(t2[i].response):
                        report.append(response_error(timecode, s1, s2, t, t1[i].frame, t2[i].frame))
                else:
                    # not a fixed event.
                    if normalize_response(t1[i].response) == normalize_response(t2[i].response):
                        if t1[i].response == 'away':
                            pass
                        elif t1[i].response == 'off' and t1[i-1].response == 'away':
                            pass
                        else:
                            total_shifts += 1
                            if abs(t1[i].frame - t2[i].frame) <= SHIFT_AGREEMENT_THRESHOLD:
                                same_shifts += 1
                            else:
                                report.append(timing_error(timecode, s1, s2, t, t1[i].frame, t2[i].frame))
                    else:
                        total_shifts += 1
                        # response error
                        report.append(response_error(timecode, s1, s2, t, t1[i].frame, t2[i].frame))

                        if abs(t1[i].frame - t2[i].frame) <= SHIFT_AGREEMENT_THRESHOLD:
                            same_shifts += 1
                        else:
                            # timing error
                            report.append(timing_error(timecode, s1, s2, t, t1[i].frame, t2[i].frame))
        else:
            report.append(('Trial {}: Your subject had {} responses, while the other subject had {} responses.'
                           ' Cannot compare this trial.').format(t, len(t1), len(t2)))

    pct_comparable = comparable / len(common_trials) * 100 if common_trials else 0
    pct_shift_agreement = same_shifts / total_shifts * 100 if total_shifts else 0

    pct_frame_agreement = compute_frame_agreement(s1, s2)

    report.append('----------------------------------')
    report.append('Frame agreement: {:.2f}%'.format(pct_frame_agreement))
    report.append('Comparable trials: {:.2f}%'.format(pct_comparable))
    report.append('Shift agreement: {:.2f}%'.format(pct_shift_agreement))
    return report


def str2date(datestr):
    """Use dateutil.parser to convert a string to a date"""
    return parser.parse(datestr, dayfirst=False).date()


def subjects_are_comparable(s1: Subject, s2: Subject):
    """ Return true if subjects can be compared"""
    date_fields = ('Birthday', 'Date of Test')
    fields = ('Number', 'Order')
    comparable = all([str(s1[f]) == str(s2[f]) for f in fields]) and \
        all([str2date(s1[f]) == str2date(s2[f]) for f in date_fields])

    return comparable







