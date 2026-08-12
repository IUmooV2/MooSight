# MooSight on Windows

This fork tracks the current SpiderFoot `master` branch. The upstream test workflow currently tests Python 3.7, 3.8, 3.9 and 3.10 on macOS and Linux, but does not include Windows. For a conservative Windows first run, this helper uses Python 3.10 in an isolated virtual environment.

## Quick start

1. Install **64-bit Python 3.10** from python.org if it is not already installed. Keep the Python Launcher (`py.exe`) enabled during installation.
2. Download or clone this repository.
3. Double-click `MooSight-Windows.bat`.
4. On the first launch, the script creates `.venv` and installs the packages in `requirements.txt`.
5. MooSight then starts on `127.0.0.1:5001` and opens the local web interface in your default browser.

The local address is:

`http://127.0.0.1:5001`

## Stopping MooSight

Return to the launcher window and press `Ctrl+C`.

## Resetting the environment

If package installation becomes damaged, close MooSight, delete the `.venv` folder, and run `MooSight-Windows.bat` again.

## Why Python 3.10?

The upstream GitHub Actions test matrix currently stops at Python 3.10. Some dependencies in `requirements.txt` are intentionally pinned to older major versions. Using Python 3.10 avoids changing upstream dependency behavior before the application has been validated on Windows.

## Security note

The launcher binds MooSight only to `127.0.0.1`, so the web interface is local to the computer by default. Do not change the bind address to a public/network-facing interface unless you understand the exposure and have appropriate access controls.

Use OSINT and scanning functionality only on systems, accounts, domains, and other targets you own or are authorized to assess.
