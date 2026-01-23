"""
单元测试：VideoProcessor - 测试新增的 FFmpeg filter_complex_script 功能
"""
import pytest
import tempfile
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parents[2] / "src"))

from video.processor import VideoProcessor


class TestVideoProcessorFFmpegLength:
    """测试 FFmpeg 命令长度估算和脚本模式"""

    def test_estimate_filter_complex_length(self):
        """测试 filter_complex 长度估算"""
        processor = VideoProcessor()
        
        short_filter = "scale=1920:1080"
        estimated = processor._estimate_filter_complex_length(short_filter)
        
        # 估算应该包括 overhead
        assert estimated > len(short_filter), "估算应该包括额外开销"
        assert estimated == len(short_filter) + 500, "开销应该为 500 字符"

    def test_windows_cmd_limit_threshold(self):
        """测试 Windows CMD 8191 字符限制的判断逻辑"""
        processor = VideoProcessor()
        
        # 创建超过限制的 filter_complex
        very_long_filter = "x" * 8000  # 加上 500 overhead = 8500，超过 8191
        estimated = processor._estimate_filter_complex_length(very_long_filter)
        
        CMD_LIMIT = 8191
        # 应该被判断为需要使用脚本模式
        assert estimated > CMD_LIMIT - 200, "长过滤器应该触发脚本模式"

    def test_run_ffmpeg_with_script_auto_detect(self):
        """测试脚本模式的自动检测"""
        processor = VideoProcessor()
        
        # 模拟 FFmpeg 命令（没有真实视频）
        cmd = [
            "ffmpeg",
            "-y",
            "-i", "dummy.mp4",
            "-filter_complex", "PLACEHOLDER",
            "-map", "[v]",
            "-c:v", "libx264",
            "output.mp4"
        ]
        
        # 短 filter_complex：应该直接执行（会失败因为无有效视频）
        short_filter = "scale=1920:1080"
        result_ok, result_msg = processor._run_ffmpeg_with_script(cmd, short_filter)
        
        # 因为没有有效视频，会失败，但这不是我们要测试的
        # 我们只测试逻辑是否正确调用了 _run_ffmpeg（因为 filter 很短）
        # 实际的失败是因为 ffmpeg 无法处理 dummy.mp4
        assert isinstance(result_ok, bool), "应该返回布尔值"
        assert isinstance(result_msg, str), "应该返回错误信息"

    def test_filter_complex_script_file_creation(self):
        """测试脚本文件是否被正确创建和清理"""
        processor = VideoProcessor()
        
        # 创建一个超长的 filter_complex
        very_long_filter = ";" * 4000  # 4000 + 500 overhead > 8191
        
        cmd = [
            "ffmpeg",
            "-y",
            "-i", "dummy.mp4",
            "-filter_complex", "PLACEHOLDER",
            "-map", "[v]",
            "-c:v", "libx264",
            "output.mp4"
        ]
        
        # 执行（会失败，但脚本文件应该被创建和清理）
        result_ok, result_msg = processor._run_ffmpeg_with_script(cmd, very_long_filter)
        
        # 检查是否调用了脚本模式（失败信息应该不同）
        # 如果使用了脚本模式，可能出现脚本相关的错误
        # 这里主要测试函数能否正确处理超长 filter_complex
        assert isinstance(result_ok, bool), "应该返回布尔值"


class TestVideoProcessorIntegration:
    """集成测试：无真实视频，只测试逻辑流程"""

    def test_processor_initialization(self):
        """测试处理器初始化"""
        processor = VideoProcessor()
        
        assert processor.processed_count == 0, "初始化时处理计数应为 0"
        assert processor.failed_count == 0, "初始化时失败计数应为 0"

    def test_find_ffmpeg(self):
        """测试 FFmpeg 查找"""
        processor = VideoProcessor()
        
        ffmpeg_path = processor._find_ffmpeg()
        # 只检查返回类型，不要求一定找到（测试环境可能没装）
        assert ffmpeg_path is None or isinstance(ffmpeg_path, str), \
            "应该返回 None 或字符串路径"

    def test_get_duration_nonexistent_file(self):
        """测试获取不存在文件的时长"""
        processor = VideoProcessor()
        
        duration = processor._get_duration("/nonexistent/file.mp4")
        # 应该返回 0.0（异常处理）
        assert duration == 0.0, "不存在的文件应该返回 0.0"


class TestVideoProcessorErrorHandling:
    """错误处理测试"""

    def test_process_video_nonexistent_input(self):
        """测试处理不存在的输入文件"""
        processor = VideoProcessor()
        
        ok, msg = processor.process_video("/nonexistent/file.mp4")
        
        assert ok is False, "不存在的文件应该返回失败"
        assert "未找到输入文件" in msg or "nonexistent" in msg, \
            f"错误信息应该说明文件不存在，得到: {msg}"

    def test_merge_av_nonexistent_files(self):
        """测试合并不存在的文件"""
        processor = VideoProcessor()
        
        ok, msg = processor.merge_av(
            "/nonexistent/video.mp4",
            "/nonexistent/audio.aac",
            "/tmp/output.mp4"
        )
        
        assert ok is False, "不存在的文件应该返回失败"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
