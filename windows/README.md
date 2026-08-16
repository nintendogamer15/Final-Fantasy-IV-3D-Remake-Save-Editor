# Windows portable build

Run `build.bat` on a Windows machine with Python 3.10 or newer. It creates an
isolated environment, installs PyInstaller and PySide6, and writes the portable
GUI to:

```text
windows\dist\FFIV3DSaveEditor.exe
```

The executable is self-contained. It may initially trigger Windows
SmartScreen because locally built and GitHub Actions binaries are unsigned.

Windows builds cannot be produced faithfully from Linux: PyInstaller packages
for the operating system on which it runs. The release workflow therefore uses
a native `windows-latest` GitHub runner.
