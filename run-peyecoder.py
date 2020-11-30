import peyecoder.gui
import sys

# Temporary workaround for bug with displaying QT windows in MacOS Big Sur.
import _tkinter

if __name__ == "__main__":
    peyecoder.gui.run(sys.argv)

