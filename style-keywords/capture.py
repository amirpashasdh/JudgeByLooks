import os
import cv2
import numpy as np


def frame_changed(prev: np.ndarray | None, curr: np.ndarray, threshold: float = 0.15) -> bool:
    """Return True if the frame differs enough to warrant re-analysis."""
    if prev is None:
        return True
    prev_small = cv2.resize(prev, (64, 64)).astype(float)
    curr_small = cv2.resize(curr, (64, 64)).astype(float)
    diff = np.mean(np.abs(prev_small - curr_small)) / 255.0
    return diff > threshold


class FrameCapture:
    def __init__(self, source: int | str = 0):
        # validate video file path before opening
        if isinstance(source, str) and not source.isdigit():
            if not os.path.isfile(source):
                raise FileNotFoundError(
                    f"Video file not found: '{source}'\n"
                    f"Tip: make sure the path is correct, e.g. --source /path/to/video.mp4"
                )

        # on macOS, AVFoundation backend (700) works better than the default for cameras
        if isinstance(source, int):
            self.cap = cv2.VideoCapture(source, cv2.CAP_AVFOUNDATION)
        else:
            self.cap = cv2.VideoCapture(source)

        if not self.cap.isOpened():
            if isinstance(source, int):
                raise RuntimeError(
                    f"Cannot open camera (index {source}).\n"
                    f"  - Make sure your terminal has Camera permission:\n"
                    f"    System Settings → Privacy & Security → Camera → enable your terminal app\n"
                    f"  - Or run with a video file instead: python main.py --source video.mp4"
                )
            raise RuntimeError(f"Cannot open video source: {source}")

        self.is_video_file = isinstance(source, str)
        total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 0
        if self.is_video_file and total > 0:
            duration = total / fps if fps else 0
            print(f"[capture] video file — {total} frames, {fps:.1f} fps, ~{duration:.0f}s")

    def read(self) -> np.ndarray | None:
        ret, frame = self.cap.read()
        return frame if ret else None

    def release(self):
        self.cap.release()
