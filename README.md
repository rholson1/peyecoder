# peyecoder
An open-source program for coding eye movements.

Running
--
If peyecoder has been installed from PyPI using `pip install peyecoder` then peyecoder can be run using the installed
script `peyecoder-gui`.

If the code repository has been downloaded from GitHub, run peyecoder from the project directory:

```
python run-peyecoder.py
```

Alternatively, a single-file executable of peycoder can be downloaded from a GitHub release.

Dependencies
--
- **PySide2**: Qt for Python
- **opencv-python-headless**: Computer vision library used to read videos   
- **timecode**: library for SMTPE timecode computations
- **PyAudio**: library used to playback audio
- **sortedcontainers**: data structures which maintain sort order
- **python-dateutil**: date utilities

additionally, **ffmpeg** should be installed and in the path. 

Citing Peyecoder
--
Olson, R. H., Pomper, R., Potter, C. E., Hay, J. F., Saffran, J. R., Ellis Weismer, S., & Lew-Williams, C. (2020). Peyecoder: An open-source program for coding eye movements. Zenodo. http://doi.org/10.5281/zenodo.4313832

[![DOI](https://zenodo.org/badge/242180640.svg)](https://zenodo.org/badge/latestdoi/242180640)
