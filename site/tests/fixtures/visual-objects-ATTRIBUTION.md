Visual recognition test fixture

visual-objects.mp4 is a six-second synthetic still-image MP4, not an activity or motion dataset.
Source image: https://github.com/pjreddie/darknet/blob/master/data/dog.jpg
Repository author: Joseph Redmon. Source repository license declares Darknet public domain:
https://github.com/pjreddie/darknet/blob/master/LICENSE

The image visibly contains a dog, a bicycle and a parked vehicle. Tests exercise
actual browser object-model inference without claiming action recognition.
Reproduction: loop data/dog.jpg for six seconds, resize to 640x480, encode H.264/yuv420p
using FFmpeg with one thread and faststart. No content from creator accounts is used.
