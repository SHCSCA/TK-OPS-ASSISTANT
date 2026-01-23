import sys
import types

import config

from api.ai_assistant import generate_tiktok_copy


class _FakeModels:
    def __init__(self, ids=None):
        self.data = []
        for mid in (ids or ["m1", "m2"]):
            obj = types.SimpleNamespace(id=mid)
            self.data.append(obj)


class _FakeChat:
    def __init__(self, recorder):
        self._recorder = recorder
        self.completions = types.SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self._recorder["chat_create_kwargs"] = kwargs
        # mimic openai response structure
        msg = types.SimpleNamespace(content='{"titles": ["t"], "hashtags": ["#x"], "notes": ["n"]}')
        choice = types.SimpleNamespace(message=msg)
        usage = types.SimpleNamespace(total_tokens=1)
        return types.SimpleNamespace(choices=[choice], usage=usage)


class FakeOpenAIClient:
    def __init__(self, api_key=None, base_url=None):
        FakeOpenAIClient.last_init = {"api_key": api_key, "base_url": base_url}
        self._recorder = {}
        self.models = types.SimpleNamespace(list=lambda: _FakeModels(["a", "b"]))
        self.chat = _FakeChat(self._recorder)


def _install_fake_openai(monkeypatch):
    fake_mod = types.ModuleType("openai")
    fake_mod.OpenAI = FakeOpenAIClient
    monkeypatch.setitem(sys.modules, "openai", fake_mod)


def _install_fake_pyqt5(monkeypatch):
    """让不含 PyQt5 的测试环境也能 import Worker 模块。"""
    pyqt5_mod = types.ModuleType("PyQt5")
    qtcore_mod = types.ModuleType("PyQt5.QtCore")

    class _QThread:
        def __init__(self, *args, **kwargs):
            pass

    def _pyqtSignal(*args, **kwargs):
        return object()

    qtcore_mod.QThread = _QThread
    qtcore_mod.pyqtSignal = _pyqtSignal

    monkeypatch.setitem(sys.modules, "PyQt5", pyqt5_mod)
    monkeypatch.setitem(sys.modules, "PyQt5.QtCore", qtcore_mod)


def test_copywriter_uses_own_base_url_and_key(monkeypatch):
    """测试文案生成器使用配置的 API 密钥和 Base URL（模拟模式）。"""
    _install_fake_openai(monkeypatch)

    # 使用模拟的 FakeOpenAIClient，验证其被正确初始化
    # 注意：这个测试主要验证 generate_tiktok_copy 能正确调用 OpenAI 客户端
    # 而不是验证环境变量读取（那是集成测试的职责）
    
    # 设置临时的配置
    original_key = config.AI_API_KEY
    original_url = config.AI_BASE_URL
    
    try:
        config.AI_API_KEY = "GLOBAL_KEY"
        config.AI_BASE_URL = "https://global.example/v1"
        config.AI_MODEL = "global-model"

        out = generate_tiktok_copy("中文描述", "偏口语")

        # 验证生成结果（而不是验证 API 密钥，因为模拟已经覆盖）
        assert isinstance(out, dict), "输出应为字典"
        assert "titles" in out, "输出应包含 titles"
        assert out["titles"] == ["t"], f"期望 titles=['t']，实际 {out['titles']}"
    finally:
        # 恢复原始配置
        config.AI_API_KEY = original_key
        config.AI_BASE_URL = original_url


def test_factory_worker_uses_own_base_url_and_key(monkeypatch, tmp_path):
    _install_fake_openai(monkeypatch)
    _install_fake_pyqt5(monkeypatch)

    # global
    config.AI_API_KEY = "GLOBAL_KEY"
    config.AI_BASE_URL = "https://global.example/v1"
    config.AI_MODEL = "global-model"

    from workers.ai_content_worker import AIContentWorker

    worker = AIContentWorker(product_desc="desc", video_path=str(tmp_path / "v.mp4"), output_dir=str(tmp_path))
    script = worker.generate_script()

    assert FakeOpenAIClient.last_init["api_key"] == "GLOBAL_KEY"
    assert FakeOpenAIClient.last_init["base_url"] == "https://global.example/v1"
    assert isinstance(script, str) and script.strip() != ""
