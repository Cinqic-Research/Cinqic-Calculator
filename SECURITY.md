# Security

## Reporting a vulnerability

Report vulnerabilities privately through GitHub: **Security → Report a
vulnerability** on
[Cinqic-Research/Cinqic-Calculator](https://github.com/Cinqic-Research/Cinqic-Calculator/security).
Please do not post exploit details in a public issue. Cinqic Calculator is
maintained on a best-effort basis; there is no commercial support commitment.

## Security boundaries

Cinqic Calculator has no network client, server, account, or background
service. Its realistic attack surface is small:

- **Expression evaluation.** `src/cinqic_calculator/evaluator.py` parses input
  with Python's `ast` module and evaluates only an explicit allowlist of node
  types, operators, and named functions. Attribute access, imports, subscripts,
  comprehensions, and calls to any other name are rejected before evaluation.
  There is no `eval` or `exec`. Exponents and factorials are bounded so that a
  short expression cannot allocate an enormous integer.
- **Local files.** `settings.json` and the optional `history.json` live in the
  application's own data directory, are written atomically, and are parsed as
  JSON only. A corrupt file is treated as missing.
- **Android permissions.** The APK requests no permissions
  (`android.permissions =` is empty in `android/buildozer.spec`). CI inspects
  the built package and the installed app on an emulator and fails if a
  permission appears. Haptics use `View.performHapticFeedback`, which needs no
  permission.
- **Release artifacts.** Desktop builds are not code-signed. Each release
  publishes SHA-256 checksums; verify downloads against them.

See [PRIVACY.md](PRIVACY.md) for what the app stores and what it never sends.
