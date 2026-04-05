from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
I18N_DIR = BASE_DIR / "i18n"


class I18NService:
    def __init__(self) -> None:
        self._messages = {
            "uz": json.loads((I18N_DIR / "uz.json").read_text(encoding="utf-8")),
            "ru": json.loads((I18N_DIR / "ru.json").read_text(encoding="utf-8")),
        }

    def t(self, locale: str, key: str, **kwargs: str) -> str:
        messages = self._messages.get(locale, self._messages["uz"])
        template = messages.get(key, key)
        return template.format(**kwargs)
