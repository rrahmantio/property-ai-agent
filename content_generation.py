"""
Phase 1 + 2: concept generation, scoring, selection, and Threads chain writing.

Follows the HOZ Property AI Content Agent V1 spec:
  - generate 6-8 concepts before writing anything
  - score against the weighted rubric
  - select the best 3-4
  - write each as a 4-7 part Threads text chain
  - run a quality check against the reject-list

Uses OpenAI Chat Completions in JSON mode. JSON mode requires a top-level
JSON *object*, so every prompt asks for a named key wrapping the list
(e.g. {"concepts": [...]}) and _call_json unwraps it.
"""
import json

from openai import OpenAI

import config

CONTENT_PILLARS = [
    "Jakarta property trends", "Property buyer psychology",
    "Millennials / Gen Z / Gen X / Baby Boomers", "Young-family lifestyle",
    "Business-owner and professional lifestyle", "Location intelligence",
    "Jakarta infrastructure", "Commuting", "Property economics",
    "Property myths", "Buying mistakes", "Neighborhood/community",
    "Housing affordability", "Interesting observations about Jakarta living",
]

AUDIENCE_EXAMPLES = [
    "Gen Z / first-time buyer", "Millennial couple", "Young family with children",
    "Established family", "Business owner", "Professional/executive",
    "Investor", "Baby boomer / downsizer",
]

SCORING_WEIGHTS = {
    "hook": 0.20,
    "audience_relevance": 0.20,
    "useful_insight": 0.20,
    "originality": 0.15,
    "jakarta_relevance": 0.10,
    "demand_potential": 0.15,
}

QUALITY_REJECT_RULES = """Reject content that is:
- generic
- overly salesy
- obviously AI-written
- repetitive
- factually unsupported
- clickbait without substance
- excessively formal
- stuffed with emojis
- political/controversial unnecessarily
- pretending to know something that isn't known"""

VOICE = ('Natural Indonesian, Jakarta-aware, insightful, conversational. Think: "property guy '
         'who actually understands how Jakarta people live." NOT a corporate real-estate '
         "marketing department.")


def _client():
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _call_json(system: str, user: str, key: str):
    """Calls OpenAI in JSON mode and returns the list stored under `key`."""
    client = _client()
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    data = json.loads(response.choices[0].message.content)
    result = data.get(key, [])
    return result if isinstance(result, list) else []


# ---------- 1. concept generation ----------

def generate_concepts(research_notes: list, recent_history: list) -> list:
    system = f"""You generate content concepts for HOZ Property, a Jakarta property business,
for its Threads account. Voice: {VOICE}

Content pillars to draw from: {", ".join(CONTENT_PILLARS)}
Audience archetypes (use as hypotheses, not stereotypes): {", ".join(AUDIENCE_EXAMPLES)}

Ground every concept in the supplied research notes where relevant. Never invent statistics,
prices, infrastructure timelines, or distances. If a claim can't be verified from the research
notes, frame it clearly as opinion/observation instead of fact.

Generate {config.NUM_CONCEPTS_MIN}-{config.NUM_CONCEPTS_MAX} DIFFERENT concepts. Do not repeat
a topic, hook, or angle already used in the recent history provided.

Each concept must have exactly these fields:
  title, target_audience, content_pillar, hook, core_insight, why_interesting,
  property_connection, research_sources (list of source names/urls used, [] if none)

Output a JSON object: {{"concepts": [ ...concept objects... ]}}"""

    user = json.dumps({
        "research_notes": research_notes,
        "recent_history": recent_history,
    }, ensure_ascii=False)

    return _call_json(system, user, key="concepts")


# ---------- 2. scoring ----------

def score_concepts(concepts: list) -> list:
    system = f"""Score each content concept against this weighted rubric (0-10 per criterion):
  hook (20%), audience_relevance (20%), useful_insight (20%), originality (15%),
  jakarta_relevance (10%), demand_potential (15% — likelihood it generates a property
  requirement lead, per the concept's property_connection)

For each concept in the input list, return an object with:
  title, scores (object with the 6 criteria as keys, 0-10 each), weighted_total (0-10,
  computed using the weights above), rationale (1 sentence)

Output a JSON object: {{"scores": [ ...score objects, same order as input... ]}}"""

    user = json.dumps(concepts, ensure_ascii=False)
    scored = _call_json(system, user, key="scores")

    # Attach scores back onto the original concept objects for downstream use.
    by_title = {s["title"]: s for s in scored}
    for c in concepts:
        s = by_title.get(c["title"])
        if s:
            c["_score"] = s
    return concepts


def select_top(concepts: list, n: int = None) -> list:
    n = n or config.NUM_SELECTED
    scored = [c for c in concepts if "_score" in c]
    scored.sort(key=lambda c: c["_score"]["weighted_total"], reverse=True)
    return scored[:n]


# ---------- 3. Threads chain writing ----------

def write_threads_chains(selected_concepts: list) -> list:
    system = f"""Write each concept as a Threads text-post chain (4-7 parts) for HOZ Property.
Voice: {VOICE}

Format:
  - Post 1: a hook/question with a light thread emoji (e.g. "🧵"), no numbering.
  - Posts 2..N-1: numbered like "1/5", "2/5" etc (N = total numbered posts after the hook),
    building the argument/insight naturally in conversational Bahasa Indonesia.
  - Final post: a useful concluding observation, then the soft CTA. The CTA must ask a
    variation of "Rumah seperti apa yang kalian cari?" and invite the reader to share their
    requirement (budget, lokasi, jumlah kamar, kebutuhan khusus), then include this exact
    link on its own line: {config.TYPEFORM_URL}

Do not invent statistics, prices, infrastructure timelines, or distances not present in the
concept's research_sources / core_insight. If unsupported, keep it as framed opinion.

For each concept, output an object with:
  title, audience (=target_audience), pillar (=content_pillar), hook,
  thread_posts (ordered list of strings, one per Threads post, 4-7 items total)

Output a JSON object: {{"chains": [ ...one object per input concept... ]}}"""

    user = json.dumps(selected_concepts, ensure_ascii=False)
    return _call_json(system, user, key="chains")


# ---------- 4. quality check ----------

def quality_check(chains: list) -> list:
    """
    Runs each chain through the reject-list. Returns the list of chains that pass,
    each annotated with '_quality' notes. Chains that fail are dropped (caller can
    log/regenerate if too many are lost).
    """
    system = f"""Review each Threads chain against these reject rules:
{QUALITY_REJECT_RULES}

Voice should be: {VOICE}

For each chain, return an object with: title, passes (true/false), issues (list of strings,
empty if passes=true).

Output a JSON object: {{"verdicts": [ ...one per input chain, same order... ]}}"""

    user = json.dumps(chains, ensure_ascii=False)
    verdicts = _call_json(system, user, key="verdicts")

    by_title = {v["title"]: v for v in verdicts}
    passed = []
    for chain in chains:
        v = by_title.get(chain["title"], {"passes": True, "issues": []})
        chain["_quality"] = v
        if v.get("passes", True):
            passed.append(chain)
    return passed
