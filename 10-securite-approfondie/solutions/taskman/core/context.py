"""Contexte de la requête courante, propagé sans le passer en argument partout.

`request_id_var` est une `ContextVar` : sa valeur est **isolée par tâche async**
(chaque requête a la sienne). Le middleware la renseigne, le logger la lit.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()
