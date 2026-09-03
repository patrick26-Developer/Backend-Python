"""Configuration du logging : JSON structuré en dehors du local, corrélé par
`request_id`.

- une ligne = un objet JSON (facile à indexer par un agrégateur : Loki, ELK…) ;
- `request_id` ajouté automatiquement à **chaque** ligne émise pendant une requête ;
- jamais de secret loggé (à toi de ne pas en passer dans `extra=`).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from taskman.core.context import get_request_id

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = get_request_id()
        if rid is not None:
            payload["request_id"] = rid

        # champs passés via logger.info("...", extra={...})
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S")
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn a ses propres handlers : on les fait passer par les nôtres
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
