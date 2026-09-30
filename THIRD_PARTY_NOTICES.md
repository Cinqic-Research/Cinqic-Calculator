# Third-party notices

Cinqic Calculator is licensed under the Apache License 2.0 (see
[LICENSE](LICENSE) and [NOTICE](NOTICE)). That license covers the code and
assets in this repository that Cinqic owns. Components listed below are **not**
owned by Cinqic and remain under their own licenses.

## Runtime

### Core (all platforms)

The shared calculation, conversion, financial, history, settings, and storage
logic in `src/cinqic_calculator/` has **no third-party runtime dependencies** —
it is pure Python standard library.

### Desktop (Windows, Linux)

| Component | License | Notes |
| --- | --- | --- |
| [CPython](https://www.python.org/) | Python Software Foundation License 2.0 | Bundled into the packaged builds by PyInstaller. |
| [Tcl/Tk](https://www.tcl-lang.org/) | Tcl/Tk License (BSD-style) | Used via the standard library's `tkinter`; bundled into the packaged builds. |

The packaged Windows and Linux builds are produced with
[PyInstaller](https://pyinstaller.org/) (GPL-2.0-or-later **with** a bootloader
exception that explicitly permits distributing the resulting applications under
any license of your choosing). PyInstaller itself is a build tool and is not
distributed as part of the application; the bootloader it embeds is covered by
that exception.

### Android

| Component | License | Notes |
| --- | --- | --- |
| [Kivy](https://kivy.org/) | MIT | UI toolkit for the Android frontend. |
| [python-for-android](https://github.com/kivy/python-for-android) | MIT | Packaging toolchain; bundles CPython and supporting native libraries into the APK. |
| [SDL2](https://www.libsdl.org/) | Zlib | Window, input, and rendering backend used by Kivy. |
| [Roboto](https://fonts.google.com/specimen/Roboto) and [DejaVu Sans](https://dejavu-fonts.github.io/) | Apache-2.0 and DejaVu Fonts License (Bitstream Vera derivative), respectively | Shipped with Kivy and used for on-screen text. No additional font is added by this app. |

Kivy, python-for-android, and their dependencies do not add any network,
analytics, or telemetry behavior, and none is added by this application. The
Android app requests no permissions.

## Build and development only

These are used to test, lint, and package the application. They are not
redistributed as part of it.

| Component | License |
| --- | --- |
| [pytest](https://pytest.org/) | MIT |
| [Ruff](https://docs.astral.sh/ruff/) | MIT |
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0-or-later with bootloader exception |
| [Buildozer](https://github.com/kivy/buildozer) | MIT |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Inno Setup License (BSD-style) |

## Assets

The Cinqic Calculator icon, emblem, and wordmark in `assets/` are original
works owned by Cinqic and are covered by this repository's Apache-2.0 license.
The Cinqic name and logo are not trademarks licensed for use in derivative
works; see the Apache-2.0 license's trademark clause (section 6).
