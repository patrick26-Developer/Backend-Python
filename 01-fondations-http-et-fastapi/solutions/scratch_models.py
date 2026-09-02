"""Solution de l'exercice 01.3 — démonstration des validations Pydantic.

Lancer depuis la racine du dépôt :
    python -m "01-fondations-http-et-fastapi.solutions.scratch_models"

Aucun cas invalide ne doit passer : chacun DOIT lever `ValidationError`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from .models import TaskCreate


def expect_ok(label: str, **kwargs: Any) -> None:
    task = TaskCreate(**kwargs)
    print(f"OK   {label}: {task.title!r} priority={task.priority} tags={task.tags}")


def expect_error(label: str, **kwargs: Any) -> None:
    try:
        TaskCreate(**kwargs)
    except ValidationError as exc:
        first = exc.errors()[0]
        print(f"OK   {label}: rejeté -> {first['loc']} : {first['msg']}")
    else:
        raise AssertionError(f"ÉCHEC {label}: aurait dû lever ValidationError")


def main() -> None:
    future = datetime.now(UTC) + timedelta(days=7)
    past = datetime.now(UTC) - timedelta(days=1)

    expect_ok(
        "données valides",
        title="  Préparer la démo  ",  # sera strippé
        description="slides + script",
        priority=4,
        due_date=future,
        tags=["demo", " urgent "],
    )
    expect_error("titre vide", title="   ")
    expect_error("priorité hors bornes", title="x", priority=9)
    expect_error("échéance passée", title="x", due_date=past)
    expect_error("trop de tags", title="x", tags=[f"t{i}" for i in range(11)])
    expect_error("tag trop long", title="x", tags=["x" * 21])

    print("\nTous les cas se comportent comme attendu.")


if __name__ == "__main__":
    main()
