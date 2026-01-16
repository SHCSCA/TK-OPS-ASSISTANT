"""Unit tests for script validation utilities."""

import pytest

from utils.script_validation import validate_tiktok_script_payload


def test_validate_ok_english_script():
    payload = {
        "hook_text": "Stop wasting money on loud fans.",
        "pain_text": "Your desk fan is noisy, weak, and dies in an hour.",
        "solution_text": "This mini clip fan is whisper-quiet, lasts all night, and clamps anywhere.",
        "cta_text": "Tap the link and grab yours today.",
        "full_script": "Stop wasting money on loud fans. Your desk fan is noisy, weak, and dies in an hour. This mini clip fan is whisper-quiet, lasts all night, and clamps anywhere. Tap the link and grab yours today.",
    }

    result = validate_tiktok_script_payload(payload, strict=True)
    assert result.ok is True
    assert "通过" in result.reason
    assert "tap" in result.normalized_script_text.lower()


def test_validate_missing_fields_fails():
    payload = {
        "hook_text": "Hook",
        "pain_text": "Pain",
        "solution_text": "Solution",
        # missing cta_text
    }

    result = validate_tiktok_script_payload(payload, strict=True)
    assert result.ok is False
    assert "缺少字段" in result.reason


def test_validate_cta_without_action_fails_in_strict_mode():
    payload = {
        "hook_text": "Hook",
        "pain_text": "Pain",
        "solution_text": "Solution",
        "cta_text": "Thanks for watching.",
        "full_script": "Hook Pain Solution Thanks for watching.",
    }

    result = validate_tiktok_script_payload(payload, strict=True)
    assert result.ok is False
    assert "CTA" in result.reason


def test_validate_too_long_english_fails_in_strict_mode():
    long_solution = " ".join(["solution"] * 120)
    payload = {
        "hook_text": "Hook",
        "pain_text": "Pain",
        "solution_text": long_solution,
        "cta_text": "Click the link now.",
        "full_script": f"Hook Pain {long_solution} Click the link now.",
    }

    result = validate_tiktok_script_payload(payload, strict=True)
    assert result.ok is False
    assert "过长" in result.reason


def test_validate_ok_chinese_script():
    payload = {
        "hook_text": "别再被风扇吵到睡不着了！",
        "pain_text": "普通风扇噪音大、续航短，还不好固定。",
        "solution_text": "这款迷你夹子风扇超静音、续航长，床头桌边一夹就稳。",
        "cta_text": "现在点击链接去下单。",
    }

    result = validate_tiktok_script_payload(payload, strict=True)
    assert result.ok is True
    assert result.normalized_script_text
