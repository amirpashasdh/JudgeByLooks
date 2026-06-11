import base64
import json
import re
import cv2
import numpy as np

# ─────────────────────────────────────────────
# PROMPT — edit this to change what gets extracted
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are a fashion style analyst. Analyze the clothing and style of the
person in the image.

Return ONLY a sparse JSON object of keyword scores — no prose, no markdown.
Include ONLY keywords that genuinely apply with a score between 0.1 and 1.0.
Omit keywords that score 0. Most people match 8–15 keywords.

Score based on:
- Garments visible (type, cut, fabric impression)
- Colors and patterns worn
- Silhouette and fit
- Overall aesthetic impression and mood
- Occasion and context clues

Valid keywords and their dimensions:

[Aesthetic]
minimalist, maximalist, classic, avant_garde, streetwear, bohemian,
preppy, romantic, edgy, quiet_luxury, coastal, dark_academia, sporty

[Mood]
playful, serious, rebellious, elegant, laid_back, bold, understated,
whimsical, polished, raw

[Color palette]
neutral, monochrome, earth_tones, pastel, bold_colors, black_forward,
white_forward, jewel_tones, multicolor

[Formality]
loungewear, casual, smart_casual, business_casual, formal, black_tie

[Cultural]
parisian, scandinavian, italian_luxury, japanese_minimalist,
american_prep, british_heritage, nyc_streetwear, californian

[Silhouette]
fitted, oversized, structured, flowy, layered, cropped, voluminous

[Occasion]
everyday, workwear, going_out, travel, outdoor, sport, beach, occasion

[Values]
sustainable, investment_piece, trend_driven, heritage_craft,
luxury_status, budget_conscious, logo_forward, logo_free,
size_inclusive, gender_neutral, performance_tech

Example output:
{
  "classic": 0.8,
  "earth_tones": 0.7,
  "fitted": 0.7,
  "business_casual": 0.6,
  "polished": 0.6,
  "neutral": 0.5,
  "italian_luxury": 0.4,
  "investment_piece": 0.4,
  "understated": 0.3
}
"""

# ─────────────────────────────────────────────
# BACKEND — switch between "claude", "ollama", "gemini"
# ─────────────────────────────────────────────
BACKEND = "claude"        # "claude", "ollama", or "gemini"
OLLAMA_MODEL = "llava:7b" # change to "llava:13b" or "moondream" if preferred
OLLAMA_URL = "http://localhost:11434/api/generate"
GEMINI_MODEL = "gemini-2.0-flash"  # free tier, fast, great vision support


def _encode_image(frame: np.ndarray) -> str:
    """Resize to max 1024px and base64-encode as JPEG."""
    h, w = frame.shape[:2]
    max_side = 1024
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.standard_b64encode(buf.tobytes()).decode("utf-8")


def _parse_json(raw: str) -> dict | None:
    """Strip markdown fences and parse JSON."""
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[analyzer] JSON parse error: {e}\nRaw output: {raw[:300]}")
        return None


class StyleAnalyzer:
    def __init__(self, backend: str = BACKEND):
        self.backend = backend
        if backend == "claude":
            import anthropic
            self.client = anthropic.Anthropic()
        elif backend == "gemini":
            import os
            from google import genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY not set.\n"
                    "  export GEMINI_API_KEY=your_key_here"
                )
            self.gemini_client = genai.Client(api_key=api_key)
        elif backend == "ollama":
            pass  # uses urllib, no init needed
        else:
            raise ValueError(f"Unknown backend: '{backend}'. Use 'claude', 'gemini', or 'ollama'.")

    def analyze(self, crop: np.ndarray) -> dict | None:
        image_data = _encode_image(crop)
        if self.backend == "claude":
            return self._analyze_claude(image_data)
        elif self.backend == "gemini":
            return self._analyze_gemini(crop)
        else:
            return self._analyze_ollama(image_data)

    def _analyze_claude(self, image_data: str) -> dict | None:
        import anthropic
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": "Analyze this person's clothing and style."},
                    ],
                }],
            )
            return _parse_json(message.content[0].text)
        except anthropic.APIError as e:
            print(f"[analyzer] Claude API error: {e}")
            return None

    def _analyze_gemini(self, crop: np.ndarray) -> dict | None:
        from google import genai
        from google.genai import types
        import io
        from PIL import Image

        # convert frame to PIL image
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        buf.seek(0)

        prompt = SYSTEM_PROMPT + "\n\nAnalyze this person's clothing and style. Return only the JSON object."

        try:
            response = self.gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                    prompt,
                ],
            )
            return _parse_json(response.text)
        except Exception as e:
            print(f"[analyzer] Gemini error: {e}")
            return None

    def _analyze_ollama(self, image_data: str) -> dict | None:
        import urllib.request
        import urllib.error

        prompt = (
            SYSTEM_PROMPT
            + "\n\nAnalyze this person's clothing and style. Return only the JSON object."
        )
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "images": [image_data],
            "stream": False,
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return _parse_json(result.get("response", ""))
        except urllib.error.URLError:
            print("[analyzer] Ollama not reachable. Is 'ollama serve' running?")
            return None
        except Exception as e:
            print(f"[analyzer] Ollama error: {e}")
            return None
