import wave
import pyaudio
import time


class AudioPlayer:
    def __init__(self, source):
        self.reader = wave.open(source, 'rb')
        self.params = self.reader.getparams()  # (nchannels, sampwidth, framerate, nframes, comptype, compname)

        self.p = pyaudio.PyAudio()
        self.player = None
        self.start_player()

    def start_player(self):
        def callback(in_data, frame_count, time_info, status):
            if self.playing:
                data = self.reader.reader.readframes(1024)
                return data, pyaudio.paContinue
            else:
                return None, pyaudio.paContinue

        self.player = self.p.open(format=self.p.get_format_from_width(self.reader.params.sampwidth),
                                  channels=self.reader.params.nchannels,
                                  rate=self.reader.params.framerate,
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
        pos = frame
        self.reader.setpos(pos)

    def play(self):
        self.playing = True

    def stop(self):
        self.playing = False





if __name__ == '__main__':

    # Test AudioReader

    p = pyaudio.PyAudio()


    source = r'M:\work\iCoder\sample_data\output-audio.wav'
    with AudioPlayer(source) as reader:
        print(reader.params)
        stream = p.open(format=p.get_format_from_width(reader.params.sampwidth),
                        channels=reader.params.nchannels,
                        rate=reader.params.framerate,
                        output=True,
                        stream_callback=callback)
        stream.start_stream()
        while stream.is_active():
            time.sleep(0.1)
        stream.stop_stream()
        stream.close()

        # blocking mode
        #data = reader.reader.readframes(1024)
        #while len(data) > 0:
        #    stream.write(data)
        #    data = reader.reader.readframes(1024)
        #stream.stop_stream()
        #stream.close()
        p.terminate()


