import asyncio

from app.database import SessionLocal
from app.jobs.events import JobEventHub, job_events_hub
from app.models import GenerationJob
from tests.conftest import wait_for_job


def test_hub_broadcasts_from_a_thread_to_all_project_subscribers():
    hub = JobEventHub()

    async def check():
        with hub.subscribe("p1") as first, hub.subscribe("p2") as other:
            with hub.subscribe("p1") as second:
                await asyncio.to_thread(hub.publish, "p1")
                assert first.is_set()
                assert second.is_set()
                assert not other.is_set()
                second.clear()

            first.clear()
            await asyncio.to_thread(hub.publish, "p1")
            assert first.is_set()
            assert not second.is_set()

    asyncio.run(check())


def test_job_changes_publish_only_after_outer_commit(project, enqueue, client):
    job_id = enqueue()
    wait_for_job(client, job_id)

    async def check():
        with job_events_hub.subscribe(project) as signal, SessionLocal() as db:
            job = db.get(GenerationJob, job_id)
            with db.begin_nested():
                job.error_message = "nested"
            await asyncio.sleep(0)
            assert not signal.is_set()
            db.rollback()
            await asyncio.sleep(0)
            assert not signal.is_set()

            with db.begin_nested():
                job.error_message = "committed"
            db.commit()
            await asyncio.wait_for(signal.wait(), timeout=1)

    asyncio.run(check())
