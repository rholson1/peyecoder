# peyecoder

## About peyecoder
Peyecoder is used for coding eye movements in looking-while-listening experiments.  It was designed
as a replacement for the now-outdated program iCoder developed at Stanford in the early 2000s.

## Installing peyecoder
There are three ways to obtain peyecoder.
- Download an executable version of the program attached to a [GitHub Release](https://github.com/rholson1/peyecoder/releases/).
- Install from the Python Package Index `pip install peyecoder` [TBD]
- Download the source code from GitHub
 
For audio playback, peyecoder requires that [ffmpeg](https://ffmpeg.org/) be available in the system path. 
 
### Building executable files for distribution
The executable files attached to releases are built using PyInstaller.
Steps to build an executable are:
- download the peyecoder source from GitHub
- create an associated venv and install peyecoder dependencies (see requirements.txt)
- install pyinstaller
- create a single-file executable using the command:
```
(venv) $ pyinstaller run-peyecoder.py --name peyecoder --onefile
```

