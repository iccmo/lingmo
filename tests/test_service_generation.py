"""Tests for the typed generation service wrapper."""

import threading

import pytest

from novel_writer.schemas import GenerateBatchRequest, GenerateRequest
from novel_writer.services.generation_service import GenerationService
from novel_writer.state import gen_state


class FakeDb:
    def __init__(self, chapters):
        self._chapters = chapters

    def get_novel(self, novel_id: str):
        return {"id": novel_id, "chapters": self._chapters}


class NoopThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass


class ImmediateThread:
    def __init__(self, target, args=(), kwargs=None, **_ignored):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

    def start(self):
        self.target(*self.args, **self.kwargs)


def test_generation_service_next_chapter_ignores_outline_placeholders(monkeypatch):
    monkeypatch.setattr(threading, "Thread", NoopThread)
    novel_id = "svc-gen-outline"
    gen_state.pop_status(novel_id)
    service = GenerationService(FakeDb([
        {"number": 1, "word_count": 1800},
        {"number": 2, "word_count": 0},
        {"number": 3, "word_count": 1900},
    ]))

    response = service.trigger_generate(novel_id, GenerateRequest())

    assert response.next_chapter == 4


def test_generation_service_rejects_single_generate_while_batch_is_running(monkeypatch):
    monkeypatch.setattr(threading, "Thread", NoopThread)
    novel_id = "svc-single-busy"
    gen_state.set_status(novel_id, "running", "批量生成中", 20)
    service = GenerationService(FakeDb([]))

    with pytest.raises(ValueError, match="已有生成任务"):
        service.trigger_generate(novel_id, GenerateRequest())

    gen_state.pop_status(novel_id)


def test_generation_service_rejects_batch_when_queue_job_is_active(monkeypatch):
    monkeypatch.setattr(threading, "Thread", NoopThread)
    novel_id = "svc-batch-busy"
    job_id = "svc-batch-busy-job"
    gen_state.pop_status(novel_id)
    gen_state.set_job(job_id, {
        "job_id": job_id,
        "novel_id": novel_id,
        "status": "running",
        "progress": {"current": 0, "total": 2},
    })
    service = GenerationService(FakeDb([]))

    with pytest.raises(ValueError, match="已有生成任务"):
        service.trigger_batch(novel_id, GenerateBatchRequest(count=2))

    gen_state.remove_job(job_id)


def test_generation_service_batch_marks_job_done_after_runner_returns(monkeypatch):
    from novel_writer.routers.novel import generation_service as router_generation_service

    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        router_generation_service,
        "run_batch_generation",
        lambda *_args: {
            "requested": 2,
            "generated": 2,
            "failed": 0,
            "message": "批量生成完成：2章",
        },
    )
    novel_id = "svc-batch-done"
    gen_state.pop_status(novel_id)
    gen_state.remove_job("batch-svc-ba")
    service = GenerationService(FakeDb([]))

    response = service.trigger_batch(novel_id, GenerateBatchRequest(count=2))

    job = gen_state.get_job_dict()[response.job_id]
    assert job["status"] == "done"
    assert job["progress"] == {"current": 2, "total": 2}
    assert job.get("last_error") is None
    assert service.get_queue_status(novel_id).status == "complete"


def test_generation_service_batch_marks_job_error_when_runner_generates_nothing(monkeypatch):
    from novel_writer.routers.novel import generation_service as router_generation_service

    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    monkeypatch.setattr(
        router_generation_service,
        "run_batch_generation",
        lambda *_args: {
            "requested": 2,
            "generated": 0,
            "failed": 2,
            "message": "批量生成失败：0/2章产出有效内容",
        },
    )
    novel_id = "svc-batch-error"
    gen_state.pop_status(novel_id)
    service = GenerationService(FakeDb([]))

    response = service.trigger_batch(novel_id, GenerateBatchRequest(count=2))

    job = gen_state.get_job_dict()[response.job_id]
    assert job["status"] == "error"
    assert job["last_error"] == "批量生成失败：0/2章产出有效内容"
    assert service.get_queue_status(novel_id).status == "error"


def test_generation_service_batch_next_chapter_ignores_outline_placeholders(monkeypatch):
    monkeypatch.setattr(threading, "Thread", NoopThread)
    novel_id = "svc-batch-outline"
    gen_state.pop_status(novel_id)
    service = GenerationService(FakeDb([
        {"number": 1, "word_count": 1800},
        {"number": 2, "word_count": 0},
        {"number": 3, "word_count": 1900},
    ]))

    response = service.trigger_batch(novel_id, GenerateBatchRequest(count=3))

    assert response.next_chapter == 4
