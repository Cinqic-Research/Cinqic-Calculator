# Changelog

All notable changes to Cinqic Calculator are documented in this file.

From 1.1.0 onwards, all platforms share one product version. Desktop releases
(Windows and Linux) are tagged `vX.Y.Z` and ship together; Android is packaged
separately and tagged `android-vX.Y.Z`. Before 1.1.0, Windows and Android were
versioned independently.

## Unreleased

- Added comma thousands separators to entered numbers, expressions, live
  previews, results, and history results on desktop and Android. For example,
  `1234.56` is displayed as `1,234.56`. Fractional digits and scientific
  notation stay intact; calculations, copied values, stored history results,
  and calculator memory continue using ungrouped numeric values.

## 1.1.0

### Changed behaviour worth knowing about

- **Arithmetic now follows operator precedence.** `2 + 3 × 4` is `14`, where
  earlier versions evaluated strictly left to right and answered `20`. This is
  a consequence of showing the whole expression: once the display reads
  `2 + 3 × 4`, answering `20` contradicts what you can see. Parentheses are
  available for explicit grouping.

### User experience

- **Live answer preview.** The expression being built is shown in full, and
  the result it would produce appears as you type, before `=` is pressed. An
  unfinished expression stays quiet instead of flashing an error; genuine
  mistakes (dividing by zero, a domain error, an overflow) are reported with a
  short, readable message rather than Python exception text.
- **The expression line now works.** It previously existed in the desktop
  interface but was never populated.
- **Repeated equals now works.** `2 + 3 =` gives `5`, and pressing `=` again
  gives `8`, then `11`. This was documented from 1.0.0 onwards but never
  implemented; the test covering it never pressed `=` twice.
- **A clear key that says what it does** — it shows `CE` while an entry is
  being edited and `AC` when it would clear the whole calculation.
- **The pending operator is now visible** in both interfaces. On the desktop
  it is shown by a filled background and a sunken relief; on Android the key
  inverts to a bright fill with a dark label. Neither relies on hue alone.
- Long values stay readable: the display font shrinks as numbers grow.

### Calculations

- Added parentheses, `x^y`, `Ans`, `eˣ`, `10ˣ`, inverse trigonometry
  (`sin⁻¹`, `cos⁻¹`, `tan⁻¹`), and hyperbolic functions.
- `Ans` reuses the previous result and is kept separate from calculator
  memory, which remains explicitly user-controlled.
- Very large and very small results now use scientific notation instead of
  being rounded into a different number. Previously `1e-15` was displayed as
  `0`.
- The expression evaluator no longer hangs on an enormous exponent such as
  `9**9**9`, which previously allocated an unbounded integer — a denial of
  service in a sandbox meant to bound untrusted input. It remains allowlist-only
  with no `eval()` or `exec()` anywhere.

### Android

- Redesigned keypad: keys respond to a press with a short spring compression
  and rebound, drawn as a canvas transform so a pressed key never disturbs its
  neighbours. Newly entered digits animate into the display, with a slightly
  stronger transition when `=` commits a result.
- Animation is cosmetic only — calculator state updates immediately, and fast
  input retargets in-flight animations rather than queueing stale motion.
- The permanent memory row, the detached equals row, and the expanding
  scientific block are gone. The keypad is now a single four-column grid with
  `=` in it, backspace sits beside the display, and memory has moved into the
  scientific surface.
- Scientific mode is now a sheet that slides up over the keypad, with its
  functions grouped by purpose. Everything in it is reachable by tap; the drag
  handle is an addition, never the only way in or out.
- A combined `( )` key inserts whichever bracket fits the expression.
- Optional haptic feedback, using Android's built-in key-press feedback, which
  requires **no** additional permission. The app still requests no permissions
  at all.

### Windows

- The packaged executable is now smoke-tested during the release build.
- `--version` and `--help` options, so a packaged build can be checked without
  a display.

### Linux

- **Linux is now a supported platform.** Released as a self-contained
  `Cinqic-Calculator-Linux-x86_64.tar.gz` bundle that includes Python and Tk,
  with a launcher and a desktop entry.
- Settings and history follow the XDG Base Directory specification
  (`$XDG_DATA_HOME/Cinqic/Calculator`) rather than a bare folder in `$HOME`.
- Light/dark detection for the "system" theme now works on Linux desktops, not
  only on Windows.
- Continuous integration runs the full suite, lint, and the real Tkinter GUI
  smoke tests under Xvfb on Linux, and verifies the released tarball runs from
  a clean extraction.

### Accessibility

- A reduced-motion setting that removes bouncing and movement while keeping
  immediate feedback on every press. Animations remain on by default.
- Spoken labels for keys whose face is a symbol.
- Keypad touch targets sized for comfortable use on a phone.
- No state is conveyed by colour alone.
- Every text colour in both themes now meets WCAG AA contrast. The light
  theme's accent — used for the live answer, the operator keys, and the
  memory indicator — previously sat at 3.1:1 against the keypad, below the
  readable threshold. Label colour on the accent fill is now chosen by
  measured contrast rather than hardcoded, and a test enforces both.

### Licensing

- Cinqic Calculator is now licensed under the **Apache License 2.0**, replacing
  MIT. A `NOTICE` file and a `THIRD_PARTY_NOTICES.md` inventory have been
  added. Third-party components retain their own licences.

### Developer and release infrastructure

- Windows and Linux desktop artifacts are now built, verified, and published
  from a single tag, so both always represent the same version, with one
  combined `SHA256SUMS.txt` covering every asset.
- Continuous integration runs tests and lint on both Windows and Linux, and
  fails if the GUI smoke tests silently skip for want of a display.
- The Android emulator check now drives real input through the app — entry,
  the live preview, equals, repeated equals, backspace and rapid typing — and
  asserts the installed package requests no permissions, instead of only
  confirming that it launches.
- A test suite guards version and licence coherence across the seven places
  they are declared.

## Android 1.0.0

### Added

- A separate, independent Android frontend built with Kivy, reusing the
  same tested calculator, evaluator, financial, conversion, history,
  settings, and storage logic as the Windows app unchanged.
- Standard and scientific calculator, memory (MC/MR/M+/M-/MS) with the
  same enabled/disabled and cross-view isolation behavior as the desktop
  v1.0.1 fixes, unit conversions, financial tools, local history, settings,
  and About/privacy screens.
- Fully offline. No internet permission, no unnecessary permissions.
- Package `com.cinqic.calculator`, distributed as a direct signed APK
  download with a published SHA-256 checksum and signing certificate
  fingerprint — not through the Google Play Store.

## 1.0.1

### Fixed

- `MC` and `MR` are now disabled whenever memory is empty, instead of
  always appearing clickable regardless of state.
- Keyboard shortcuts (digits, operators, Enter, Escape, Backspace) no
  longer leak into the calculator's hidden state while another view
  (Convert, Financial, History, Settings, About) is active. Previously,
  typing into an entry field on another view also silently drove the
  invisible calculator's state, which could later surface as unexpected
  values or memory behavior when returning to the Calculator view.
- The "Remember calculator memory between sessions" setting now actually
  works: memory is restored on startup when enabled, saved whenever it
  changes, and cleared from disk immediately when the setting is turned
  off. Previously the checkbox had no effect at all, and even a direct
  write to this setting would have been silently dropped on reload.

### Improved

- The memory indicator and `MC`/`MR` state are now initialized correctly
  as soon as the calculator view is built, rather than only updating
  after the first button press.

## 1.0.0

Initial release.

### Added

- Standard calculator: addition, subtraction, multiplication, division,
  decimals, positive/negative values, percentage, square root, clear entry,
  clear all, backspace, and repeated-equals behavior.
- Collapsible scientific mode: square, cube, arbitrary exponent (via
  keyboard expression entry), square root, cube root, reciprocal,
  factorial, absolute value, pi, e, natural log, base-10 log, sine, cosine,
  tangent, and a degree/radian toggle.
- Calculator memory: MC, MR, M+, M-, MS with a visible memory indicator.
- Keyboard shortcuts for digits, operators, equals, clear, backspace, copy,
  paste, clear history, settings, and help.
- Unit conversion for length, mass, temperature, area, volume, speed, time,
  and data storage — with decimal (KB, MB, GB) and binary (KiB, MiB, GiB)
  data units kept explicitly distinct.
- Financial tools: percentage of/increase/decrease/difference, discount,
  sales tax, final price, tip, bill splitting, simple interest, and
  compound interest, using `Decimal` internally for currency accuracy.
- Local calculation history (up to 200 entries) with copy, reuse, delete,
  and clear-all, and a setting to disable history saving entirely.
- Local settings with dark, light, and system themes.
- A Windows installer and a portable ZIP build, both produced via
  PyInstaller and GitHub Actions.

### Known limitations

- Windows only (10/11, 64-bit) for this release.
- The build is not code-signed; Windows SmartScreen may show an
  unfamiliar-app warning on first run.
- Juniper is not integrated into this release. The calculator works fully
  without AI.
