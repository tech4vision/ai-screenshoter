# ai-screenshoter
Ai Screenshooter App - lastshot.ai


## Upload process
rm -rf dist
source .venv/bin/activate
python -m build
twine upload dist/*
paste the token from file pypi-screenshoter-api-token.txt

## Upgrade the lib
pipx upgrade ai-screenshooter