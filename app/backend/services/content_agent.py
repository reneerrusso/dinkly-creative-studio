from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.backend.models.content_agent import ContentFormat
from app.backend.providers.reasoning_model import ReasoningModelProvider
from app.backend.services.repository_service import RepositoryError
from app.backend.services.secrets_service import SecretsService


class ContentModelProvider(ReasoningModelProvider):
    """Backward-compatible name for the canonical reasoning-provider boundary."""


class UnavailableContentModelProvider(ContentModelProvider):
    @property
    def configured(self) -> bool:
        return False

    def generate_candidates(self, content_format: ContentFormat, brief: dict[str, Any], count: int) -> list[dict[str, Any]]:
        raise RepositoryError("Concept Generator needs an AI provider to create new concepts.")


class DevelopmentFixtureProvider(ContentModelProvider):
    """Deterministic, clearly labeled data for tests and UI demonstrations only."""

    name = "development-fixtures"
    development_fixture = True

    @property
    def configured(self) -> bool:
        return True

    def generate_candidates(self, content_format: ContentFormat, brief: dict[str, Any], count: int) -> list[dict[str, Any]]:
        builders = {
            ContentFormat.WITH_YOU: self._with_you,
            ContentFormat.BEFORE_AFTER: self._before_after,
            ContentFormat.FIVE_STORY: self._five_story,
        }
        return builders[content_format](count)

    def _with_you(self, count: int) -> list[dict[str, Any]]:
        topics = [
            ("PORCH SITTING", "front porch", ["two porch chairs", "side table", "potted fern"]),
            ("THRIFTING", "quiet thrift shop", ["clothing rack", "full-length mirror", "woven basket"]),
            ("SUNSET WALKS", "lakeside path", ["park bench", "lamp post", "fallen leaves"]),
            ("BAKING", "small kitchen", ["mixing bowl", "baking tray", "oven mitt"]),
            ("BOOKSTORES", "cozy bookstore", ["low bookshelf", "reading chair", "book stack"]),
            ("PICNICS", "grassy park", ["checked blanket", "picnic basket", "thermos"]),
            ("GARDENING", "backyard garden", ["watering can", "raised planter", "garden stool"]),
            ("TRAIN RIDES", "quiet train carriage", ["window seat", "small travel bag", "paper tickets"]),
            ("FARM STANDS", "roadside produce stand", ["wooden table", "apple crates", "canvas tote"]),
            ("POWER OUTAGES", "dim living room", ["flashlight", "floor cushions", "battery lantern"]),
            ("PUZZLES", "dining nook", ["round table", "two chairs", "puzzle box"]),
            ("WINDOW SHOPPING", "small-town sidewalk", ["shop window", "awning", "street planter"]),
            ("SPRING CLEANING", "sunny bedroom", ["laundry basket", "open wardrobe", "storage box"]),
            ("LATE-NIGHT DINERS", "rounded diner booth", ["table jukebox", "two plates", "napkin holder"]),
            ("MUSEUM DAYS", "minimal gallery", ["framed painting", "gallery bench", "museum map"]),
            ("CAMPING", "quiet campsite", ["small tent", "camp chairs", "lantern"]),
            ("FLOWER MARKETS", "outdoor flower stall", ["flower buckets", "striped awning", "paper wrap"]),
            ("FERRY RIDES", "open ferry deck", ["painted railing", "bench", "life ring"]),
            ("MINI GOLF", "simple mini-golf lane", ["putters", "golf ball", "windmill obstacle"]),
            ("YARD SALES", "suburban driveway", ["folding table", "cardboard sign", "small lamp"]),
            ("KARAOKE", "private karaoke room", ["microphone", "small screen", "low table"]),
            ("DOG-SITTING", "entryway", ["dog bed", "leash hook", "water bowl"]),
            ("STORM WATCHING", "covered balcony", ["two chairs", "blanket", "rainy window"]),
            ("POTTERY PAINTING", "craft studio", ["work table", "two stools", "paint cups"]),
        ]
        results = []
        for index, (title, setting, props) in enumerate(topics[:count]):
            results.append({
                "format": "with_you", "title_left": title, "title_right": f"{title} WITH YOU", "left_character": "girl" if index % 3 == 0 else "boy",
                "left_action": f"stands quietly in the {setting}, focused on the ordinary activity", "left_setting": setting, "left_props": props[:3], "left_emotion": "neutral or mildly bored—never happy",
                "right_action": "shares the same activity with the other DINKLY, leaning close and laughing", "right_setting": setting, "right_props": props[:3], "right_emotion": "warm, playful, and connected",
                "right_characters": ["boy", "girl"], "shared_environment": f"the same {setting} continues across both sides", "environmental_contrast": "The left stays sparse while the right adds only the shared activity and signs of companionship.", "background_color": ["warm cream", "powder blue", "soft lavender", "warm sage"][index % 4], "accent_color": ["muted coral", "dusty blue", "muted mustard"][index % 3], "camera_angle": "medium straight-on",
                "emotional_insight": "The activity barely changes; companionship changes how it feels.", "why_it_may_work": "A recognizable routine creates immediate contrast while the scene stays easy to read.", "timely_signal": None, "social_learning_ids": [], "preference_matches": [], "execution_risks": ["Keep props behind or beside the characters; no human anatomy."],
            })
        return results


class OpenAIContentModelProvider(ContentModelProvider):
    """Real production provider. Credentials are resolved on every call for background-worker parity."""

    name = "openai"
    real_provider = True

    def __init__(self, secrets: SecretsService, transport: httpx.BaseTransport | None = None) -> None:
        self.secrets = secrets
        self.transport = transport
        self.estimated_batch_cost = float(os.getenv("DINKLY_CONTENT_ESTIMATED_BATCH_COST", "1.0"))

    @property
    def configured(self) -> bool:
        return bool(self.secrets.get_content_credentials()["OPENAI_API_KEY"])

    @property
    def model(self) -> str:
        return self.secrets.get_content_credentials()["DINKLY_CONTENT_MODEL"]

    def health(self) -> dict[str, Any]:
        status = self.secrets.get_content_provider_status()
        return {
            **status,
            "provider": self.name,
            "real_provider": True,
            "estimated_batch_cost": self.estimated_batch_cost,
            "connection_status": "Configured — connection not tested" if self.configured else "Not configured",
        }

    def test_connection(self) -> dict[str, Any]:
        if not self.configured:
            return {**self.health(), "connected": False, "message": "OpenAI API key is not configured."}
        payload = self._request("Return exactly the word READY.", max_output_tokens=8)
        output = self._output_text(payload).strip()
        return {**self.health(), "connected": output == "READY", "message": "Model responded." if output == "READY" else "Model returned an unexpected response."}

    def generate_candidates(self, content_format: ContentFormat, brief: dict[str, Any], count: int) -> list[dict[str, Any]]:
        if not self.configured:
            raise RepositoryError("Concept Generator needs an OpenAI API key to create new concepts.")
        schema = _candidate_schema(content_format, count)
        instructions = _production_instructions(content_format, brief, count)
        payload = self._request(
            instructions,
            max_output_tokens=30000,
            text_format={"type": "json_schema", "name": "dinkly_concepts", "strict": True, "schema": schema},
        )
        try:
            parsed = json.loads(self._output_text(payload))
            candidates = parsed.get("candidates", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            raise RepositoryError("OpenAI returned invalid structured concept data.") from exc
        if not isinstance(candidates, list):
            raise RepositoryError("OpenAI returned an invalid concept list.")
        return candidates

    def _request(self, prompt: str, *, max_output_tokens: int, text_format: dict[str, Any] | None = None) -> dict[str, Any]:
        credentials = self.secrets.get_content_credentials()
        request: dict[str, Any] = {
            "model": credentials["DINKLY_CONTENT_MODEL"],
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }
        if text_format:
            request["text"] = {"format": text_format}
        try:
            with httpx.Client(timeout=httpx.Timeout(180.0, connect=15.0), transport=self.transport) as client:
                response = client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {credentials['OPENAI_API_KEY']}", "Content-Type": "application/json"},
                    json=request,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            message = self.secrets.redact(exc.response.text)[:500]
            raise RepositoryError(f"OpenAI request failed ({exc.response.status_code}): {message}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RepositoryError(f"OpenAI connection failed: {self.secrets.redact(str(exc))}") from exc

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if isinstance(content.get("text"), str):
                    return content["text"]
        raise RepositoryError("OpenAI response did not contain text output.")


class _CompleteDevelopmentFixtureProvider(DevelopmentFixtureProvider):
    def _before_after(self, count: int) -> list[dict[str, Any]]:
        topics = [
            ("ENTRYWAYS", "apartment entryway", ["shoe mat", "wall hooks", "small console"]),
            ("GROCERY LISTS", "kitchen counter area", ["notepad", "fruit bowl", "refrigerator"]),
            ("BIRTHDAYS", "small dining room", ["round table", "single candle", "paper garland"]),
            ("SICK DAYS", "bedroom floor beside the bed", ["tissue box", "water glass", "bedside lamp"]),
            ("ROAD TRIPS", "roadside rest stop", ["travel bags", "folded map", "picnic table"]),
            ("SUNDAY NIGHTS", "living-room floor", ["floor cushions", "low side table", "calendar"]),
            ("NEW APARTMENTS", "empty apartment", ["moving box", "floor lamp", "potted plant"]),
            ("LUNCH BREAKS", "office courtyard", ["bench", "lunch bags", "planter"]),
            ("HOLIDAY MORNINGS", "home entry room", ["garland", "gift bag", "side table"]),
            ("RAINY COMMUTES", "covered bus stop", ["bench", "umbrella stand", "route sign"]),
            ("DINNER TABLES", "dining nook", ["round table", "two chairs", "serving dish"]),
            ("WEEKDAY EVENINGS", "small kitchen", ["stove", "prep table", "radio"]),
            ("BALCONIES", "apartment balcony", ["one chair", "second chair", "plant shelf"]),
            ("PACKING", "bedroom", ["open suitcase", "clothes basket", "travel checklist"]),
            ("FIRST SNOW", "front stoop", ["doormat", "porch light", "snow shovel"]),
            ("MORNING LIGHT", "breakfast nook", ["small table", "curtains", "ceramic pitcher"]),
            ("LONG WEEKS", "home office", ["desk", "desk chair", "tea tray"]),
            ("ERRAND DAYS", "neighborhood sidewalk", ["canvas bags", "shop sign", "street bench"]),
            ("UNPACKING", "new bedroom", ["two boxes", "low dresser", "framed photo"]),
            ("QUIET HOUSES", "hallway", ["console table", "lamp", "two framed photos"]),
            ("SUMMER NIGHTS", "back patio", ["patio chairs", "string lights", "lemonade pitcher"]),
            ("TAKEOUT NIGHTS", "dining nook", ["takeout cartons", "two chairs", "small table"]),
            ("BAD NEWS", "quiet kitchen", ["two stools", "counter", "flower vase"]),
            ("GOOD NEWS", "front porch", ["mail envelope", "two chairs", "potted flowers"]),
        ]
        results = []
        for index, (title, setting, props) in enumerate(topics[:count]):
            results.append({
                "format": "before_after", "title_left": f"{title} BEFORE YOU", "title_right": f"{title} AFTER YOU", "left_character": "boy",
                "left_action": f"moves through the sparse {setting} alone with one unfinished task", "left_setting": setting, "left_props": props[:2], "left_emotion": "quiet and neutral—not devastated",
                "right_action": f"shares the same {setting} with Girl DINKLY as they complete the routine together", "right_setting": setting, "right_props": props[:3], "right_emotion": "settled, warm, and at home",
                "right_characters": ["boy", "girl"], "shared_environment": f"the same {setting}, made fuller through shared life", "environmental_contrast": "The same room gains a few shared signs of routine and care without becoming luxurious.", "background_color": ["warm sand", "blush pink", "pistachio", "pastel peach"][index % 4], "accent_color": ["dusty rose", "muted teal", "muted coral"][index % 3], "camera_angle": "medium straight-on",
                "emotional_insight": "Love makes an ordinary part of life feel inhabited and personal.", "why_it_may_work": "The same setting makes the emotional transformation instantly legible.", "timely_signal": None, "social_learning_ids": [], "preference_matches": [], "execution_risks": ["Keep the transformation warm rather than materialistic or visually overloaded."],
                "transformation": "The environment gains shared signs of care without becoming luxurious.", "before_state": "functional but sparse and solitary", "after_state": "personal, shared, and comfortably lived-in",
            })
        return results

    def _five_story(self, count: int) -> list[dict[str, Any]]:
        themes = [
            ("THE LITTLE WAYS YOU WAIT FOR ME", "Waiting becomes a quiet language of care", ["doorway", "bus stop", "kitchen", "bookstore", "bedroom"]),
            ("HOW WEEKENDS BECAME OURS", "Small weekend rituals slowly become a shared life", ["market", "kitchen", "park", "laundry room", "porch"]),
            ("THE FIRST THINGS WE SHARED", "Ordinary objects begin to carry a shared history", ["café", "hallway", "bookshelf", "kitchen", "bedroom"]),
            ("WHEN I KNEW I WAS HOME", "Home reveals itself through repeated acts of belonging", ["entryway", "kitchen", "living room", "balcony", "bedroom"]),
            ("FIVE WAYS YOU MAKE HARD DAYS SOFTER", "Care appears through practical, quiet choices", ["bus stop", "kitchen", "desk", "front porch", "bedroom"]),
            ("THE SEASON WE FELL INTO A ROUTINE", "A relationship grows through seasonal repetition", ["sidewalk", "market", "kitchen", "porch", "bedroom"]),
            ("THINGS WE STARTED LEAVING AT EACH OTHER'S PLACE", "Belongings become evidence of belonging", ["bathroom", "entryway", "bookshelf", "kitchen", "closet"]),
            ("OUR FAVORITE KIND OF PLANS", "Unplanned time becomes the plan they treasure", ["kitchen", "park", "bookstore", "diner", "home"]),
            ("THE WAYS WE SAY I MISSED YOU", "Reunions live in tiny familiar gestures", ["doorway", "train platform", "kitchen", "porch", "bedroom"]),
            ("HOW WE LEARNED EACH OTHER'S BAD DAYS", "Care becomes more precise as two people pay attention", ["office exit", "grocery store", "kitchen", "living room", "bedroom"]),
            ("A YEAR OF ORDINARY FIRSTS", "A shared year is remembered through everyday milestones", ["park", "kitchen", "beach", "market", "home"]),
            ("THE THINGS YOU ALWAYS REMEMBER", "Small remembered preferences communicate lasting attention", ["café", "bookstore", "market", "kitchen", "bedroom"]),
            ("WHEN TWO ROUTINES BECAME ONE", "Separate habits gradually make room for each other", ["bathroom", "kitchen", "hallway", "desk", "bedroom"]),
            ("OUR QUIETEST ADVENTURES", "Simple outings feel expansive when they are shared", ["trail", "ferry", "museum", "diner", "porch"]),
            ("FIVE TIMES YOU CHOSE US", "Commitment is shown through small daily decisions", ["sidewalk", "kitchen", "store", "porch", "home"]),
            ("THE HOME WE MADE IN SMALL PIECES", "A shared home forms one practical detail at a time", ["entryway", "kitchen", "closet", "bookshelf", "bedroom"]),
            ("THINGS THAT FEEL LIKE SUNDAY", "A relationship is held together by restorative rituals", ["bedroom", "kitchen", "market", "park", "porch"]),
            ("HOW WE CELEBRATE THE SMALL WINS", "Encouragement makes modest victories feel worth remembering", ["desk", "kitchen", "store", "diner", "home"]),
            ("THE PLACES WE ALWAYS FIND EACH OTHER", "Familiar locations become emotional landmarks", ["bus stop", "bookstore", "market", "park", "home"]),
            ("WHEN THE WEATHER KEPT US CLOSE", "Changing weather creates new forms of togetherness", ["sidewalk", "porch", "kitchen", "window", "bedroom"]),
            ("THE BEST PART OF COMING BACK", "The return matters because someone familiar is waiting", ["train platform", "entryway", "kitchen", "porch", "bedroom"]),
            ("FIVE ORDINARY PROMISES", "Love is expressed through reliable everyday follow-through", ["calendar", "market", "kitchen", "doorway", "home"]),
            ("THE SUMMER WE STAYED OUT LATE", "Long light turns small outings into shared memories", ["market", "beach", "diner", "ferry", "porch"]),
            ("WHAT WE KEEP FOR EACH OTHER", "Saving a seat, snack, or story becomes a form of devotion", ["train", "kitchen", "bookstore", "porch", "bedroom"]),
        ]
        results = []
        for index, (title, premise, settings) in enumerate(themes[:count]):
            comics = []
            actions = ["waits with a saved seat", "sets aside the other’s favorite item", "makes room beside their own things", "notices a tired expression and quietly helps", "rests close together after the ordinary day"]
            props = [["bench", "small bag"], ["side table", "wrapped snack"], ["low shelf", "two books"], ["lamp", "water glass"], ["blanket", "bedside table"]]
            for beat in range(5):
                comics.append({"title": f"Comic {beat + 1}", "scene": f"Boy and Girl DINKLY are in the {settings[beat]}; one {actions[beat]} while the other responds with a small body lean.", "characters": ["Dinko", "Dinka"], "setting": settings[beat], "props": props[beat], "emotion": ["anticipation", "recognition", "belonging", "care", "quiet contentment"][beat], "camera_angle": "medium straight-on"})
            results.append({
                "format": "five_story", "story_title": title, "left_character": "boy", "left_props": [], "right_props": [], "background_color": ["warm cream", "soft lavender", "warm sage", "powder blue"][index % 4], "accent_color": ["muted coral", "muted mustard", "dusty rose"][index % 3], "camera_angle": "medium straight-on", "emotional_premise": premise, "why_it_may_work": "The sequence builds through familiar actions toward one clear emotional conclusion.", "timely_signal": None, "social_learning_ids": [], "preference_matches": [], "execution_risks": ["Keep each comic independently simple and preserve exact character scale across all five."], "comics": comics, "final_payoff": "The smallest repeated choices are how an ordinary life becomes ours.", "visual_continuity": "Keep Dinka and Dinko equal in size with the same home-world furniture language and character model throughout.", "background_strategy": "Use one consistent pastel family across all five comics with one restrained accent color.",
            })
        return results


class DevelopmentFixtureProvider(_CompleteDevelopmentFixtureProvider):
    """Complete deterministic fixture provider; never eligible for production scheduling."""

    pass


def content_provider_from_environment(repository=None) -> ContentModelProvider:
    if os.getenv("DINKLY_CONTENT_FIXTURES") == "1":
        return DevelopmentFixtureProvider()
    if repository is not None:
        return OpenAIContentModelProvider(SecretsService(repository))
    return UnavailableContentModelProvider()


def _string(min_length: int = 1) -> dict[str, Any]:
    return {"type": "string", "minLength": min_length}


def _string_array(max_items: int = 5) -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "maxItems": max_items}


def _nullable_string() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _candidate_schema(content_format: ContentFormat, count: int) -> dict[str, Any]:
    shared = {
        "background_color": _string(), "accent_color": _string(), "camera_angle": _string(),
        "why_it_may_work": _string(12), "execution_risks": _string_array(), "timely_signal": _nullable_string(),
        "social_learning_ids": _string_array(8), "preference_matches": _string_array(8), "left_character": {"type": "string", "enum": ["boy", "girl"]},
    }
    if content_format == ContentFormat.FIVE_STORY:
        beat_properties = {"title": _string(), "scene": _string(12), "characters": _string_array(2), "setting": _string(2), "props": _string_array(), "emotion": _string(2), "camera_angle": _string()}
        properties = {**shared, "format": {"type": "string", "enum": ["five_story"]}, "story_title": _string(), "emotional_premise": _string(12), "comics": {"type": "array", "minItems": 5, "maxItems": 5, "items": {"type": "object", "additionalProperties": False, "properties": beat_properties, "required": list(beat_properties)}}, "final_payoff": _string(8), "visual_continuity": _string(12), "background_strategy": _string(8), "left_props": _string_array(), "right_props": _string_array()}
    else:
        properties = {
            **shared, "format": {"type": "string", "enum": [content_format.value]}, "title_left": _string(), "title_right": _string(),
            "left_action": _string(12), "left_setting": _string(2), "left_props": _string_array(), "left_emotion": _string(2),
            "right_characters": {"type": "array", "items": {"type": "string", "enum": ["boy", "girl"]}, "minItems": 2, "maxItems": 2},
            "right_action": _string(12), "right_setting": _string(2), "right_props": _string_array(), "right_emotion": _string(2),
            "shared_environment": _string(8), "environmental_contrast": _string(8), "emotional_insight": _string(12),
        }
        if content_format == ContentFormat.BEFORE_AFTER:
            properties.update({"before_state": _string(4), "after_state": _string(4), "transformation": _string(8)})
    item = {"type": "object", "additionalProperties": False, "properties": properties, "required": list(properties)}
    return {"type": "object", "additionalProperties": False, "properties": {"candidates": {"type": "array", "minItems": count, "maxItems": count, "items": item}}, "required": ["candidates"]}


def _production_instructions(content_format: ContentFormat, brief: dict[str, Any], count: int) -> str:
    return (
        "You are the DINKLY Concept Generator. Produce original STORY CONCEPTS, never image prompts. "
        f"Return exactly {count} {content_format.value} candidates using the supplied JSON schema. "
        "Every scene must be production-ready: one clear action per character, a named setting, 2–5 purposeful scene props, readable emotions, realistic prop scale, and one continuous pastel environment. "
        "Dinko and Dinka remain equal-size bright-yellow round characters with orange spots, nub arms and attached nub feet; no human anatomy. "
        "For split concepts, the left character is sad, bored, or neutral—never happy—and the right side changes mainly through companionship. "
        "Five-comic candidates must be one coherent emotional story with exactly five individually generatable beats and strong visual continuity. "
        "Avoid semantic duplicates and do not copy supplied winners. Keep text concise and scenes visually specific. "
        "Only cite social-learning IDs and current trends that appear in the brief; otherwise return empty evidence arrays and null timely_signal. "
        f"Creative brief: {json.dumps(brief, ensure_ascii=False)}"
    )
