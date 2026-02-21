"""LLM-powered multilingual item normalization into English product intelligence."""

import json
import logging
from dataclasses import dataclass
from typing import Any

import litellm
from pydantic import BaseModel, Field

from src.config import settings
from src.services.category_taxonomy import DEFAULT_CATEGORY_TREE

logger = logging.getLogger(__name__)

INTELLIGENCE_PROMPT = """You are a grocery item normalization and categorization engine.
Given a list of raw purchase item names (possibly multilingual and noisy receipt text),
return a JSON object that maps each item into English canonical product intelligence.

Rules:
1) Canonical names MUST be in English.
2) Aliases MUST be in English and concise. Include the source-language alias only if useful.
3) Category path MUST be in English and use this format exactly: "Root > Subcategory".
4) Keep semantics faithful (e.g., "pechuga de pollo" -> "Chicken Breast").
5) Do not invent brands or quantities not present in the item.
6) If uncertain, use lower confidence and choose "Other > Uncategorized".
7) Output ONLY valid JSON.
"""

ALLOWED_CATEGORY_PATHS = [
    f"{root} > {child}"
    for root, children in DEFAULT_CATEGORY_TREE.items()
    for child in children
]


class IntelligenceItem(BaseModel):
    source_name: str
    canonical_name_en: str
    aliases_en: list[str] = Field(default_factory=list)
    category_path_en: str = "Other > Uncategorized"
    confidence: float = 0.0


@dataclass(slots=True)
class ItemIntelligence:
    source_name: str
    canonical_name_en: str
    aliases_en: list[str]
    category_path_en: str
    confidence: float


class ProductIntelligenceService:
    """Provides LLM-based item enrichment for product matching and categorization."""

    @staticmethod
    def _fallback_map(cleaned_names: list[str]) -> dict[str, ItemIntelligence]:
        return {
            name: ItemIntelligence(
                source_name=name,
                canonical_name_en=name.title(),
                aliases_en=[name],
                category_path_en="Other > Uncategorized",
                confidence=0.0,
            )
            for name in cleaned_names
        }

    @staticmethod
    def _pick(
        payload: dict[str, Any], keys: tuple[str, ...], default: Any = None
    ) -> Any:
        for key in keys:
            if key in payload and payload[key] is not None:
                return payload[key]
        return default

    def _normalize_response_items(
        self, raw_payload: dict[str, Any], cleaned_names: list[str]
    ) -> list[IntelligenceItem]:
        raw_items = raw_payload.get("items")
        if not isinstance(raw_items, list):
            return []

        normalized: list[IntelligenceItem] = []
        for idx, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                continue

            source_name = self._pick(
                raw_item,
                ("source_name", "source", "original_name", "input_name"),
                cleaned_names[idx] if idx < len(cleaned_names) else "",
            )
            canonical_name = self._pick(
                raw_item,
                ("canonical_name_en", "canonical_name", "canonical"),
                str(source_name).strip().title(),
            )
            aliases = self._pick(raw_item, ("aliases_en", "aliases", "alias_list"), [])
            if isinstance(aliases, str):
                aliases = [aliases]
            if not isinstance(aliases, list):
                aliases = []

            category_path = self._pick(
                raw_item,
                ("category_path_en", "category_path", "category"),
                "Other > Uncategorized",
            )
            confidence = self._pick(raw_item, ("confidence", "score"), 0.0)

            normalized.append(
                IntelligenceItem(
                    source_name=str(source_name).strip(),
                    canonical_name_en=str(canonical_name).strip(),
                    aliases_en=[str(a).strip() for a in aliases if str(a).strip()],
                    category_path_en=str(category_path).strip()
                    or "Other > Uncategorized",
                    confidence=float(confidence),
                )
            )
        return normalized

    async def enrich_items(
        self, raw_item_names: list[str]
    ) -> dict[str, ItemIntelligence]:
        """Return item intelligence keyed by original source_name."""
        cleaned_names = [
            name.strip() for name in raw_item_names if name and name.strip()
        ]
        if not cleaned_names:
            return {}

        if (
            not settings.enable_item_intelligence
            or settings.openai_api_key.startswith("test-")
            or settings.gemini_api_key.startswith("test-")
        ):
            return self._fallback_map(cleaned_names)

        try:
            response = await litellm.acompletion(
                model=settings.item_intelligence_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"{INTELLIGENCE_PROMPT}\n\n"
                            f"Use one of these category paths when possible: "
                            f"{', '.join(ALLOWED_CATEGORY_PATHS)}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"items": cleaned_names}, ensure_ascii=True
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or "{}"
            normalized_items = self._normalize_response_items(
                json.loads(raw_content), cleaned_names
            )
        except Exception as e:
            logger.info(f"Error: {e}")
            logger.exception(
                "Item intelligence LLM call failed; using fallback mapping."
            )
            return self._fallback_map(cleaned_names)

        mapped: dict[str, ItemIntelligence] = {}
        for item in normalized_items:
            canonical = (item.canonical_name_en or item.source_name).strip().title()
            aliases = [
                alias.strip()
                for alias in item.aliases_en
                if alias and alias.strip() and len(alias.strip()) <= 255
            ]
            if canonical.lower() not in {a.lower() for a in aliases}:
                aliases.append(canonical)

            mapped[item.source_name] = ItemIntelligence(
                source_name=item.source_name,
                canonical_name_en=canonical,
                aliases_en=aliases[:20],
                category_path_en=item.category_path_en or "Other > Uncategorized",
                confidence=max(0.0, min(1.0, float(item.confidence))),
            )

        # Ensure every source item has a fallback result.
        for name in cleaned_names:
            if name not in mapped:
                mapped[name] = ItemIntelligence(
                    source_name=name,
                    canonical_name_en=name.title(),
                    aliases_en=[name.title()],
                    category_path_en="Other > Uncategorized",
                    confidence=0.0,
                )

        return mapped
