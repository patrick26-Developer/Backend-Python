"""Le noyau de domaine : événements et types partagés entre *bounded contexts*."""

from taskman.domain.events import DomainEvent, EventPublisher

__all__ = ["DomainEvent", "EventPublisher"]
