# Utilities for working with data and template files

import plistlib


def load_datafile(filename):
    """Load a data file and return the contents as a dictionary """
    with open(filename, 'rb') as f:
        data = plistlib.load(f)
    return data


def save_datafile(filename, data):
    """Save data to a datafile"""
    try:
        with open(filename, 'wb') as f:
            plistlib.dump(data, f)
        return True
    except:
        return False


# Functions to convert dictionary with integer keys to string keys and vice versa
def stringify_keys(d):
    return {str(k): v for k, v in d.items()}


def intify_keys(d):
    """Convert string keys in a dictionary to integers"""
    return {int(k): v for k, v in d.items()}
