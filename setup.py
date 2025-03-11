from setuptools import setup, find_packages

setup(
    name="ai-screenshooter",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["ai_screenshot"],
    install_requires=[
        "pynput",
        "requests",
        "Pillow",
        "pygetwindow"
    ],
    entry_points={
        "console_scripts": [
            "ai-screenshooter=ai_screenshot:main",
        ],
    },
    author="Victor Oliveira",
    author_email="victor.soares@live.it",
    description="A CLI tool to capture and send AI-powered screenshots",
    url="https://github.com/tech4vision/ai-screenshoter",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)