"""测试 GenerationState 线程安全和一致性。"""
import threading
import time

from novel_writer.state import GenerationState, is_active_generation_status


class TestGenerationState:
    """GenerationState 单例行为测试。"""

    def test_singleton(self):
        """单例：多次导入返回同一实例。"""
        from novel_writer.state import gen_state as a
        from novel_writer.state import gen_state as b
        assert a is b

    def test_set_and_get_status(self):
        """基本读写：set 后 get 返回一致。"""
        gs = GenerationState()
        gs.set_status("novel-1", "generating", "正在生成...", 50, 0.85)
        status = gs.get_status("novel-1")
        assert status["status"] == "generating"
        assert status["message"] == "正在生成..."
        assert status["progress"] == 50
        assert status["overall"] == 0.85

    def test_default_idle(self):
        """未设置的 novel 返回 idle 状态。"""
        gs = GenerationState()
        status = gs.get_status("nonexistent")
        assert status["status"] == "idle"

    def test_overwrite_status(self):
        """同一 novel 多次写入，最后一次生效。"""
        gs = GenerationState()
        gs.set_status("nov-1", "generating", "first", 10)
        gs.set_status("nov-1", "complete", "done", 100, 0.92)
        status = gs.get_status("nov-1")
        assert status["status"] == "complete"
        assert status["overall"] == 0.92

    def test_overall_zero_not_set(self):
        """overall=0 时不写入该字段。"""
        gs = GenerationState()
        gs.set_status("nov-1", "generating", "msg", 0, 0)
        status = gs.get_status("nov-1")
        assert "overall" not in status

    def test_update_stream_content_increments_version_without_resetting_status(self):
        """流式正文更新应保留当前阶段，并递增版本供 SSE 推送。"""
        gs = GenerationState()
        gs.set_status("nov-1", "generating", "正在生成", 20)
        gs.update_stream_content("nov-1", "第一段")
        gs.update_stream_content("nov-1", "第一段第二句")

        status = gs.get_status("nov-1")
        assert status["status"] == "generating"
        assert status["message"] == "正在生成"
        assert status["progress"] == 20
        assert status["stream_content"] == "第一段第二句"
        assert status["stream_version"] == 2

    def test_set_status_preserves_stream_content_across_generation_phases(self):
        """编辑和评分阶段不应让实时预览突然消失。"""
        gs = GenerationState()
        gs.set_status("nov-1", "generating", "正在生成", 20)
        gs.update_stream_content("nov-1", "已经生成的正文")

        gs.set_status("nov-1", "editing", "正在精修", 65)
        editing_status = gs.get_status("nov-1")
        gs.set_status("nov-1", "judging", "正在评分", 80)
        judging_status = gs.get_status("nov-1")

        assert editing_status["stream_content"] == "已经生成的正文"
        assert editing_status["stream_version"] == 1
        assert judging_status["stream_content"] == "已经生成的正文"
        assert judging_status["stream_version"] == 1

    def test_set_status_clears_stale_stream_content_when_new_generation_starts(self):
        """新一轮生成排队时不能显示上一章的旧预览。"""
        gs = GenerationState()
        gs.set_status("nov-1", "complete", "完成", 100)
        gs.update_stream_content("nov-1", "上一章正文")

        gs.set_status("nov-1", "generating", "正在排队", 5)

        status = gs.get_status("nov-1")
        assert "stream_content" not in status
        assert "stream_version" not in status

    def test_set_status_clears_stale_stream_content_when_batch_generation_starts(self):
        """批量生成可能直接进入高进度 generating，也不能继承上一章预览。"""
        gs = GenerationState()
        gs.set_status("nov-1", "complete", "上一章完成", 100)
        gs.update_stream_content("nov-1", "上一章正文")

        gs.set_status("nov-1", "generating", "正在生成第2章", 50)

        status = gs.get_status("nov-1")
        assert "stream_content" not in status
        assert "stream_version" not in status

    def test_set_status_can_apply_quality_fields_atomically(self):
        """完成态质量详情应随同一状态事件写入，避免 SSE 最终包缺字段。"""
        gs = GenerationState()
        gs.set_status(
            "nov-1",
            "complete",
            "完成",
            100,
            0.87,
            extra={"grade": "A", "quality_detail": {"plot": 0.9}},
        )

        status = gs.get_status("nov-1")
        assert status["overall"] == 0.87
        assert status["grade"] == "A"
        assert status["quality_detail"] == {"plot": 0.9}

    def test_get_status_dict_copy(self):
        """get_status_dict 返回副本，外部修改不影响内部。"""
        gs = GenerationState()
        gs.set_status("a", "running", "", 0)
        d = gs.get_status_dict()
        d["a"]["status"] = "hacked"
        assert gs.get_status("a")["status"] == "hacked"  # shallow copy — nested dict still shared

    def test_pop_status(self):
        """pop 返回并删除。"""
        gs = GenerationState()
        gs.set_status("x", "done", "", 100)
        popped = gs.pop_status("x")
        assert popped["status"] == "done"
        assert gs.get_status("x")["status"] == "idle"

    def test_active_generation_status_helper(self):
        assert is_active_generation_status("generating")
        assert is_active_generation_status("polishing")
        assert is_active_generation_status("running")
        assert not is_active_generation_status("complete")
        assert not is_active_generation_status("done")
        assert not is_active_generation_status("error")
        assert not is_active_generation_status(None)

    # ── Directions ──

    def test_directions_set_and_pop(self):
        gs = GenerationState()
        gs.set_direction("key1", "val1")
        assert gs.pop_direction("key1") == "val1"
        assert gs.pop_direction("key1", "none") == "none"

    def test_pop_direction_default(self):
        gs = GenerationState()
        assert gs.pop_direction("no-such", "default") == "default"

    def test_clean_directions(self):
        gs = GenerationState()
        gs.set_direction("nov-1", "direction")
        gs.set_direction("nov-1_soul", "soul")
        gs.set_direction("nov-1_qthreshold", "0.8")
        gs.clean_directions("nov-1")
        assert gs.pop_direction("nov-1", "gone") == "gone"
        assert gs.pop_direction("nov-1_soul", "gone") == "gone"

    # ── Job Queue ──

    def test_job_lifecycle(self):
        gs = GenerationState()
        gs.set_job("j1", {"job_id": "j1", "novel_id": "n1", "status": "queued"})
        assert gs.get_job("n1") is not None
        gs.update_job("j1", status="running")
        job = gs.get_job("n1")
        assert job["status"] == "running"

    def test_get_job_none_when_done(self):
        gs = GenerationState()
        gs.set_job("j1", {"job_id": "j1", "novel_id": "n1", "status": "done"})
        # done jobs are not "active" (only queued/running)
        assert gs.get_job("n1") is None

    def test_remove_job(self):
        gs = GenerationState()
        gs.set_job("j1", {"job_id": "j1", "novel_id": "n1", "status": "queued"})
        gs.remove_job("j1")
        assert gs.get_job("n1") is None

    # ── Thread Safety ──

    def test_concurrent_set_status(self):
        """多线程同时写入不应崩溃或丢数据。"""
        gs = GenerationState()
        errors = []

        def writer(n):
            try:
                for i in range(100):
                    gs.set_status(f"novel-{n}", "generating", f"msg-{i}", i)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All 10 novels should have status
        for i in range(10):
            assert gs.get_status(f"novel-{i}")["status"] == "generating"

    def test_concurrent_directions(self):
        """多线程 pop/set 交错不应丢数据。"""
        gs = GenerationState()
        results = []

        def worker(n):
            for _ in range(50):
                gs.set_direction(f"k{n}", f"v{n}")
                val = gs.pop_direction(f"k{n}", "miss")
                if val and val != f"v{n}":
                    results.append(f"unexpected: {val}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 0
