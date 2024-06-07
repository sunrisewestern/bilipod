from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="bilipod",
    version="0.1.0",
    author="X Chen",
    author_email="chenxiaoxime@gmail.com",
    description="Make bilibili user or playlist into podcast",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sunrisewestern/bilipod",
    packages=find_packages(),
    install_requires=[
        "bilibili-api-python==16.2.0",
        "feedgen==1.0.0",
        "loguru==0.7.2",
        "PyYAML>=6.0",
        "requests>=2.27.1",
        "tinydb==4.8.0",
        "schedule==1.2.2",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GPL3 License",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "bilipod=bilipod:main",
        ],
    },
)
