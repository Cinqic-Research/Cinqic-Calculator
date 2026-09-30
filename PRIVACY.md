# Privacy

Cinqic Calculator is designed to work entirely on your device.

## What the application does

- Does **not** require an account.
- Does **not** include advertising.
- Does **not** include analytics.
- Does **not** include telemetry.
- Does **not** transmit your calculations, history, or settings anywhere.
- Stores settings and (optionally) calculation history locally:
  - **Windows** — `%LOCALAPPDATA%\Cinqic\Calculator\`
  - **Linux** — `$XDG_DATA_HOME/Cinqic/Calculator/` (by default
    `~/.local/share/Cinqic/Calculator/`)
  - **Android** — the app's private storage
    (`Context.getFilesDir()`-equivalent, via Kivy's `user_data_dir`)
- Works fully offline. An internet connection is never required to use it.
  The Android app requests no internet permission at all.
- Does **not** include Juniper or any other AI model. Juniper is
  not integrated into Cinqic Calculator on any platform.

## Local data

Two small JSON files may exist in the application's private data directory
on any platform:

- `settings.json` — your theme, degree/radian mode, history preference, and
  interface preferences such as reduced motion and haptic feedback.
- `history.json` — recent calculations, if history saving is enabled.

Both files are written atomically and are readable/editable by you. Neither
is ever read by, or sent to, any server. Disabling "Save calculation
history" in Settings stops new history from being written; existing history
can be deleted from the History or Settings view at any time.

On Android, this data lives in the app's private storage, which no other
app can read, and which is deleted automatically when the app is
uninstalled — there is nothing left behind to clean up manually.

## Permissions (Android)

The Android app requests no permissions: no internet, no storage access
beyond its own private app directory, and nothing else. You can confirm
this yourself in [`android/buildozer.spec`](android/buildozer.spec)
(`android.permissions =`, left empty) or by inspecting the APK's manifest.
Continuous integration asserts it too, on every build and against the
installed package on an emulator, so a future change cannot add one quietly.

The optional haptic feedback added in 1.1.0 deliberately uses Android's
built-in key-press feedback (`View.performHapticFeedback`), which requires no
permission. The `Vibrator`/`VibrationEffect` APIs, which would require the
`VIBRATE` permission, are not used. Haptics can be turned off in Settings.

## Dependencies

The core calculation, conversion, financial, history, and settings logic
(`src/cinqic_calculator/`) has no third-party runtime dependencies — pure
Python standard library. The desktop interface (Windows and Linux) uses only
`tkinter`, also standard library; the packaged builds bundle Python and Tk so
nothing else has to be installed. The Android interface additionally uses
[Kivy](https://kivy.org), an open-source UI toolkit, to draw the touch
interface; Kivy does not add any network, analytics, or telemetry
behavior on its own, and none is added by this app either.

## Crash reporting

No crash-reporting or error-telemetry service is included.

## Questions

Cinqic Calculator is open source. You can read the exact source code that
implements everything described here in this repository.
