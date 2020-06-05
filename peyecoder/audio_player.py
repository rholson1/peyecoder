import wave
import pyaudio
import os
from peyecoder.av_utils import extract_sound


def noop(*args, **kwargs):
    return None


class VideoAudioPlayer:
    """Player to play the audio from a video.
    """
    _player_methods = ['seek', 'play', 'stop']

    def __init__(self):

        self.video_filename = ''
        self.audio_filename = ''
        self.audio_player = None

    # Release the video source when the object is destroyed
    def __del__(self):
        self.cleanup()

    def set_video_source(self, video_source, frame_rate):
        if self.audio_player:
            self.cleanup()
        self.audio_filename = extract_sound(video_source)
        self.audio_player = AudioPlayer(self.audio_filename, frame_rate)

    def cleanup(self):
        """Cleanup - delete temporary files and cleanup audio stream"""
        if self.audio_player:
            self.audio_player.close()
        if self.audio_filename:
            os.remove(self.audio_filename)

    def __getattr__(self, item):
        if item in self._player_methods:
            if self.audio_player:
                return getattr(self.audio_player, item)
            else:
                return noop


class AudioPlayer:
    def __init__(self, audio_filename, steps_per_second=30):
        """
        :param audio_filename: filename of the audio file to be played
        :param steps_per_second: size of steps used for navigation in file, specified as a rate.  Corresponds to the
        framerate of the corresponding video
        """
        self.reader = wave.open(audio_filename, 'rb')
        self.params = self.reader.getparams()  # (nchannels, sampwidth, framerate, nframes, comptype, compname)
        self.chunk_size = int(self.params.framerate / steps_per_second)

        self.p = pyaudio.PyAudio()
        self.player = None
        self.playing = False
        self.start_player()

    def start_player(self):
        def callback(in_data, frame_count, time_info, status):
            if self.playing:
                data = self.reader.readframes(self.chunk_size)
            else:
                data = b'\x00' * 4 * frame_count
            return data, pyaudio.paContinue

        self.player = self.p.open(format=self.p.get_format_from_width(self.params.sampwidth),
                                  channels=self.params.nchannels,
                                  rate=self.params.framerate,
                                  frames_per_buffer=self.chunk_size,
                                  output=True,
                                  stream_callback=callback)
        self.player.start_stream()

    def close(self):
        # cleanup audio player
        self.player.stop_stream()
        self.player.close()
        self.p.terminate()

        # cleanup audio reader
        self.reader.close()

    # __enter__ and __exit__ methods make AudioReader a context manager, allowing use in a 'with' block
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def seek(self, frame):
        pos = frame * self.chunk_size
        self.reader.setpos(pos)

    def tell(self):
        return self.reader.tell() / self.chunk_size

    def play(self):
        self.playing = True

    def stop(self):
        self.playing = False

