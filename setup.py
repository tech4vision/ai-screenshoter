from setuptools import setup, find_packages

setup(
    name="ai-screenshooter",
    version="1.2.2",
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
    author="Last Shot AI",
    author_email="support@lastshot.ai",
    description="A CLI tool to capture and send AI-powered screenshots",
    url="https://github.com/tech4vision/ai-screenshoter",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)