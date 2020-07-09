import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="peyecoder",
    version="1.0.2",
    author="Rob Olson",
    author_email="rolson@waisman.wisc.edu",
    description="Software for coding eye movements",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rholson1/peyecoder",
    packages=setuptools.find_packages(),
    entry_points={
        'gui_scripts': [
            "peyecoder-gui = peyecoder.gui:run",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        'numpy',
        'opencv-python-headless',
        'PyAudio',
        'PySide2',
        'python-dateutil',
        'sortedcontainers',
        'timecode'
    ]
)