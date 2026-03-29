"""Locale registry and message resolution."""

import os

from .locales.en import MESSAGES as _EN_MESSAGES

_current_locale: str = "en"
_messages: dict[str, dict[str, str]] = {"en": _EN_MESSAGES}


def set_locale(locale: str) -> None:
    """Set the active locale and eagerly load its messages."""
    global _current_locale
    normalized = _normalize_locale(locale)
    _current_locale = normalized
    _ensure_loaded(normalized)


def get_locale() -> str:
    """Get the active locale code."""
    return _current_locale


def detect_locale() -> str:
    """Detect locale from environment.

    Priority: NWVAULT_LEGACY_LANG env var -> system locale -> 'en'
    """
    env_lang = os.environ.get("NWVAULT_LEGACY_LANG")
    if env_lang:
        return _normalize_locale(env_lang)

    import locale as locale_mod

    try:
        system_locale, _ = locale_mod.getlocale()
    except Exception:
        system_locale = None

    if system_locale:
        return _normalize_locale(system_locale)

    return "en"


def _normalize_locale(raw: str) -> str:
    """Normalize locale string to a supported code.

    Maps zh_CN, zh-Hans, zh_TW, zh -> 'zh'
    Maps en_US, en-GB, en -> 'en'
    Unsupported locales fall back to 'en'
    """
    code = raw.lower().replace("-", "_").split("_")[0]
    from .locales import AVAILABLE_LOCALES

    if code in AVAILABLE_LOCALES:
        return code
    return "en"


def _ensure_loaded(locale: str) -> None:
    """Load a locale's messages if not already cached."""
    if locale in _messages:
        return

    if locale == "zh":
        from .locales.zh import MESSAGES

        _messages["zh"] = MESSAGES


def translate(key: str, **kwargs: object) -> str:
    """Look up a message key and interpolate.

    Fallback chain: current locale -> English -> raw key.
    """
    msg = _messages.get(_current_locale, {}).get(key)
    if msg is None:
        msg = _messages["en"].get(key)
    if msg is None:
        return key

    if kwargs:
        try:
            return msg.format(**kwargs)
        except (KeyError, IndexError):
            return msg
    return msg


# Auto-detect locale from env var at import time so lazy_t()
# resolves correctly during typer command tree construction.
_detected = detect_locale()
if _detected != "en":
    set_locale(_detected)
