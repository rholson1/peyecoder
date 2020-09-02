import cv2
from collections import deque


class VideoReader:
    def __init__(self, video_source=0):
        # Open the video source
        self.video_source = video_source
        self.vid = cv2.VideoCapture(video_source)
        if not self.vid.isOpened():
            raise ValueError("Unable to open video source", video_source)

        # Get video source properties
        self.width = self.vid.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = self.vid.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.frame_count = self.vid.get(cv2.CAP_PROP_FRAME_COUNT)
        self.frame_rate = self.vid.get(cv2.CAP_PROP_FPS)

    def get_frame(self):
        if self.vid.isOpened():
            ret, frame = self.vid.read()
            if ret:
                # Return a boolean success flag and the current frame converted to RGB from BGR
                return ret, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                return ret, None
        else:
            return False, None

    def seek(self, frame_number):
        # seek to a specific frame in the video
        self.vid.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    # Release the video source when the object is destroyed
    def __del__(self):
        if self.vid.isOpened():
            self.vid.release()

    def reset(self):
        # Close and reopen the video source to return to the beginning of the file.
        if self.vid.isOpened():
            self.vid.release()
        self.vid = cv2.VideoCapture(self.video_source)
        if not self.vid.isOpened():
            raise ValueError("Unable to open video source", self.video_source)


class BufferedVideoReader(VideoReader):
    """ Access a video using a buffer to allow stepping backward efficiently (up to the length of the buffer)"""
    def __init__(self, video_source, buffer_len=100):

        super().__init__(video_source=video_source)

        self.buffer_len = buffer_len
        self.buffer = deque([], self.buffer_len)
        self.frame_number = 0

        # initially, fill buffer
        for i in range(self.buffer_len):
            success, frame = self.get_frame()
            if success:
                self.buffer.append((self.frame_number, frame))
                self.frame_number += 1

        self.buffer_cursor = 0

        self.frame_number = self.buffer[0][0]  # should be 0
        self.frame = self.buffer[0][1]  # first frame of video

    def next(self, step=1):
        """ Get next frame, either from buffer or from file"""
        self.goto_framenumber(self.frame_number + step)

    def prev(self, step=1):
        """ Get previous frame, either from buffer or from file"""
        self.goto_framenumber(max(self.frame_number - step, 0))

    def goto_framenumber(self, target_frame):
        if target_frame < self.buffer[0][0]:
            # reload file to get to frame
            if target_frame < self.buffer_len:
                self.seek(0)
                # fill buffer
                for i in range(self.buffer_len):
                    success, frame = self.get_frame()
                    if success:
                        self.buffer.append((i, frame))
                self.buffer_cursor = target_frame
            else:
                # fill buffer, starting buffer_len frames before target
                self.seek(target_frame - self.buffer_len)
                for i in range(target_frame - self.buffer_len, target_frame + 1):
                    success, frame = self.get_frame()
                    if success:
                        self.buffer.append((i, frame))
                assert target_frame == self.buffer[-1][0]
                self.buffer_cursor = self.buffer_len - 1
        elif target_frame <= self.buffer[-1][0]:
            # frame is in buffer
            self.buffer_cursor = target_frame - self.buffer[0][0]
        else:
            # frame is not in buffer, so advance to it
            frame_number = self.buffer[-1][0]
            if target_frame - frame_number > self.buffer_len:
                self.seek(target_frame - self.buffer_len)
                for i in range(target_frame - self.buffer_len, target_frame + 1):
                    success, frame = self.get_frame()
                    if success:
                        self.buffer.append((i, frame))
                try:
                    assert target_frame == self.buffer[-1][0]
                except AssertionError:
                    print('Assertion error.  target_frame = {}, self.buffer[-1][0] = {}'.format(target_frame, self.buffer[-1][0]))
                self.buffer_cursor = self.buffer_len - 1
            else:
                for i in range(target_frame - self.buffer[-1][0]):
                    success, frame = self.get_frame()
                    if success:
                        frame_number += 1
                        self.buffer.append((frame_number, frame))

            self.buffer_cursor = self.buffer_len - 1
        self.frame_number, self.frame = self.buffer[self.buffer_cursor]

    def reload_buffer(self):
        """Reload the frames stored in the buffer to clear any old occluder images"""
        start_frame = self.buffer[0][0]
        self.seek(start_frame)
        for i in range(start_frame, start_frame + self.buffer_len):
            success, frame = self.get_frame()
            if success:
                self.buffer.append((i, frame))
        self.frame_number, self.frame = self.buffer[self.buffer_cursor]



