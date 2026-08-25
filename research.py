"""
Phase 1: research.

Uses OpenAI's web search tool (Responses API) to pull current Jakarta/Jabodetabek
property and lifestyle information, prioritising:
  1. Government / official sources
  2. Official company announcements
  3. Reputable Indonesian media
  4. Reputable property sources

Two-step process:
  1. Responses API + web_search_preview tool -> raw findings text (with sources).
  2. Chat Completions in JSON mode -> structure that text into a list of notes.

This keeps JSON reliability high without depending on strict-JSON + tool-use
being combinable in a single call.
"""
import json

from openai import OpenAI

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

SEARCH_INSTRUCTIONS = """You are a research assistant for a Jakarta property content agent.
Find CURRENT, VERIFIABLE facts about Jakarta/Jabodetabek property, infrastructure, and
lifestyle topics.

Rules:
- Prioritise official/government sources, official company announcements, reputable
  Indonesian media, and reputable property publications, in that order.
- Never invent statistics, prices, infrastructure timelines, or distances.
- For every fact, note where it came from (publication/source name) and roughly when.
- If you cannot verify something, do not include it.

Write your findings as plain text notes, one fact per line, including the source and
approximate date for each."""

STRUCTURE_SYSTEM_PROMPT = """Convert the research notes below into structured JSON.

Output a JSON object with a single key "notes", a list of objects with fields:
  "topic", "fact", "source", "date_or_recency", "url" (url can be "" if not given).

Only include facts that already have a clear source in the input — do not invent or
add anything not present in the input text."""


def _client():
    return OpenAI(api_key=config.OPENAI_API_KEY)


def research_jakarta_topics(topics=None, max_notes=25):
    topics = topics or RESEARCH_TOPICS
    client = _client()

    search_prompt = (
        "Research current information on the following Jakarta/Jabodetabek topics:\n- "
        + "\n- ".join(topics)
        + f"\n\nReturn up to {max_notes} of the most relevant, recent, verifiable facts."
    )

    # Step 1: web-search-grounded findings.
    search_response = client.responses.create(
        model=config.OPENAI_MODEL,
        tools=[{"type": "web_search_preview"}],
        instructions=SEARCH_INSTRUCTIONS,
        input=search_prompt,
    )
    raw_findings = (search_response.output_text or "").strip()

    if not raw_findings:
        return []

    # Step 2: structure into JSON.
    structure_response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": STRUCTURE_SYSTEM_PROMPT},
            {"role": "user", "content": raw_findings},
        ],
    )

    try:
        data = json.loads(structure_response.choices[0].message.content)
        notes = data.get("notes", [])
        if isinstance(notes, list):
            return notes
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fall back to an empty list rather than crashing the daily job — concepts
    # will lean on framed opinion instead of fabricated stats.
    return []
