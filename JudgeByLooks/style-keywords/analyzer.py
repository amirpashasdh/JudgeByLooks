import base64
import json
import os
import re
import cv2
import numpy as np

# ─────────────────────────────────────────────
# TAXONOMY MODE — controls what style_scores contains
# "keywords"   → 72-keyword sparse scores only
# "archetypes" → 32-archetype weighted scores only
# "both"       → both sets in parallel
# ─────────────────────────────────────────────
TAXONOMY_MODE = os.getenv("TAXONOMY_MODE", "both")

BACKEND      = "claude"
OLLAMA_MODEL = "llava:7b"
OLLAMA_URL   = "http://localhost:11434/api/generate"
GEMINI_MODEL = "gemini-2.0-flash"

_KEYWORDS_SECTION = """
[Aesthetic — broad]
minimalist, maximalist, classic, avant_garde, streetwear, bohemian,
preppy, romantic, edgy, quiet_luxury, coastal, dark_academia, sporty

[Aesthetic — sub-genres]
clean_girl, ballet_aesthetic, coquette_style, tomboy_chic, androgynous_look,
soft_glamour, indie_style, coastal_grandmother, dopamine_dressing, quiet_opulence,
power_dressing, artsy_downtown, retro_seventies, retro_nineties, y2k_inspired,
futuristic_style, boho_luxe, mob_wife_glam, stealth_wealth, avant_minimalist

[Mood]
playful, serious, rebellious, elegant, laid_back, bold, understated,
whimsical, polished, raw, dramatic, ethereal, sensual, nostalgic, futuristic_mood

[Color — palette]
neutral, monochrome, earth_tones, pastel, bold_colors, black_forward,
white_forward, jewel_tones, multicolor, neon_accent, pastel_rainbow,
gradient_dye, burnout_print, ikat_pattern

[Color — specifics]
burgundy_wine, camel_tan, cobalt_blue, forest_green, blush_pink, cream_ivory,
olive_khaki, rust_orange, stone_grey, dusty_mauve, warm_taupe, slate_blue,
powder_blue, mint_green, lilac_purple, sage_green, mustard_yellow, coral_pink,
teal_green, charcoal_grey, navy_blue, silver_tone, golden_yellow, deep_purple,
hot_pink, champagne_gold, midnight_blue, chocolate_brown, nude_pink, jade_green,
indigo_blue, fuchsia_pink, lavender_haze, amber_gold, smoky_grey, copper_bronze,
pearl_white, burnt_sienna

[Formality]
loungewear, casual, smart_casual, business_casual, formal, black_tie

[Cultural]
parisian, scandinavian, italian_luxury, japanese_minimalist, american_prep,
british_heritage, nyc_streetwear, californian, korean_minimal, french_riviera,
milan_chic, mediterranean_style, australian_surf, east_london, tokyo_street,
brooklyn_cool, porto_casual, rio_beach

[Silhouette — core]
fitted, oversized, structured, flowy, layered, cropped, voluminous

[Silhouette — cut]
wide_leg, slim_cut, high_waist, tailored_cut, balloon_sleeve, a_line,
shift_silhouette, bodycon, empire_waist, pencil_cut, column_silhouette,
cape_silhouette, mermaid_cut, trapeze_cut, boxy_cut

[Neckline]
v_neck, turtleneck, crewneck, off_shoulder, halter_neck, boat_neck,
square_neck, cowl_neck, mock_neck, one_shoulder, scoop_neck, sweetheart_neckline

[Sleeve]
long_sleeve, short_sleeve, sleeveless, three_quarter_sleeve, raglan_sleeve,
dolman_sleeve, cap_sleeve, flutter_sleeve, cold_shoulder, dropped_shoulder

[Occasion — broad]
everyday, workwear, going_out, travel, outdoor, sport, beach, occasion

[Occasion — nuance]
date_night, cocktail, brunch, festival_wear, office_ready, transitional,
gym_wear, yoga_wear, running_wear, swim_wear, resort_wear, evening_wear,
wedding_guest, party_wear, work_from_home, ski_wear, activewear_set,
capsule_piece, night_out, formal_occasion

[Values]
sustainable, investment_piece, trend_driven, heritage_craft, luxury_status,
budget_conscious, logo_forward, size_inclusive, gender_neutral, performance_tech,
wardrobe_staple, statement_piece, limited_edition, handmade_detail, capsule_wardrobe

[Pattern]
floral_print, striped_pattern, checked_pattern, animal_print, solid_color,
abstract_print, paisley_print, baroque_print, tie_dye, ombre_effect, polka_dot,
camouflage, tropical_print, fairisle_knit, argyle_pattern, colour_block,
acid_wash, graphic_print, logo_repeat, leopard_spot, zebra_stripe,
toile_print, damask_print, windowpane_check

[Fabric — material]
denim_fabric, linen_fabric, velvet_fabric, satin_fabric, leather_fabric,
knitwear_fabric, silk_fabric, cotton_fabric, modal_fabric, lyocell_fabric,
viscose_fabric, wool_fabric, cashmere_fabric, suede_fabric, nylon_fabric,
jersey_fabric, crepe_fabric, brocade_fabric, corduroy_fabric, organza_fabric,
chiffon_fabric, poplin_fabric, flannel_fabric, fleece_fabric, recycled_fabric,
stretch_fabric

[Fabric — texture]
sheer_fabric, mesh_detail, ribbed_texture, quilted_detail, faux_fur_trim,
distressed_finish, woven_texture, technical_fabric, jacquard_weave, burnout_effect,
metallic_sheen, glitter_detail, sequin_embellishment, beaded_detail, laser_cut,
perforated_detail, frayed_edge, brushed_finish

[Length]
mini_length, midi_length, maxi_length

[Construction & detail]
ruffled, belted, crochet_detail, embroidered_detail, pleated_detail, wrap_style,
cutout_detail, asymmetric_hem, tie_waist, puff_sleeve, button_front,
double_breasted, single_breasted, zip_front, cargo_pockets, patch_pocket,
chest_pocket, notch_lapel, mandarin_collar, shawl_collar, gathered_bodice,
smocked_detail, pintuck_detail, shirred_detail, drawstring_waist, elastic_waist,
corset_detail, gathered_waist, raw_edge_hem, fringe_trim, lace_trim,
contrast_stitch, open_back, gold_hardware, silver_hardware, chain_trim,
buckle_detail, stud_embellishment
"""

_ARCHETYPES_SECTION = """
minimalist, streetwear, goth, dark_academia, preppy, bohemian,
classic_business, athleisure, romantic_feminine, grunge, cottagecore,
y2k_retro, coastal_resort, punk_edgy, old_money_quiet_luxury, techwear,
western_country, glam_evening, artsy_eclectic, scandinavian_minimal,
military_utility, pinup_vintage_50s, skater_surf, japanese_street_avant_garde,
tropical_vacation, biker_moto, normcore, art_deco_glamour, gorpcore,
balletcore, office_siren, festival_eclectic, scholarly_prep_ivy
"""


def _build_system_prompt(taxonomy_mode: str) -> str:
    if taxonomy_mode == "keywords":
        style_scores_spec = f"""  "style_scores": {{
    "keywords": {{sparse dict keyword: score 0.1-1.0, omit zeros, 8-15 typical}}
  }}
Valid keywords:{_KEYWORDS_SECTION}"""
    elif taxonomy_mode == "archetypes":
        style_scores_spec = f"""  "style_scores": {{
    "archetypes": {{weighted dict archetype_id: score 0.0-1.0, top 2-4 sum ~1.0}}
  }}
Valid archetype ids:{_ARCHETYPES_SECTION}"""
    else:  # "both"
        style_scores_spec = f"""  "style_scores": {{
    "keywords": {{sparse dict keyword: score 0.1-1.0, omit zeros, 8-15 typical}},
    "archetypes": {{weighted dict archetype_id: score 0.0-1.0, top 2-4 sum ~1.0}}
  }}
Valid keywords:{_KEYWORDS_SECTION}
Valid archetype ids:{_ARCHETYPES_SECTION}"""

    return f"""You are a professional fashion stylist analyzing a photo to produce a structured styling brief.

Return ONLY a single valid JSON object — no prose, no markdown fences.

Output schema:
{{
  "current_outfit": [
    {{
      "item_type": "top|bottom|dress|jacket|shoes|accessory|other",
      "color": "<primary color>",
      "color_family": "black|white|pastel|jewel_tone|bold|earth_tone|neutral|warm_neutral|cool_neutral|denim_blue|navy|multi",
      "silhouette": "fitted|oversized|structured|flowy|voluminous|cropped|straight|relaxed|regular",
      "pattern": "solid|stripes|check|floral|graphic|abstract|animal|none",
      "fabric": "denim|leather|knit|linen|velvet|satin|technical|cotton|unknown",
      "formality": "black_tie|formal|business_casual|smart_casual|casual|loungewear"
    }}
  ],
{style_scores_spec},
  "gender": "male|female|unisex",
  "coloring": {{
    "skin_tone": "warm|cool|neutral",
    "contrast_level": "low|medium|high",
    "confidence": 0.0
  }},
  "context": {{
    "setting": "<free text e.g. urban daytime>",
    "inferred_formality": "black_tie|formal|business_casual|smart_casual|casual|loungewear",
    "confidence": 0.0
  }},
  "price_tier": {{
    "inferred_tier": "budget|mid|premium|luxury",
    "confidence": 0.0,
    "signals": "<short note on what drove the read>"
  }},
  "interpretation": "<2-4 sentences: what you see in the photo, the overall aesthetic read, why you scored the top keywords the way you did, and what that says about the person's style>",
  "overall_confidence": 0.0,
  "low_confidence_fallback": false,
  "recommendations": [
    {{
      "slot": "outerwear|footwear|accessory|layering|bottom|top",
      "reasoning": "<1-2 sentences: why this slot, color complement, context>",
      "target_attributes": {{
        "item_type": "<specific item>",
        "color": "<target color>",
        "color_family": "<color_family>",
        "silhouette": "<silhouette>",
        "pattern": "<pattern>",
        "fabric": "<fabric>",
        "formality": "<formality>"
      }}
    }}
  ]
}}

Rules:
- current_outfit: every visible garment as a separate object in the Layer-1 vocabulary
- style_scores: scored from the outfit as a single observation; blends (2 archetypes at 0.4-0.5) are normal
- coloring: person's natural coloring, independent of outfit
- price_tier: strictly independent of style_scores — aesthetic and price are separate signals
- overall_confidence < 0.2 → set low_confidence_fallback true
- recommendations: 2-4 gap-based slots — items that COMPLEMENT the outfit, not duplicates of it
- target_attributes uses the same vocabulary as current_outfit for direct retrieval matching
- Never recommend items already worn (same item_type + similar color_family + similar silhouette)
- Silhouette reasoning in the reasoning field must be garment-focused, never body-focused
"""


def _encode_image(frame: np.ndarray) -> str:
    h, w = frame.shape[:2]
    max_side = 1024
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.standard_b64encode(buf.tobytes()).decode("utf-8")


def _parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[analyzer] JSON parse error: {e}\nRaw: {raw[:300]}")
        return None


def _validate_brief(brief: dict, taxonomy_mode: str) -> dict:
    """Fill missing fields with safe defaults so downstream never KeyErrors."""
    brief.setdefault("gender", "unisex")
    brief.setdefault("current_outfit", [])
    brief.setdefault("style_scores", {})
    if taxonomy_mode in ("keywords", "both"):
        brief["style_scores"].setdefault("keywords", {})
    if taxonomy_mode in ("archetypes", "both"):
        brief["style_scores"].setdefault("archetypes", {})
    brief.setdefault("coloring", {"skin_tone": "neutral", "contrast_level": "medium", "confidence": 0.0})
    brief.setdefault("context", {"setting": "unknown", "inferred_formality": "casual", "confidence": 0.0})
    brief.setdefault("price_tier", {"inferred_tier": "mid", "confidence": 0.0, "signals": ""})
    brief.setdefault("overall_confidence", 0.0)
    brief.setdefault("low_confidence_fallback", brief.get("overall_confidence", 0.0) < 0.2)
    brief.setdefault("recommendations", [])
    return brief


class StyleAnalyzer:
    def __init__(self, backend: str = BACKEND, taxonomy_mode: str = TAXONOMY_MODE):
        self.backend = backend
        self.taxonomy_mode = taxonomy_mode
        self.system_prompt = _build_system_prompt(taxonomy_mode)

        if backend == "claude":
            import anthropic
            self.client = anthropic.Anthropic()
        elif backend == "gemini":
            from google import genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set.")
            self.gemini_client = genai.Client(api_key=api_key)
        elif backend == "ollama":
            pass
        else:
            raise ValueError(f"Unknown backend: '{backend}'")

    def analyze(self, crop: np.ndarray) -> dict | None:
        image_data = _encode_image(crop)
        if self.backend == "claude":
            raw = self._call_claude(image_data)
        elif self.backend == "gemini":
            raw = self._call_gemini(crop)
        else:
            raw = self._call_ollama(image_data)

        if raw is None:
            return None
        return _validate_brief(raw, self.taxonomy_mode)

    def _call_claude(self, image_data: str) -> dict | None:
        import anthropic
        try:
            msg = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                system=self.system_prompt,
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
                        {"type": "text", "text": "Produce the stylist brief JSON for this person's outfit."},
                    ],
                }],
            )
            raw_text = msg.content[0].text
            print(f"[analyzer] raw response length={len(raw_text)}, stop_reason={msg.stop_reason}")
            print(f"[analyzer] raw[:500]={raw_text[:500]}")
            return _parse_json(raw_text)
        except anthropic.APIError as e:
            print(f"[analyzer] Claude API error: {e}")
            return None

    def _call_gemini(self, crop: np.ndarray) -> dict | None:
        from google import genai
        from google.genai import types
        import io
        from PIL import Image

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        buf.seek(0)

        prompt = self.system_prompt + "\n\nProduce the stylist brief JSON for this person's outfit."
        try:
            resp = self.gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                    prompt,
                ],
            )
            return _parse_json(resp.text)
        except Exception as e:
            print(f"[analyzer] Gemini error: {e}")
            return None

    def _call_ollama(self, image_data: str) -> dict | None:
        import urllib.request
        import urllib.error

        prompt = self.system_prompt + "\n\nProduce the stylist brief JSON for this person's outfit."
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "images": [image_data],
            "stream": False,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return _parse_json(result.get("response", ""))
        except urllib.error.URLError:
            print("[analyzer] Ollama not reachable.")
            return None
        except Exception as e:
            print(f"[analyzer] Ollama error: {e}")
            return None
