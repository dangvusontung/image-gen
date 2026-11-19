import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import GenerationJob


class JobEventHub:
    """Wake project subscribers in a single backend process, as assumed by JobRunner.

    Subscribers have independent asyncio events. Publishers may run in request
    threads, and multiple changes can coalesce into one database refresh.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._subscribers: dict[str, dict[asyncio.Event, asyncio.AbstractEventLoop]] = {}

    @contextmanager
    def subscribe(self, project_id: str) -> Iterator[asyncio.Event]:
        loop = asyncio.get_running_loop()
        signal = asyncio.Event()
        with self._lock:
            self._subscribers.setdefault(project_id, {})[signal] = loop
        try:
            yield signal
        finally:
            with self._lock:
                subscribers = self._subscribers[project_id]
                del subscribers[signal]
                if not subscribers:
                    del self._subscribers[project_id]

    def publish(self, project_id: str) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers.get(project_id, {}).items())
        for signal, loop in subscribers:
            try:
                loop.call_soon_threadsafe(signal.set)
            except RuntimeError:
                if not loop.is_closed():
                    raise


job_events_hub = JobEventHub()
_CHANGED_PROJECTS = "job_events_changed_projects"


@event.listens_for(Session, "before_flush")
def _track_job_changes(session, flush_context, instances):
    # Covers runner and service writes, dismiss/restore/purge, and ORM deletes.
    projects = {
        job.project_id
        for jobs in (session.new, session.dirty, session.deleted)
        for job in jobs
        if isinstance(job, GenerationJob) and job.project_id is not None
    }
    if projects:
        transaction = session.get_nested_transaction() or session.get_transaction()
        session.info.setdefault(_CHANGED_PROJECTS, {}).setdefault(transaction, set()).update(projects)


@event.listens_for(Session, "after_commit")
def _publish_job_changes(session):
    transaction = session.get_nested_transaction() or session.get_transaction()
    changes = session.info.get(_CHANGED_PROJECTS, {})
    projects = changes.pop(transaction, ())
    if projects and transaction.nested:
        changes.setdefault(transaction.parent, set()).update(projects)
    else:
        for project_id in projects:
            job_events_hub.publish(project_id)


@event.listens_for(Session, "after_transaction_end")
def _discard_uncommitted_job_changes(session, transaction):
    changes = session.info.get(_CHANGED_PROJECTS)
    if changes is not None:
        changes.pop(transaction, None)
        if not changes:
            del session.info[_CHANGED_PROJECTS]
