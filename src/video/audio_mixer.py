"""
Audio Mixer - Handles timeline-based audio synthesis and mixing.
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import config
from video.processor import VideoProcessor
from tts import synthesize as tts_synthesize
from tts.utils import build_emotion_instruction

logger = logging.getLogger(__name__)

class AudioMixer:
    """Handles audio synthesis (TTS) and timeline mixing."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.processor = VideoProcessor()
        self._name_voice_timeline = "配音_时间轴.mp3"

    def synthesize_timeline(self, timeline: List[Dict]) -> Tuple[str, str]:
        """
        Synthesize voice based on a timeline, handling gaps and speed adjustments.
        
        Args:
            timeline: List of dicts with keys 'start', 'end', 'text', 'emotion'.
            
        Returns:
            (audio_path, error_message)
        """
        audio_path = Path(self.output_dir) / self._name_voice_timeline
        
        provider = (getattr(config, "TTS_PROVIDER", "edge-tts") or "edge-tts").strip()
        fallback = (getattr(config, "TTS_FALLBACK_PROVIDER", "") or "").strip()
        
        clips_to_concat = [] 
        current_time = 0.0
        
        # Helper for TTS generation
        def _gen_tts(txt, emo, out):
            try:
                tts_synthesize(text=txt, out_path=out, provider=provider, emotion=emo)
                return True
            except Exception as e:
                logger.warning(f"Primary TTS failed: {e}")
                if fallback:
                    try:
                        tts_synthesize(text=txt, out_path=out, provider=fallback, emotion=emo)
                        return True
                    except Exception as e2:
                        logger.warning(f"Fallback TTS failed: {e2}")
                        pass
            return False

        try:
            # Ensure output dir exists
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)

            for i, seg in enumerate(timeline):
                if not isinstance(seg, dict): continue
                try:
                    start = float(seg.get("start", 0))
                    end = float(seg.get("end", 0))
                except Exception: continue
                
                text = (seg.get("text", "") or "").strip()
                emotion = (seg.get("emotion", "neutral") or "neutral").strip().lower()
                
                # Instruction building (simplified from worker)
                # Ideally this logic should also be decoupled, but keeping here for now as it maps emotion string to TTS instruction
                # We can inject a formatter maybe? For now simple passthrough or simple instruction
                emotion_instruction = self._build_emotion_instruction(emotion)
                
                if not text or end <= start: continue

                # 1. Handle Gap (Silence)
                if start > current_time:
                    gap = start - current_time
                    if gap > 0.05:
                        silence_path = Path(self.output_dir) / f"silence_{i}_{int(gap*1000)}.mp3"
                        # Generate silence using processor (FFmpeg)
                        if self.processor.generate_silence(gap, str(silence_path)):
                            clips_to_concat.append(str(silence_path))
                    current_time = start # Align to start

                # 2. Generate TTS
                seg_out = Path(self.output_dir) / f"tts_seg_{i:03d}.mp3"
                if not _gen_tts(text, emotion_instruction, seg_out):
                    return "", f"TTS generation failed for segment {i}"
                
                if not seg_out.exists():
                     return "", f"TTS file missing for segment {i}"

                # 3. Align Duration
                dur = self.processor.get_audio_duration(str(seg_out))
                slot = max(0.1, end - start)
                
                # Check speed factor
                if dur > slot + 0.1: # Tolerance
                    # Speed up
                    factor = dur / slot
                    speed_out = Path(self.output_dir) / f"tts_seg_{i:03d}_speed.mp3"
                    if self.processor.adjust_audio_speed(str(seg_out), str(speed_out), factor):
                        clips_to_concat.append(str(speed_out))
                    else:
                        # Fallback to original
                        clips_to_concat.append(str(seg_out))
                elif dur < slot - 0.1:
                    # Pad
                    clips_to_concat.append(str(seg_out))
                    pad = slot - dur
                    pad_path = Path(self.output_dir) / f"pad_{i}_{int(pad*1000)}.mp3"
                    if self.processor.generate_silence(pad, str(pad_path)):
                        clips_to_concat.append(str(pad_path))
                else:
                    clips_to_concat.append(str(seg_out))

                current_time = end

            if not clips_to_concat:
                return "", "时间轴为空或无法生成配音"

            # Concat all
            if self.processor.concat_audio_files(clips_to_concat, str(audio_path)):
                return str(audio_path), ""
            else:
                return "", "音频拼接失败"

        except Exception as e:
            logger.error(f"Timeline synthesis failed: {e}", exc_info=True)
            return "", f"时间轴配音失败：{e}"

    def _build_emotion_instruction(self, base_emotion: str) -> str:
        """Wrapper for shared utility."""
        return build_emotion_instruction(base_emotion)
