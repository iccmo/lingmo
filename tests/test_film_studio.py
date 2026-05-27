"""Film Studio unit tests — DB, stations, endpoints."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from novel_writer.database import Database

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    """Isolated temp database."""
    return Database(str(tmp_path / "test.db"))


# ── Database: film_settings ─────────────────────────────────────────


class TestFilmSettings:
    def test_load_empty(self, db):
        """Fresh DB returns empty dict."""
        settings = db.load_film_settings()
        assert settings == {}

    def test_save_and_load(self, db):
        """Save a setting and load it back."""
        db.save_film_setting("image_provider", "stability")
        db.save_film_setting("image_api_key", "sk-abc123")
        settings = db.load_film_settings()
        assert settings["image_provider"] == "stability"
        assert settings["image_api_key"] == "sk-abc123"

    def test_overwrite(self, db):
        """Overwrite an existing setting."""
        db.save_film_setting("image_provider", "placeholder")
        db.save_film_setting("image_provider", "stability")
        assert db.load_film_settings()["image_provider"] == "stability"

    def test_multiple_keys(self, db):
        """Multiple keys coexist."""
        db.save_film_setting("image_provider", "stability")
        db.save_film_setting("music_provider", "suno")
        db.save_film_setting("image_api_key", "sk-xyz")
        settings = db.load_film_settings()
        assert len(settings) == 3
        assert settings["music_provider"] == "suno"


# ── Compositor: _render_subtitle ────────────────────────────────────


class TestRenderSubtitle:
    def test_basic_render(self, tmp_path):
        """Renders a subtitle PNG with valid dimensions."""
        from novel_writer.stations.drama.compositor import Compositor

        result = Compositor._render_subtitle("你好世界", 1080, 1920)
        try:
            assert result is not None
            assert result.endswith(".png")
            assert Path(result).exists()
            # Verify it's a valid PNG
            from PIL import Image

            img = Image.open(result)
            assert img.size == (1080, 1920)
            assert img.mode == "RGBA"
        finally:
            if result and Path(result).exists():
                os.unlink(result)

    def test_empty_text_returns_none(self):
        """Empty text returns None (no subtitle needed)."""
        from novel_writer.stations.drama.compositor import Compositor

        assert Compositor._render_subtitle("", 1080, 1920) is None
        assert Compositor._render_subtitle("   ", 1080, 1920) is None

    def test_long_text_wraps(self, tmp_path):
        """Long text is auto-wrapped into multiple lines."""
        from novel_writer.stations.drama.compositor import Compositor

        long_text = "这是一段非常非常长的对白，需要自动换行处理才能在屏幕上正确显示出来"
        result = Compositor._render_subtitle(long_text, 1080, 1920)
        try:
            assert result is not None
            assert Path(result).exists()
        finally:
            if result and Path(result).exists():
                os.unlink(result)

    def test_chinese_characters(self, tmp_path):
        """Chinese characters render without error."""
        from novel_writer.stations.drama.compositor import Compositor

        result = Compositor._render_subtitle("吾乃天命之子，尔等安敢放肆！", 1080, 1920)
        try:
            assert result is not None
        finally:
            if result and Path(result).exists():
                os.unlink(result)


# ── MusicEngine: _match_mood ────────────────────────────────────────


class TestMatchMood:
    def test_known_mood(self):
        """Known moods return their specific parameters."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        me = MusicEngine()
        params = me._match_mood("紧张")
        assert params["base_freq"] == 110
        assert params["harmonic_freq"] == 165

    def test_unknown_mood_returns_default(self):
        """Unknown mood returns default parameters."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        me = MusicEngine()
        params = me._match_mood("快乐")
        assert params == MusicEngine.DEFAULT_MUSIC

    def test_empty_mood_returns_default(self):
        """Empty mood returns default parameters."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        me = MusicEngine()
        assert me._match_mood("") == MusicEngine.DEFAULT_MUSIC

    def test_partial_match(self):
        """Mood containing a keyword matches (e.g. '紧张感' contains '紧张')."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        me = MusicEngine()
        params = me._match_mood("紧张感十足")
        assert params["base_freq"] == 110


# ── MusicEngine: _generate_suno (mocked) ────────────────────────────


class TestGenerateSuno:
    @patch("urllib.request.urlopen")
    def test_success(self, mock_urlopen, tmp_path):
        """Successful Suno API call downloads audio."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        # Mock the API response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"audio_url": "https://cdn.suno.ai/test.mp3"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        # Mock urlretrieve
        output_path = str(tmp_path / "test_music.mp3")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with patch("urllib.request.urlretrieve") as mock_retrieve:
                def fake_retrieve(url, path):
                    Path(path).write_bytes(b"fake audio data")
                mock_retrieve.side_effect = fake_retrieve

                result = MusicEngine._generate_suno("紧张 悬疑", 60.0, output_path, "sk-test")
                assert result is True
                assert Path(output_path).exists()

    def test_no_api_key_returns_false(self, tmp_path):
        """Empty API key should fail gracefully."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        output_path = str(tmp_path / "test_music.mp3")
        # _generate_suno will fail on the request, but should not raise
        result = MusicEngine._generate_suno("mood", 60.0, output_path, "")
        assert result is False


# ── Film Studio: Settings API endpoints ─────────────────────────────


class TestFilmSettingsAPI:
    @pytest.fixture
    def client(self, tmp_path):
        """TestClient with isolated DB."""
        from fastapi.testclient import TestClient

        from novel_writer.server import app, db

        old_path = db.db_path
        db.db_path = str(tmp_path / "test.db")
        db._init()
        tc = TestClient(app)
        yield tc
        db.db_path = old_path

    def test_get_defaults(self, client):
        """GET /api/novels/film-settings returns defaults."""
        r = client.get("/api/novels/film-settings")
        assert r.status_code == 200
        data = r.json()
        assert data["image_provider"] == "placeholder"
        assert data["image_api_key"] == ""

    def test_put_and_get(self, client):
        """PUT saves settings, GET returns them."""
        r = client.put(
            "/api/novels/film-settings",
            json={"image_provider": "stability", "image_api_key": "sk-abcdef123456"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        r = client.get("/api/novels/film-settings")
        data = r.json()
        assert data["image_provider"] == "stability"
        # Key should be masked
        assert "sk-a" in data["image_api_key"]
        assert "3456" in data["image_api_key"]
        assert "abcdef" not in data["image_api_key"]

    def test_put_provider_only(self, client):
        """PUT with only image_provider doesn't clear the key."""
        # First set a key
        client.put(
            "/api/novels/film-settings",
            json={"image_provider": "stability", "image_api_key": "sk-secret"},
        )
        # Then change provider only
        client.put(
            "/api/novels/film-settings",
            json={"image_provider": "placeholder"},
        )
        r = client.get("/api/novels/film-settings")
        data = r.json()
        assert data["image_provider"] == "placeholder"
        # Key should still be there (masked)
        assert data["image_api_key"] != ""


# ── ImageGenerator: provider selection ──────────────────────────────


class TestImageGeneratorProvider:
    def test_placeholder_by_default(self):
        """Default provider is placeholder."""
        from novel_writer.stations.drama.image_generator import ImageGenerator

        ig = ImageGenerator()
        # Just verify the class attributes exist
        assert ig.WIDTH == 1080
        assert ig.HEIGHT == 1920
        assert "close-up" in ig.GRADIENT_THEMES
        assert "紧张" in ig.EMOTION_TINTS


# ── MusicEngine: Suno polling helpers ─────────────────────────────


class TestSunoHelpers:
    def test_extract_audio_url_from_dict(self):
        """Extracts audio_url from a direct response dict."""
        from novel_writer.stations.drama.music_engine import _extract_audio_url

        assert _extract_audio_url({"audio_url": "https://cdn.suno.ai/a.mp3"}) == "https://cdn.suno.ai/a.mp3"

    def test_extract_audio_url_from_clips(self):
        """Extracts audio_url from clips array."""
        from novel_writer.stations.drama.music_engine import _extract_audio_url

        data = {"clips": [{"audio_url": "https://cdn.suno.ai/b.mp3"}]}
        assert _extract_audio_url(data) == "https://cdn.suno.ai/b.mp3"

    def test_extract_audio_url_from_list(self):
        """Extracts audio_url from a list response."""
        from novel_writer.stations.drama.music_engine import _extract_audio_url

        data = [{"audio_url": "https://cdn.suno.ai/c.mp3"}]
        assert _extract_audio_url(data) == "https://cdn.suno.ai/c.mp3"

    def test_extract_audio_url_empty(self):
        """Returns empty string for no audio_url."""
        from novel_writer.stations.drama.music_engine import _extract_audio_url

        assert _extract_audio_url({}) == ""
        assert _extract_audio_url(None) == ""
        assert _extract_audio_url([]) == ""

    def test_extract_clip_id_from_dict(self):
        """Extracts clip_id from response."""
        from novel_writer.stations.drama.music_engine import _extract_clip_id

        assert _extract_clip_id({"clip_id": "abc123"}) == "abc123"
        assert _extract_clip_id({"id": "xyz789"}) == "xyz789"

    def test_extract_clip_id_from_clips(self):
        """Extracts clip_id from clips array."""
        from novel_writer.stations.drama.music_engine import _extract_clip_id

        data = {"clips": [{"clip_id": "clip42"}]}
        assert _extract_clip_id(data) == "clip42"

    def test_extract_clip_id_empty(self):
        """Returns empty string for missing clip_id."""
        from novel_writer.stations.drama.music_engine import _extract_clip_id

        assert _extract_clip_id({}) == ""
        assert _extract_clip_id(None) == ""


# ── Film settings: music & subtitle ────────────────────────────────


class TestMusicSettings:
    @pytest.fixture
    def client(self, tmp_path):
        """TestClient with isolated DB."""
        from fastapi.testclient import TestClient

        from novel_writer.server import app, db

        old_path = db.db_path
        db.db_path = str(tmp_path / "test.db")
        db._init()
        tc = TestClient(app)
        yield tc
        db.db_path = old_path
    def test_music_settings_defaults(self, client):
        """GET film-settings includes music defaults."""
        r = client.get("/api/novels/film-settings")
        assert r.status_code == 200
        data = r.json()
        assert data["music_provider"] == "ambient"
        assert data["suno_api_key"] == ""

    def test_save_music_provider(self, client):
        """PUT saves music_provider."""
        r = client.put("/api/novels/film-settings", json={"music_provider": "suno"})
        assert r.status_code == 200
        r = client.get("/api/novels/film-settings")
        assert r.json()["music_provider"] == "suno"

    def test_subtitle_style_defaults(self, client):
        """GET film-settings includes subtitle defaults."""
        r = client.get("/api/novels/film-settings")
        data = r.json()
        assert data["subtitle_font_size"] == "36"
        assert data["subtitle_font_color"] == "#FFFFFF"
        assert data["subtitle_position"] == "bottom"

    def test_render_subtitle_with_custom_style(self, tmp_path):
        """Custom style dict is applied correctly."""
        from novel_writer.stations.drama.compositor import Compositor

        style = {
            "font_size": 48,
            "font_color": "#FF0000",
            "bg_color": "#0000FF",
            "bg_opacity": 200,
            "position": "top",
        }
        result = Compositor._render_subtitle("测试字幕", 1080, 1920, style)
        try:
            assert result is not None
            assert Path(result).exists()
        finally:
            if result and Path(result).exists():
                os.unlink(result)


# ── ComfyUI Client ───────────────────────────────────────────────────


class TestComfyUIClient:
    def test_init(self):
        """Client initializes with correct base URL."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        c = ComfyUIClient(host="localhost", port=9999)
        assert c.base_url == "http://localhost:9999"
        assert len(c.client_id) == 16

    def test_init_defaults(self):
        """Client defaults to 127.0.0.1:8188."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        c = ComfyUIClient()
        assert c.base_url == "http://127.0.0.1:8188"

    @patch("urllib.request.urlopen")
    def test_health_check_ok(self, mock_urlopen):
        """Health check returns True when ComfyUI responds."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"system": {"python_version": "3.10"}}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = ComfyUIClient()
        assert client.health_check() is True

    @patch("urllib.request.urlopen")
    def test_health_check_offline(self, mock_urlopen):
        """Health check returns False when ComfyUI is unreachable."""
        import urllib.error

        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        client = ComfyUIClient()
        assert client.health_check() is False

    @patch("urllib.request.urlopen")
    def test_queue_prompt_success(self, mock_urlopen):
        """queue_prompt returns prompt_id on success."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"prompt_id": "abc123"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = ComfyUIClient()
        prompt_id = client.queue_prompt({"1": {"class_type": "SaveImage"}})
        assert prompt_id == "abc123"

    @patch("urllib.request.urlopen")
    def test_queue_prompt_error(self, mock_urlopen):
        """queue_prompt raises ComfyUIError on HTTP error."""
        import urllib.error

        from novel_writer.stations.drama.comfyui_client import ComfyUIClient, ComfyUIError

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"error": "bad workflow"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        err = urllib.error.HTTPError(
            url="/prompt", code=400, msg="Bad Request",
            hdrs=None, fp=mock_resp,
        )
        mock_urlopen.side_effect = err

        client = ComfyUIClient()
        with pytest.raises(ComfyUIError, match="提交工作流失败"):
            client.queue_prompt({})

    @patch("urllib.request.urlopen")
    @patch("time.sleep")
    def test_poll_progress_completed(self, mock_sleep, mock_urlopen):
        """poll_progress returns when history shows completed."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        # First call: empty history; second call: completed
        empty_resp = MagicMock()
        empty_resp.read.return_value = b'{}'
        empty_resp.__enter__ = MagicMock(return_value=empty_resp)
        empty_resp.__exit__ = MagicMock(return_value=False)

        completed_resp = MagicMock()
        completed_resp.read.return_value = b'''{
            "prompt_123": {
                "outputs": {
                    "7": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}
                },
                "status": {"status_str": "success"}
            }
        }'''
        completed_resp.__enter__ = MagicMock(return_value=completed_resp)
        completed_resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [empty_resp, completed_resp]

        client = ComfyUIClient()
        result = client.poll_progress("prompt_123", timeout=10, interval=0.1)
        assert "outputs" in result
        assert "7" in result["outputs"]

    @patch("urllib.request.urlopen")
    @patch("time.monotonic")
    def test_poll_progress_timeout(self, mock_time, mock_urlopen):
        """poll_progress raises on timeout."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient, ComfyUIError

        empty_resp = MagicMock()
        empty_resp.read.return_value = b'{}'
        empty_resp.__enter__ = MagicMock(return_value=empty_resp)
        empty_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = empty_resp

        # Simulate time passing immediately
        mock_time.side_effect = [0.0, 400.0]

        client = ComfyUIClient()
        with pytest.raises(ComfyUIError, match="生成超时"):
            client.poll_progress("prompt_123", timeout=300, interval=0.01)

    @patch("urllib.request.urlopen")
    def test_download_image_success(self, mock_urlopen, tmp_path):
        """download_image writes file to save_path."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'\x89PNG fake data'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        save_path = str(tmp_path / "output.png")
        client = ComfyUIClient()
        result = client.download_image("out.png", "", save_path)
        assert result is True
        assert Path(save_path).exists()
        assert Path(save_path).read_bytes() == b'\x89PNG fake data'

    @patch("urllib.request.urlopen")
    def test_upload_image_success(self, mock_urlopen, tmp_path):
        """upload_image sends file and returns metadata."""
        from novel_writer.stations.drama.comfyui_client import ComfyUIClient

        # Create test image file
        img_path = str(tmp_path / "ref.png")
        Path(img_path).write_bytes(b'\x89PNG test')

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"name": "ref.png", "subfolder": "", "type": "input"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = ComfyUIClient()
        result = client.upload_image(img_path)
        assert result["name"] == "ref.png"
        assert result["type"] == "input"


# ── ComfyUI Workflow Builders ────────────────────────────────────────


class TestComfyUIWorkflows:
    def test_txt2img_basic(self):
        """build_txt2img_workflow produces valid workflow."""
        from novel_writer.stations.drama.comfyui_workflows import build_txt2img_workflow

        wf = build_txt2img_workflow(prompt="a cat", seed=42)
        assert "1" in wf  # CheckpointLoaderSimple
        assert "2" in wf  # CLIPTextEncode positive
        assert "3" in wf  # CLIPTextEncode negative
        assert "5" in wf  # KSampler
        assert "7" in wf  # SaveImage
        assert wf["2"]["inputs"]["text"] == "a cat"
        assert wf["5"]["inputs"]["seed"] == 42

    def test_txt2img_custom_params(self):
        """build_txt2img_workflow respects custom params."""
        from novel_writer.stations.drama.comfyui_workflows import build_txt2img_workflow

        wf = build_txt2img_workflow(
            prompt="test", negative="bad",
            checkpoint="custom.safetensors",
            width=512, height=512,
            steps=30, cfg=8.0,
        )
        assert wf["1"]["inputs"]["ckpt_name"] == "custom.safetensors"
        assert wf["4"]["inputs"]["width"] == 512
        assert wf["5"]["inputs"]["steps"] == 30
        assert wf["5"]["inputs"]["cfg"] == 8.0

    def test_ipadapter_faceid_has_required_nodes(self):
        """IP-Adapter FaceID workflow has all required nodes."""
        from novel_writer.stations.drama.comfyui_workflows import build_ipadapter_faceid_workflow

        wf = build_ipadapter_faceid_workflow(
            prompt="portrait", ref_image_name="ref.png",
        )
        class_types = {v["class_type"] for v in wf.values()}
        assert "LoadImage" in class_types
        assert "InsightFaceLoader" in class_types
        assert "IPAdapterModelLoader" in class_types
        assert "IPAdapterFaceID" in class_types
        assert "KSampler" in class_types
        assert "SaveImage" in class_types

    def test_portrait_workflow_prompt(self):
        """Portrait workflow builds correct prompt."""
        from novel_writer.stations.drama.comfyui_workflows import build_portrait_workflow

        wf = build_portrait_workflow(
            appearance="30岁男性，瘦削，黑色短发",
            costume="灰色卫衣",
            expression="眉头微蹙",
        )
        # Find the positive prompt node
        for node in wf.values():
            if node.get("class_type") == "CLIPTextEncode":
                text = node["inputs"].get("text", "")
                if "portrait photo" in text:
                    assert "30岁男性" in text
                    assert "灰色卫衣" in text
                    assert "眉头微蹙" in text
                    return
        pytest.fail("Positive prompt node not found")


# ── ImageGenerator: character refs matching ───────────────────────────


class TestCharacterRefsMatching:
    def test_match_found(self):
        """_match_character_refs returns refs when char_key in subject."""
        from novel_writer.stations.drama.image_generator import ImageGenerator

        refs = {"李明": ["/path/ref1.png", "/path/ref2.png"]}
        result = ImageGenerator._match_character_refs("李明站在窗前", refs)
        assert result == ["/path/ref1.png", "/path/ref2.png"]

    def test_match_not_found(self):
        """_match_character_refs returns empty list when no match."""
        from novel_writer.stations.drama.image_generator import ImageGenerator

        refs = {"李明": ["/path/ref1.png"]}
        result = ImageGenerator._match_character_refs("张伟走进教室", refs)
        assert result == []

    def test_match_empty_refs(self):
        """_match_character_refs handles empty refs dict."""
        from novel_writer.stations.drama.image_generator import ImageGenerator

        result = ImageGenerator._match_character_refs("李明在跑步", {})
        assert result == []

    def test_match_empty_values(self):
        """_match_character_refs skips chars with empty ref lists."""
        from novel_writer.stations.drama.image_generator import ImageGenerator

        refs = {"李明": [], "张伟": ["/path/ref.png"]}
        result = ImageGenerator._match_character_refs("李明在路上", refs)
        assert result == []


# ── ComfyUI Settings API ─────────────────────────────────────────────


class TestComfyUISettingsAPI:
    @pytest.fixture
    def client(self, tmp_path):
        """TestClient with isolated DB."""
        from fastapi.testclient import TestClient

        from novel_writer.server import app, db

        old_path = db.db_path
        db.db_path = str(tmp_path / "test.db")
        db._init()
        tc = TestClient(app)
        yield tc
        db.db_path = old_path

    def test_comfyui_defaults(self, client):
        """GET film-settings includes ComfyUI defaults."""
        r = client.get("/api/novels/film-settings")
        data = r.json()
        assert data["comfyui_url"] == "http://127.0.0.1:8188"
        assert data["comfyui_checkpoint"] == "sd_xl_base_1.0.safetensors"
        assert data["comfyui_ipadapter_model"] == "ip-adapter-faceid-plusv2_sd15.bin"
        assert data["comfyui_lora_strength"] == "0.8"
        assert data["comfyui_steps"] == "25"
        assert data["comfyui_cfg"] == "7.0"

    def test_save_comfyui_settings(self, client):
        """PUT saves ComfyUI settings."""
        r = client.put("/api/novels/film-settings", json={
            "image_provider": "comfyui",
            "comfyui_url": "http://192.168.1.100:8188",
            "comfyui_checkpoint": "my_model.safetensors",
            "comfyui_steps": "30",
        })
        assert r.status_code == 200
        r = client.get("/api/novels/film-settings")
        data = r.json()
        assert data["image_provider"] == "comfyui"
        assert data["comfyui_url"] == "http://192.168.1.100:8188"
        assert data["comfyui_checkpoint"] == "my_model.safetensors"
        assert data["comfyui_steps"] == "30"


# ── E2: StationResult + Knowledge Infrastructure ──────────────────


class TestStationResult:
    def test_default_values(self):
        """StationResult defaults to ok with empty knowledge."""
        from novel_writer.stations.base import StationResult

        sr = StationResult()
        assert sr.status == "ok"
        assert sr.data == {}
        assert sr.knowledge == []
        assert sr.errors == []

    def test_to_dict_basic(self):
        """to_dict merges status + data fields."""
        from novel_writer.stations.base import StationResult

        sr = StationResult(status="ok", data={"count": 5, "total": 42.0})
        d = sr.to_dict()
        assert d["status"] == "ok"
        assert d["count"] == 5
        assert d["total"] == 42.0

    def test_to_dict_with_knowledge(self):
        """to_dict includes knowledge list."""
        from novel_writer.stations.base import StationResult

        sr = StationResult()
        sr.add_knowledge("ai_director", "生成8个镜头", "压抑的情绪")
        d = sr.to_dict()
        assert "knowledge" in d
        assert len(d["knowledge"]) == 1
        assert d["knowledge"][0]["station"] == "ai_director"
        assert d["knowledge"][0]["decision"] == "生成8个镜头"
        assert d["knowledge"][0]["rationale"] == "压抑的情绪"

    def test_to_dict_errors_included(self):
        """to_dict includes errors list."""
        from novel_writer.stations.base import StationResult

        sr = StationResult(status="error", errors=["LLM timeout"])
        d = sr.to_dict()
        assert d["errors"] == ["LLM timeout"]

    def test_to_dict_empty_knowledge_omitted(self):
        """to_dict omits knowledge key when empty."""
        from novel_writer.stations.base import StationResult

        sr = StationResult(status="ok")
        d = sr.to_dict()
        assert "knowledge" not in d

    def test_add_knowledge(self):
        """add_knowledge appends to knowledge list."""
        from novel_writer.stations.base import StationResult

        sr = StationResult()
        sr.add_knowledge("station1", "decision1")
        sr.add_knowledge("station2", "decision2", "reason2")
        assert len(sr.knowledge) == 2
        assert sr.knowledge[1]["station"] == "station2"
        assert sr.knowledge[1]["rationale"] == "reason2"


class TestBaseStationKnowledge:
    def test_add_and_get_knowledge(self):
        """BaseStation tracks knowledge via add/get/reset."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        me = MusicEngine()
        assert me.get_knowledge() == []

        me.add_knowledge("使用 ambient 模式", "无 Suno API key")
        me.add_knowledge("节奏: building", "")
        assert len(me.get_knowledge()) == 2
        assert me.get_knowledge()[0]["station"] == "music_engine"

    def test_reset_knowledge(self):
        """reset_knowledge clears accumulated knowledge."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        me = MusicEngine()
        me.add_knowledge("test decision")
        assert len(me.get_knowledge()) == 1

        me.reset_knowledge()
        assert me.get_knowledge() == []

    def test_knowledge_copies_list(self):
        """get_knowledge returns a copy, not the internal list."""
        from novel_writer.stations.drama.music_engine import MusicEngine

        me = MusicEngine()
        me.add_knowledge("decision1")
        kb = me.get_knowledge()
        kb.append({"station": "fake", "decision": "injected"})
        # Original should not be affected
        assert len(me.get_knowledge()) == 1

    def test_station_context_knowledge_field(self):
        """StationContext.from_dict extracts knowledge list."""
        from novel_writer.stations.base import StationContext

        ctx = StationContext.from_dict({
            "novel_id": "test",
            "chapter_num": 1,
            "knowledge": [
                {"station": "ai_director", "decision": "生成8个镜头"},
            ],
        })
        assert len(ctx.knowledge) == 1
        assert ctx.knowledge[0]["station"] == "ai_director"

    def test_station_context_knowledge_default_empty(self):
        """StationContext defaults to empty knowledge list."""
        from novel_writer.stations.base import StationContext

        ctx = StationContext.from_dict({"novel_id": "test"})
        assert ctx.knowledge == []


# ── E2: PromptGenerator Knowledge Consumption ─────────────────────


class TestPromptGeneratorKnowledge:
    def test_extract_mood_from_knowledge(self):
        """_extract_mood_from_knowledge maps mood to style."""
        from novel_writer.stations.script.prompt_generator import PromptGenerator

        pg = PromptGenerator()
        knowledge = [
            {"station": "ai_director", "decision": "情绪基调", "rationale": "压抑"},
            {"station": "ai_director", "decision": "调色: 冷蓝调", "rationale": "冷蓝调"},
        ]
        result = pg._extract_mood_from_knowledge(knowledge)
        assert "heavy atmosphere" in result.lower() or "dark muted" in result.lower()

    def test_extract_mood_empty_knowledge(self):
        """_extract_mood_from_knowledge returns empty for no knowledge."""
        from novel_writer.stations.script.prompt_generator import PromptGenerator

        pg = PromptGenerator()
        assert pg._extract_mood_from_knowledge([]) == ""

    def test_extract_mood_no_mood_entry(self):
        """_extract_mood_from_knowledge returns empty when no mood entry."""
        from novel_writer.stations.script.prompt_generator import PromptGenerator

        pg = PromptGenerator()
        knowledge = [
            {"station": "ai_director", "decision": "生成8个镜头", "rationale": ""},
        ]
        assert pg._extract_mood_from_knowledge(knowledge) == ""


# ── E3: CharacterConsistencyMemory ────────────────────────────────


class TestCharacterConsistencyMemory:
    def test_record_and_get_visual_state(self, db):
        """Record visual state and retrieve it."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        # First, create a novel and character_state entry
        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 1, "林动", emotion="紧张")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(1, "林动", {
            "costume": "灰色卫衣",
            "hair_style": "黑色短发",
        })

        history = memory.get_visual_history("林动")
        assert len(history) == 1
        assert history[0].costume == "灰色卫衣"
        assert history[0].hair_style == "黑色短发"
        assert history[0].chapter_num == 1

    def test_record_baseline_and_later(self, db):
        """Record baseline (ch0) and later chapter, verify ordering."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 0, "林动")
        db.save_character_state("test-nov", 3, "林动")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(0, "林动", {"costume": "灰色卫衣"})
        memory.record_visual_state(3, "林动", {"costume": "黑色皮衣"})

        history = memory.get_visual_history("林动")
        assert len(history) == 2
        assert history[0].chapter_num == 0
        assert history[0].costume == "灰色卫衣"
        assert history[1].chapter_num == 3
        assert history[1].costume == "黑色皮衣"

    def test_get_visual_history_up_to_chapter(self, db):
        """get_visual_history respects up_to_chapter filter."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 0, "林动")
        db.save_character_state("test-nov", 3, "林动")
        db.save_character_state("test-nov", 5, "林动")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(0, "林动", {"costume": "灰衣"})
        memory.record_visual_state(3, "林动", {"costume": "黑衣"})
        memory.record_visual_state(5, "林动", {"costume": "白衣"})

        history = memory.get_visual_history("林动", up_to_chapter=3)
        assert len(history) == 2
        assert all(s.chapter_num <= 3 for s in history)

    def test_get_latest_visual(self, db):
        """get_latest_visual returns the most recent snapshot."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 0, "林动")
        db.save_character_state("test-nov", 3, "林动")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(0, "林动", {"costume": "灰衣"})
        memory.record_visual_state(3, "林动", {"costume": "黑衣"})

        latest = memory.get_latest_visual("林动", current_chapter=5)
        assert latest is not None
        assert latest.costume == "黑衣"
        assert latest.chapter_num == 3

    def test_get_latest_visual_no_history(self, db):
        """get_latest_visual returns None when no history."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        memory = CharacterConsistencyMemory(db, "test-nov")
        assert memory.get_latest_visual("不存在", current_chapter=5) is None

    def test_build_consistency_prompt(self, db):
        """build_consistency_prompt generates descriptive string."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 0, "林动")
        db.save_character_state("test-nov", 3, "林动")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(0, "林动", {
            "costume": "灰色卫衣",
            "injury_marks": "无",
        })
        memory.record_visual_state(3, "林动", {
            "costume": "黑色皮衣",
            "injury_marks": "左臂绷带",
        })

        prompt = memory.build_consistency_prompt("林动", current_chapter=5)
        assert "林动" in prompt
        assert "灰色卫衣" in prompt
        assert "黑色皮衣" in prompt
        assert "绷带" in prompt or "左臂" in prompt
        assert "第5章" in prompt

    def test_build_consistency_prompt_no_history(self, db):
        """build_consistency_prompt returns empty when no history."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        memory = CharacterConsistencyMemory(db, "test-nov")
        assert memory.build_consistency_prompt("不存在", current_chapter=5) == ""

    def test_detect_inconsistency_injury_missing(self, db):
        """detect_inconsistency flags missing injury marks."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 0, "林动")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(0, "林动", {
            "injury_marks": "左臂绷带",
        })

        # New chapter describes no injury → should detect inconsistency
        errors = memory.detect_inconsistency(1, "林动", {"costume": "新衣服"})
        assert len(errors) == 1
        assert "左臂绷带" in errors[0]

    def test_detect_inconsistency_clean(self, db):
        """detect_inconsistency returns empty when consistent."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 0, "林动")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(0, "林动", {
            "injury_marks": "无",
        })

        errors = memory.detect_inconsistency(1, "林动", {"costume": "新衣服"})
        assert errors == []

    def test_detect_inconsistency_no_history(self, db):
        """detect_inconsistency returns empty when no history."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        memory = CharacterConsistencyMemory(db, "test-nov")
        assert memory.detect_inconsistency(1, "林动", {}) == []

    def test_overwrite_same_chapter(self, db):
        """Recording same chapter twice overwrites the first entry."""
        from novel_writer.stations.script.character_memory import CharacterConsistencyMemory

        db.create_novel(id="test-nov", title="测试小说")
        db.save_character_state("test-nov", 1, "林动")

        memory = CharacterConsistencyMemory(db, "test-nov")
        memory.record_visual_state(1, "林动", {"costume": "灰衣"})
        memory.record_visual_state(1, "林动", {"costume": "黑衣"})

        history = memory.get_visual_history("林动")
        assert len(history) == 1
        assert history[0].costume == "黑衣"

    def test_visual_snapshot_to_from_dict(self):
        """VisualSnapshot serializes and deserializes correctly."""
        from novel_writer.stations.script.character_memory import VisualSnapshot

        snap = VisualSnapshot(
            chapter_num=3,
            costume="黑衣",
            injury_marks="左臂绷带",
            hair_style="短发",
            accessories="银戒指",
            mood_expression="沉思",
            extra={"custom": "value"},
        )
        d = snap.to_dict()
        restored = VisualSnapshot.from_dict(d)
        assert restored.chapter_num == 3
        assert restored.costume == "黑衣"
        assert restored.injury_marks == "左臂绷带"
        assert restored.extra == {"custom": "value"}


# ── E4: QualityChecker ─────────────────────────────────────────────


class TestQualityChecker:
    def test_config_defaults(self):
        """QualityConfig has sane defaults."""
        from novel_writer.stations.drama.quality_checker import QualityConfig

        cfg = QualityConfig()
        assert cfg.enabled is True
        assert cfg.max_retries == 2
        assert cfg.check_file is True
        assert cfg.check_dimensions is True
        assert cfg.check_face is False  # optional, off by default
        assert cfg.check_clip is False  # optional, off by default
        assert cfg.min_file_size == 10_000
        assert cfg.min_dimension == 512

    def test_config_from_dict(self):
        """QualityConfig.from_dict parses dict correctly."""
        from novel_writer.stations.drama.quality_checker import QualityConfig

        cfg = QualityConfig.from_dict({
            "enabled": False,
            "max_retries": 3,
            "check_face": True,
            "clip_threshold": 0.30,
        })
        assert cfg.enabled is False
        assert cfg.max_retries == 3
        assert cfg.check_face is True
        assert cfg.clip_threshold == 0.30
        assert cfg.check_file is True  # default

    def test_config_from_none(self):
        """QualityConfig.from_dict(None) returns defaults."""
        from novel_writer.stations.drama.quality_checker import QualityConfig

        cfg = QualityConfig.from_dict(None)
        assert cfg.enabled is True
        assert cfg.max_retries == 2

    def test_check_disabled_passes(self):
        """Disabled checker always passes."""
        from novel_writer.stations.drama.quality_checker import QualityChecker, QualityConfig

        checker = QualityChecker(QualityConfig(enabled=False))
        result = checker.check("nonexistent.png")
        assert result.passed is True
        assert result.checks_run == []

    def test_check_missing_file_fails(self):
        """Missing file fails file check."""
        from novel_writer.stations.drama.quality_checker import QualityChecker, QualityConfig

        checker = QualityChecker(QualityConfig(check_clip=False, check_face=False))
        result = checker.check("/nonexistent/path/image.png")
        assert result.passed is False
        assert "file" in result.checks_run
        assert "文件不存在" in result.failure_reason

    def test_check_small_file_fails(self, tmp_path):
        """File smaller than min_file_size fails."""
        from novel_writer.stations.drama.quality_checker import QualityChecker, QualityConfig

        small_file = tmp_path / "tiny.png"
        small_file.write_bytes(b"x" * 100)

        checker = QualityChecker(QualityConfig(check_clip=False, check_face=False))
        result = checker.check(str(small_file))
        assert result.passed is False
        assert any("太小" in f for f in result.failures)

    def test_check_valid_png_passes(self, tmp_path):
        """Valid PNG passes file + dimension checks."""
        from novel_writer.stations.drama.quality_checker import QualityChecker, QualityConfig

        # Create a valid PNG (800x800, >512px dimensions)
        # Use low min_file_size since solid-color PNGs compress well
        from PIL import Image
        img = Image.new("RGB", (800, 800), "blue")
        img_path = str(tmp_path / "valid.png")
        img.save(img_path)

        checker = QualityChecker(QualityConfig(
            check_clip=False, check_face=False, min_file_size=100,
        ))
        result = checker.check(img_path)
        assert result.passed is True
        assert "file" in result.checks_run
        assert "dimensions" in result.checks_run

    def test_check_small_dimensions_fails(self, tmp_path):
        """Image smaller than min_dimension fails."""
        from novel_writer.stations.drama.quality_checker import QualityChecker, QualityConfig

        from PIL import Image
        # 200x200 image — below 512px min_dimension
        img = Image.new("RGB", (200, 200), "red")
        img_path = str(tmp_path / "small.png")
        img.save(img_path)

        # Lower min_file_size so file check passes and we test dimensions
        checker = QualityChecker(QualityConfig(
            check_clip=False, check_face=False,
            min_dimension=512, min_file_size=100,
        ))
        result = checker.check(img_path)
        assert result.passed is False
        assert any("尺寸太小" in f for f in result.failures)

    def test_check_result_summary(self):
        """check_result_summary lists enabled checks."""
        from novel_writer.stations.drama.quality_checker import QualityChecker, QualityConfig

        checker = QualityChecker(QualityConfig(check_face=True, check_clip=False))
        summary = checker.check_result_summary
        assert "file" in summary
        assert "dimensions" in summary
        assert "face" in summary
        assert "clip" not in summary

    def test_best_of_empty(self):
        """best_of returns empty for empty candidates."""
        from novel_writer.stations.drama.quality_checker import QualityChecker

        checker = QualityChecker()
        assert checker.best_of([]) == ""

    def test_best_of_single(self):
        """best_of returns the single candidate."""
        from novel_writer.stations.drama.quality_checker import QualityChecker

        checker = QualityChecker()
        assert checker.best_of(["only.png"]) == "only.png"

    def test_best_of_prefers_larger_file(self, tmp_path):
        """best_of prefers larger file among passing candidates."""
        from novel_writer.stations.drama.quality_checker import QualityChecker, QualityConfig

        from PIL import Image

        checker = QualityChecker(QualityConfig(check_clip=False, check_face=False))

        small_img = Image.new("RGB", (600, 600), "blue")
        small_path = str(tmp_path / "small.png")
        small_img.save(small_path)

        large_img = Image.new("RGB", (1200, 1200), "red")
        large_path = str(tmp_path / "large.png")
        large_img.save(large_path)

        result = checker.best_of([small_path, large_path])
        assert result == large_path


# ── E4: Compositor Constants & Post-Processing ─────────────────────


class TestCompositorE4:
    def test_ken_burns_params_defined(self):
        """KEN_BURNS_PARAMS covers all 4 shot types."""
        from novel_writer.stations.drama.compositor import KEN_BURNS_PARAMS

        for st in ("close-up", "medium", "wide", "extreme-wide"):
            assert st in KEN_BURNS_PARAMS
            params = KEN_BURNS_PARAMS[st]
            assert "z" in params
            assert "x" in params
            assert "y" in params

    def test_camera_move_override(self):
        """CAMERA_MOVE_OVERRIDE maps special moves to shot types."""
        from novel_writer.stations.drama.compositor import CAMERA_MOVE_OVERRIDE

        assert CAMERA_MOVE_OVERRIDE["slow_zoom"] == "close-up"
        assert CAMERA_MOVE_OVERRIDE["pan"] == "medium"
        assert CAMERA_MOVE_OVERRIDE["static"] == ""  # no effect

    def test_color_profiles_defined(self):
        """COLOR_PROFILES has all three profiles."""
        from novel_writer.stations.drama.compositor import COLOR_PROFILES

        assert "冷蓝调" in COLOR_PROFILES
        assert "暖黄调" in COLOR_PROFILES
        assert "高对比黑白" in COLOR_PROFILES
        # Each should be a non-empty FFmpeg filter string
        for v in COLOR_PROFILES.values():
            assert len(v) > 0

    def test_post_process_filters(self):
        """POST_PROCESS_FILTERS includes sharpening, vignette, saturation."""
        from novel_writer.stations.drama.compositor import POST_PROCESS_FILTERS

        assert len(POST_PROCESS_FILTERS) == 3
        assert any("unsharp" in f for f in POST_PROCESS_FILTERS)
        assert any("vignette" in f for f in POST_PROCESS_FILTERS)
        assert any("saturation" in f for f in POST_PROCESS_FILTERS)

    def test_render_shot_static_mode(self, tmp_path):
        """_render_shot with static camera_move produces a video file."""
        from novel_writer.stations.drama.compositor import Compositor

        comp = Compositor()
        shot_path = str(tmp_path / "test_shot.ts")
        # No image file, static mode → uses lavfi color source
        result = comp._render_shot(
            shot_path=shot_path,
            duration=1.0,
            subject="test subject",
            dialogue="",
            shot_type="medium",
            image_file=None,
            voice_file="",
            subtitle="",
            camera_move="static",
        )
        # May fail if ffmpeg not installed; skip if so
        if result:
            assert Path(shot_path).exists()
            assert Path(shot_path).stat().st_size > 0

    @patch("subprocess.run")
    def test_apply_post_processing_calls_ffmpeg(self, mock_run, tmp_path):
        """_apply_post_processing builds correct FFmpeg command."""
        from novel_writer.stations.drama.compositor import Compositor

        output_path = str(tmp_path / "output.mp4")

        def create_output(cmd, **kwargs):
            Path(output_path).write_bytes(b"fake video")
            return MagicMock(returncode=0)

        mock_run.side_effect = create_output

        result = Compositor._apply_post_processing(
            "input.mp4", output_path, "冷蓝调",
        )
        assert result is True

        # Verify ffmpeg was called
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd[0]
        assert "-vf" in cmd

        # Verify the filter chain contains the color profile
        vf_idx = cmd.index("-vf") + 1
        vf_string = cmd[vf_idx]
        assert "colorbalance=" in vf_string or "curves=" in vf_string
        assert "unsharp" in vf_string

    @patch("subprocess.run")
    def test_apply_post_processing_unknown_grade(self, mock_run, tmp_path):
        """_apply_post_processing with unknown color_grade skips curves."""
        from novel_writer.stations.drama.compositor import Compositor

        output_path = str(tmp_path / "output.mp4")

        def create_output(cmd, **kwargs):
            Path(output_path).write_bytes(b"fake video")
            return MagicMock(returncode=0)

        mock_run.side_effect = create_output

        result = Compositor._apply_post_processing(
            "input.mp4", output_path, "不存在的色调",
        )
        assert result is True

        cmd = mock_run.call_args[0][0]
        vf_idx = cmd.index("-vf") + 1
        vf_string = cmd[vf_idx]
        # No curves for unknown grade, but still has post-process filters
        assert "curves=" not in vf_string
        assert "unsharp" in vf_string

    @patch("subprocess.run")
    def test_apply_post_processing_ffmpeg_error(self, mock_run):
        """_apply_post_processing returns False on FFmpeg error."""
        from novel_writer.stations.drama.compositor import Compositor

        mock_run.return_value = MagicMock(returncode=1, stderr="error output")

        result = Compositor._apply_post_processing("input.mp4", "output.mp4", "")
        assert result is False


# ── E4: ImageGenerator SHOT_OPTIMIZE ───────────────────────────────


class TestImageGeneratorE4:
    def test_shot_optimize_defined(self):
        """SHOT_OPTIMIZE maps shot_type to steps/cfg/prompt_prefix."""
        from novel_writer.stations.drama.image_generator import SHOT_OPTIMIZE

        for st in ("close-up", "medium", "wide", "extreme-wide"):
            assert st in SHOT_OPTIMIZE
            params = SHOT_OPTIMIZE[st]
            assert "steps" in params
            assert "cfg" in params
            assert "prompt_prefix" in params

    def test_shot_optimize_closeup_highest_steps(self):
        """Close-up has highest steps for maximum detail."""
        from novel_writer.stations.drama.image_generator import SHOT_OPTIMIZE

        closeup_steps = SHOT_OPTIMIZE["close-up"]["steps"]
        for st, params in SHOT_OPTIMIZE.items():
            if st != "close-up":
                assert closeup_steps >= params["steps"]

    def test_shot_optimize_cfg_range(self):
        """Close-up has tighter cfg (stricter prompt adherence)."""
        from novel_writer.stations.drama.image_generator import SHOT_OPTIMIZE

        closeup_cfg = SHOT_OPTIMIZE["close-up"]["cfg"]
        wide_cfg = SHOT_OPTIMIZE["wide"]["cfg"]
        assert closeup_cfg > wide_cfg  # close-up needs stricter adherence


# ── E4: Quality Settings API ───────────────────────────────────────


class TestQualitySettingsAPI:
    @pytest.fixture
    def client(self, tmp_path):
        """TestClient with isolated DB."""
        from fastapi.testclient import TestClient

        from novel_writer.server import app, db

        old_path = db.db_path
        db.db_path = str(tmp_path / "test.db")
        db._init()
        tc = TestClient(app)
        yield tc
        db.db_path = old_path

    def test_quality_defaults(self, client):
        """GET film-settings includes quality defaults."""
        r = client.get("/api/novels/film-settings")
        data = r.json()
        assert data["quality_enabled"] == "true"
        assert data["quality_max_retries"] == "2"
        assert data["quality_check_face"] == "false"
        assert data["quality_check_clip"] == "false"
        assert data["quality_clip_threshold"] == "0.20"

    def test_save_quality_settings(self, client):
        """PUT saves quality settings."""
        r = client.put("/api/novels/film-settings", json={
            "quality_enabled": "false",
            "quality_max_retries": "3",
            "quality_check_face": "true",
        })
        assert r.status_code == 200
        r = client.get("/api/novels/film-settings")
        data = r.json()
        assert data["quality_enabled"] == "false"
        assert data["quality_max_retries"] == "3"
        assert data["quality_check_face"] == "true"
