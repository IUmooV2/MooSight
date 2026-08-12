# MooSight on Windows

MooSight currently uses Python 3.10 as the conservative Windows runtime while the modernization branch expands compatibility testing to newer Python releases.

## Quick start

1. Download or clone the complete MooSight repository.
2. Double-click `MooSight-Windows.bat`.
3. If Python 3.10 is missing, the launcher attempts to install it with Windows Package Manager (`winget`).
4. On the first launch, the script creates an isolated `.venv`, upgrades packaging tools, and installs `requirements.txt`.
5. The launcher runs `pip check` and MooSight's preflight diagnostics before startup.
6. MooSight starts through `moosight.py`, which routes both the command-line/web core and scan workers through `ModernSpiderFoot` while retaining SpiderFoot's existing application behavior.
7. The local web interface opens at `127.0.0.1:5001`.

The local address is:

`http://127.0.0.1:5001`

## Why `moosight.py`?

`sf.py` and `sfscan.py` still contain substantial legacy SpiderFoot startup and scanning behavior. Rewriting them all at once would create unnecessary regression risk. The MooSight entry point installs the modern core at startup so networking can be modernized and tested independently while the proven legacy orchestration code remains intact.

This is a transitional architecture. Once the modern core is fully validated, duplicated legacy networking code can be removed from `sflib.py` and the compatibility layer can be simplified.

## What the preflight checks do

Before starting the web interface, the launcher checks key runtime prerequisites such as repository completeness, installed dependencies, writable runtime directories, SQLite database integrity when a database exists, and whether the configured local port is already occupied.

## Stopping MooSight

Return to the launcher window and press `Ctrl+C`.

## Resetting the environment

If package installation becomes damaged, close MooSight, delete the `.venv` folder, and run `MooSight-Windows.bat` again. The environment will be recreated from the repository's declared dependencies.

## Why Python 3.10?

Python 3.10 remains the required compatibility baseline until the modernization test suite proves newer runtimes against MooSight's complete dependency and module set. A Python 3.11 compatibility probe has been added to the development CI configuration, and newer versions should become required only after their failures are understood and resolved.

## Security note

The launcher binds MooSight only to `127.0.0.1`, so the web interface is local to the computer by default. Do not change the bind address to a public or network-facing interface without deliberate access controls.

Normal HTTPS requests in the modern networking layer verify TLS certificates by default. Modules that genuinely need to inspect an invalid or untrusted certificate must opt into unverified TLS behavior for that specific operation rather than weakening HTTPS process-wide.

Use OSINT and scanning functionality only on systems, accounts, domains, and other targets you own or are authorized to assess.
