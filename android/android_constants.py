"""Android-app-only constants.

Kept separate from ``cinqic_calculator.constants`` because the Android app is
*packaged* independently (its own ``buildozer.spec``
``version``/``android.numeric_version``) and carries an Android
``versionCode`` that the desktop has no equivalent for.

Since 1.1.0 the two platforms share a single product version number, so
``ANDROID_APP_VERSION`` and ``constants.APP_VERSION`` are expected to match --
a test asserts they do not silently drift apart.
"""

ANDROID_APP_VERSION = "1.1.0"
ANDROID_VERSION_CODE = 2

PRIVACY_SUMMARY = (
    "Cinqic Calculator works fully offline. There is no account, no ads, "
    "no analytics, and no telemetry. Calculations, history, and settings "
    "are stored only in this app's private storage on your device and are "
    "never transmitted anywhere. The app requests no Android permissions, "
    "including no internet permission."
)

JUNIPER_RELATIONSHIP_TEXT = (
    "Juniper is not integrated into Cinqic Calculator. The calculator "
    "works fully without AI. Juniper is Cinqic's separate local-first "
    "assistant app."
)
