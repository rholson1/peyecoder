# Utilities for working with data and template files

import plistlib


def load_datafile(filename):
    """Load a data file and return the contents as a dictionary """
    with open(filename, 'rb') as f:
        data = plistlib.load(f)
    return data


def save_datafile(filename, data):
    """Save data to a datafile"""
    with open(filename, 'wb') as f:
        plistlib.dump(data, f)

