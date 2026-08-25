"""
Phase 1: research.

Uses Claude with the web_search tool to pull current Jakarta/Jabodetabek
property and lifestyle information, prioritising:
  1. Government / official sources
  2. Official company announcements
  3. Reputable Indonesian media
  4. Reputable property sources

Returns a list of research notes, each with the claim and its source(s),
so content_generation.py can ground concepts in real citations instead
of inventing statistics.
"""
import json

import anthropic

import config

RESEARCH_TOPICS = [
    "MRT/LRT Jakarta updates",
    "toll road and new infrastructure Jabodetabek",
    "new commercial developments Jakarta",
    "Jakarta property market trends",
    "Jakarta air quality index",
    "mortgage / KPR rate developments Indonesia",
    "Jakarta urban development and demographic changes",
    "neighbourhood developments Jabodetabek",
]

SYSTEM_PROMPT = """You are a research assistant for a Jakarta property content agent.
Your only job is to find CURRENT, VERIFIABLE facts about Jakarta/Jabodetabek property,
infrastructure, and lifestyle topics, using web search.

Rules:
- Prioritise official/government sources, official company announcements, reputable
  Indonesian media, and reputable property publications, in that order.
- Never invent statistics, prices, infrastructure timelines, or distances.
- For every fact you report, note where it came from (publication/source name) and
  roughly when (date if available).
- If you cannot verify something, do not include it.

Output ONLY valid JSON: a list of objects with fields
  "topic", "fact", "source", "date_or_recency", "url"
Nothing else — no preamble, no markdown fences.
"""


def _client():
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def research_jakarta_topics(topics=None, max_notes=25):
    """
    Runs one Claude call with the web_search tool covering the topic list,
    and returns a parsed list of research note dicts.
    """
    topics = topics or RESEARCH_TOPICS
    client = _client()

    user_prompt = (
        "Research current information on the following Jakarta/Jabodetabek topics:\n- "
        + "\n- ".join(topics)
        + f"\n\nReturn up to {max_notes} of the most relevant, recent, verifiable facts "
        "as the JSON format described in your instructions."
    )

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Collect the final text block(s) — the model may interleave tool_use /
    # tool_result blocks with text; we only want the concluding JSON text.
    text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    raw = "\n".join(text_parts).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        notes = json.loads(raw)
        if isinstance(notes, list):
            return notes
    except json.JSONDecodeError:
        pass

    # Fall back to an empty list rather than crashing the daily job —
    # content_generation will simply have less grounding material, and
    # concepts should lean on framed opinion rather than fabricated stats.
    return []
