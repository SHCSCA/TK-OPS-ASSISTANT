"""
Script Engine - Dedicated logic for script generation via AI
"""
from typing import Optional, Dict, Any
import logging
import json
import re
import config
from utils.ai_routing import resolve_ai_profile

logger = logging.getLogger(__name__)

class ScriptEngine:
    """Manages interactions with LLMs to generate TikTok scripts."""

    def __init__(self, model_override: str = "", provider_override: str = ""):
        self.model = model_override
        self.provider = provider_override
        self.last_error = ""

    def generate_script(self, 
                       product_desc: str, 
                       role_prompt: str = "",
                       ui_log_callback = None) -> Optional[str]:
        """
        Generate a video script using the configured AI model.
        
        Args:
            product_desc: Product description.
            role_prompt: Optional role instructions (overrides system default if provided).
            ui_log_callback: Optional callable for logging (e.g. `worker.emit_log`).
        
        Returns:
            The generated script text, or None if failed.
        """
        try:
            import openai
            self.last_error = ""

            profile = resolve_ai_profile("factory", model_override=self.model, provider_override=self.provider)
            api_key = (profile.get("api_key", "") or "").strip()
            if not api_key:
                logger.warning("AI_API_KEY Missing")
                self.last_error = "AI API Key missing"
                return None
            
            base_url = (profile.get("base_url", "") or "").strip() or "https://api.deepseek.com"
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            # --- Ark (Volcengine) Thinking Logic ---
            ark_thinking_type = (getattr(config, "ARK_THINKING_TYPE", "") or "").strip()
            ark_extra = None
            if base_url and ark_thinking_type:
                u = base_url.lower()
                if ("volces.com" in u) or ("volcengine.com" in u) or ("ark." in u):
                    ark_extra = {"thinking": {"type": ark_thinking_type}}
            
            # --- Prompt Construction ---
            system = (
                "You are a TikTok script writer. Keep output concise and natural. "
                "Follow role/style constraints if provided."
            )
            
            # Layered role prompt resolution
            extra_role = (
                (role_prompt or "").strip()
                or (getattr(config, "AI_FACTORY_ROLE_PROMPT", "") or "").strip()
                or (getattr(config, "AI_SYSTEM_PROMPT", "") or "").strip()
            )
            
            is_free_mode = bool(role_prompt and role_prompt.strip())
            
            if extra_role:
                system = system + "\n[ROLE_PROMPT]\n" + extra_role

            if is_free_mode:
                prompt = f"""
Context / Product: {product_desc}

Requirement: Write a short video script based on the ROLE_PROMPT above.
Output ONLY the script text, no markdown.
""".strip()
            else:
                prompt = f"""
Create a 30-second product pitch script for:

Product: {product_desc}

Requirements:
- Start with a Hook (3 seconds)
- Present Pain Points (10 seconds)
- Show Solution (15 seconds)
- End with Call to Action (2 seconds)
- Use casual, conversational American English
- Keep it under 100 words

Output ONLY the script text, no formatting.
""".strip()

            use_model = (profile.get("model", "") or "").strip() or "deepseek-chat"

            # --- Model Capability Validation ---
            _model_lower = use_model.lower()
            if any(k in _model_lower for k in ("seedance", "t2v", "i2v", "wan2.1", "wan2-1")):
                msg = f"⚠️ Error: Video model '{use_model}' detected. Script generation requires a Text model."
                if ui_log_callback: ui_log_callback(msg)
                self.last_error = msg
                return None

            # DeepSeek Official API Corrections
            if "deepseek.com" in (base_url or ""):
                if use_model not in ("deepseek-chat", "deepseek-reasoner"):
                    if "r1" in use_model.lower():
                        use_model = "deepseek-reasoner"
                    else:
                        use_model = "deepseek-chat"

            # Call API
            try:
                kwargs = {
                    "model": use_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.5,
                }
                if ark_extra:
                    kwargs["extra_body"] = ark_extra
                    
                response = client.chat.completions.create(**kwargs)
                
                # Usage Logging
                if ui_log_callback and response.usage:
                    u = response.usage
                    token_msg = f"💰 Token Usage: Prompt={u.prompt_tokens}, Completion={u.completion_tokens}, Total={u.total_tokens}"
                    ui_log_callback(token_msg)

                return (response.choices[0].message.content or "").strip()
                
            except Exception as e:
                # Handle fallback logic if needed, or re-raise
                logger.error(f"OpenAI Call Failed: {e}")
                self.last_error = str(e)
                return None

        except Exception as e:
            logger.error(f"Script Generation Logic Error: {e}")
            self.last_error = str(e)
            return None
