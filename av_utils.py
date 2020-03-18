"""Utilities for working with media

Goals:
 - extract wav file from a video
 - save in appropriate location (temp location?)
 - return filename
"""
import subprocess
from tempfile import NamedTemporaryFile


def assert_ffmpeg():
    # Check to see if ffmpeg runs
    try:
        subprocess.run(['ffmpeg', '-help'], check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


def extract_sound(video_filename):
    """Given the name of a video, extract the sound to a .wav file, and return the filename of the new file."""

    # Generate a filename for the temporary audio file
    with NamedTemporaryFile(suffix='.wav') as tf:
        wave_filename = tf.name

    # Extract the sound from the video using ffmpeg
    subprocess.run(['ffmpeg', '-i', video_filename, '-vn', wave_filename],
                   check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return wave_filename





