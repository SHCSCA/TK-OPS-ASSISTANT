import pytest

from tts.volc_docs import extract_voice_types_from_text


def test_extract_voice_types_from_text_dedup_and_sort():
    html = """
    <html>
      <body>
        <div>saturn_zh_male_shuanglangshaonian_tob</div>
        <div>saturn_zh_male_tiancaitongzhuo_tob</div>
        <div>zh_female_xueayi_saturn_bigtts</div>
        <div>BV001_streaming</div>
        <div>BV001_streaming</div>
        <div>custom_mix_bigtts</div>
      </body>
    </html>
    """

    voices = extract_voice_types_from_text(html)

    assert voices == sorted(set(voices))
    assert "saturn_zh_male_shuanglangshaonian_tob" in voices
    assert "zh_female_xueayi_saturn_bigtts" in voices
    assert "BV001_streaming" in voices
    assert "custom_mix_bigtts" in voices


def test_extract_voice_types_empty_text():
    assert extract_voice_types_from_text("") == []
    assert extract_voice_types_from_text(None) == []  # type: ignore[arg-type]
