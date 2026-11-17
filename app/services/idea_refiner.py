"""
Turns a quick capture (Idea) into a structured breakdown of features and issues
with estimates for a human developer, an AI coding agent, or both.

Breakdown shape (stored on Idea.breakdown and returned to the mobile app):

    {
      "title": "Short title",
      "summary": "One-paragraph restatement of the idea",
      "items": [
        {
          "id": "item-1",
          "type": "feature" | "issue" | "task",
          "title": "...",
          "description": "...",
          "acceptance_criteria": ["..."],
          "priority": "low" | "medium" | "high" | "critical",
          "estimate": {"points": 3, "human_hours": 6.0, "ai_hours": 1.5, "confidence": "medium"},
          "builder": "dev" | "ai" | "pair",
          "rationale": "why this builder",
          "selected": true
        }
      ],
      "questions": ["Open questions to resolve before building"],
      "totals": {"points": 3, "human_hours": 6.0, "ai_hours": 1.5},
      "engine": "anthropic:claude-..." | "heuristic"
    }
"""

import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_agent import AIAgent, AIAgentScope, AIProvider
from app.models.idea import Idea
from app.services.ai_providers import ChatMessage, get_provider
from app.settings import settings

logger = logging.getLogger(__name__)

ITEM_TYPES = {"feature", "issue", "task"}
PRIORITIES = {"low", "medium", "high", "critical"}
BUILDERS = {"dev", "ai", "pair"}
CONFIDENCE = {"low", "medium", "high"}
FIBONACCI = [1, 2, 3, 5, 8, 13, 21]

SYSTEM_PROMPT = """You are a senior product manager and tech lead for Buildly Labs.
A user jotted down a quick note on their phone (possibly with screenshots). Turn it
into a small, buildable backlog: features (new capability), issues (something broken),
and tasks (chores). Prefer few, well-scoped items over many tiny ones (1-6 items).

For each item estimate effort two ways:
- human_hours: a mid-level developer working alone
- ai_hours: wall-clock hours for an AI coding agent (e.g. Claude Code) with light human review
Use Fibonacci story points (1,2,3,5,8,13). Recommend a builder:
- "ai" for well-specified, low-ambiguity code changes
- "dev" for work needing judgment, credentials, design taste, or physical devices
- "pair" for meaningful work where AI drafts and a developer reviews/finishes

Respond with ONLY a JSON object, no prose, matching:
{"title": str, "summary": str,
 "items": [{"type": "feature|issue|task", "title": str, "description": str,
            "acceptance_criteria": [str], "priority": "low|medium|high|critical",
            "estimate": {"points": int, "human_hours": number, "ai_hours": number,
                         "confidence": "low|medium|high"},
            "builder": "dev|ai|pair", "rationale": str}],
 "questions": [str]}"""


def build_user_prompt(idea: Idea, product_name: str | None, product_description: str | None) -> str:
    """Compose the user message describing the capture."""
    parts = [f"Capture type: {idea.kind}"]
    if product_name:
        parts.append(f"Product: {product_name}")
        if product_description:
            parts.append(f"Product description: {product_description[:1000]}")
    if idea.title:
        parts.append(f"Title: {idea.title}")
    parts.append(f"Note:\n{idea.body or '(no text)'}")
    if idea.context:
        ctx = ", ".join(f"{k}={v}" for k, v in idea.context.items() if v)
        if ctx:
            parts.append(f"Device/app context: {ctx}")
    if idea.attachments:
        names = [a.get("filename") or "image" for a in idea.attachments]
        parts.append(
            f"Attached {len(names)} photo(s)/screenshot(s): {', '.join(names)}. "
            "Reference them in descriptions where relevant."
        )
    return "\n\n".join(parts)


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (tolerates code fences)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object in AI response")
        text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("AI response JSON is not an object")
    return data


def _num(value: Any, default: float) -> float:
    try:
        n = float(value)
        return n if n >= 0 else default
    except (TypeError, ValueError):
        return default


def _nearest_points(value: Any) -> int:
    n = _num(value, 3)
    return min(FIBONACCI, key=lambda f: abs(f - n))


def normalize_breakdown(data: dict, idea: Idea, engine: str) -> dict:
    """Validate and clamp AI output into the canonical breakdown shape."""
    default_type = "issue" if idea.kind == "bug" else "feature"
    items = []
    for i, raw in enumerate(data.get("items") or []):
        if not isinstance(raw, dict) or not str(raw.get("title") or "").strip():
            continue
        est = raw.get("estimate") if isinstance(raw.get("estimate"), dict) else {}
        human = round(_num(est.get("human_hours"), 4.0), 1)
        ai = round(_num(est.get("ai_hours"), human / 3), 1)
        ac = raw.get("acceptance_criteria") or []
        if isinstance(ac, str):
            ac = [ac]
        items.append({
            "id": f"item-{i + 1}",
            "type": raw.get("type") if raw.get("type") in ITEM_TYPES else default_type,
            "title": str(raw["title"]).strip()[:200],
            "description": str(raw.get("description") or "").strip(),
            "acceptance_criteria": [str(a).strip() for a in ac if str(a).strip()][:10],
            "priority": raw.get("priority") if raw.get("priority") in PRIORITIES else "medium",
            "estimate": {
                "points": _nearest_points(est.get("points")),
                "human_hours": human,
                "ai_hours": ai,
                "confidence": est.get("confidence") if est.get("confidence") in CONFIDENCE else "medium",
            },
            "builder": raw.get("builder") if raw.get("builder") in BUILDERS else "pair",
            "rationale": str(raw.get("rationale") or "").strip(),
            "selected": True,
        })
    if not items:
        raise ValueError("AI response contained no usable items")

    questions = [str(q).strip() for q in (data.get("questions") or []) if str(q).strip()][:8]
    return {
        "title": str(data.get("title") or idea.title or items[0]["title"]).strip()[:200],
        "summary": str(data.get("summary") or "").strip(),
        "items": items,
        "questions": questions,
        "totals": compute_totals(items),
        "engine": engine,
    }


def compute_totals(items: list[dict]) -> dict:
    chosen = [i for i in items if i.get("selected", True)]
    return {
        "points": sum(i["estimate"]["points"] for i in chosen),
        "human_hours": round(sum(i["estimate"]["human_hours"] for i in chosen), 1),
        "ai_hours": round(sum(i["estimate"]["ai_hours"] for i in chosen), 1),
    }


def heuristic_breakdown(idea: Idea) -> dict:
    """Non-AI fallback so the capture → Labs flow works without an AI key."""
    body = (idea.body or "").strip()
    first_line = body.splitlines()[0] if body else ""
    title = (idea.title or first_line or "Untitled capture").strip()[:120]
    words = len(body.split())
    points = 2 if words < 30 else 3 if words < 80 else 5
    human = {2: 4.0, 3: 8.0, 5: 16.0}[points]
    is_bug = idea.kind == "bug"
    item = {
        "type": "issue" if is_bug else "feature",
        "title": title,
        "description": body,
        "acceptance_criteria": (
            ["The reported problem no longer reproduces", "A regression test covers it"]
            if is_bug
            else ["Behaviour described in the note is implemented", "Covered by tests"]
        ),
        "priority": "high" if is_bug else "medium",
        "estimate": {"points": points, "human_hours": human, "ai_hours": round(human / 3, 1), "confidence": "low"},
        "builder": "pair",
        "rationale": "Rough estimate from note length — configure an AI provider for a real breakdown.",
    }
    return normalize_breakdown(
        {"title": title, "summary": body[:500], "items": [item], "questions": []}, idea, "heuristic"
    )


async def _resolve_provider(db: AsyncSession, workspace_id: int):
    """Pick the AI provider: platform setting, else the workspace's first active agent."""
    if settings.idea_ai_provider and settings.idea_ai_api_key:
        provider = AIProvider(settings.idea_ai_provider)
        return get_provider(provider, settings.idea_ai_api_key, settings.idea_ai_model,
                            temperature=0.2, max_tokens=4096, timeout=90.0), \
            f"{provider.value}:{settings.idea_ai_model}"

    result = await db.execute(
        select(AIAgent)
        .where(
            AIAgent.workspace_id == workspace_id,
            AIAgent.scope == AIAgentScope.WORKSPACE,
            AIAgent.is_active.is_(True),
            AIAgent.provider.in_([AIProvider.ANTHROPIC.value, AIProvider.OPENAI.value]),
        )
        .order_by(AIAgent.id)
        .limit(1)
    )
    agent = result.scalar_one_or_none()
    if agent:
        provider = AIProvider(agent.provider)
        return get_provider(provider, agent.api_key, agent.model,
                            temperature=0.2, max_tokens=4096, timeout=90.0), \
            f"{provider.value}:{agent.model}"
    return None, "heuristic"


async def refine_idea(db: AsyncSession, idea: Idea) -> dict:
    """Produce a breakdown for an idea. Falls back to a heuristic if no AI is configured."""
    provider, engine = await _resolve_provider(db, idea.workspace_id)
    if provider is None:
        return heuristic_breakdown(idea)

    product = idea.product
    prompt = build_user_prompt(
        idea,
        product.name if product else None,
        product.description if product else None,
    )
    response = await provider.chat([
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt),
    ])
    try:
        return normalize_breakdown(_extract_json(response.content), idea, engine)
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Idea %s: unusable AI response (%s); using heuristic", idea.id, e)
        fallback = heuristic_breakdown(idea)
        fallback["engine"] = f"heuristic (AI response unusable: {engine})"
        return fallback


def render_item_markdown(item: dict, idea: Idea, breakdown: dict) -> str:
    """Body text for an Artifact / Labs backlog item created from a breakdown item."""
    est = item["estimate"]
    builder_label = {"dev": "Developer", "ai": "AI agent", "pair": "AI + developer"}[item["builder"]]
    lines = [item["description"] or breakdown.get("summary") or idea.body, ""]
    if item["acceptance_criteria"]:
        lines.append("### Acceptance criteria")
        lines += [f"- [ ] {c}" for c in item["acceptance_criteria"]]
        lines.append("")
    lines += [
        "### Estimate",
        f"- Story points: **{est['points']}** (confidence: {est['confidence']})",
        f"- Developer: ~{est['human_hours']}h · AI agent: ~{est['ai_hours']}h",
        f"- Suggested builder: **{builder_label}**" + (f" — {item['rationale']}" if item.get("rationale") else ""),
        "",
    ]
    if breakdown.get("questions"):
        lines.append("### Open questions")
        lines += [f"- {q}" for q in breakdown["questions"]]
        lines.append("")
    if idea.attachments:
        lines.append("### Attachments")
        lines += [f"- ![{a.get('filename', 'image')}]({a['url']})" for a in idea.attachments if a.get("url")]
        lines.append("")
    if idea.context:
        lines.append("### Reported from")
        lines += [f"- {k}: {v}" for k, v in idea.context.items() if v]
        lines.append("")
    lines.append("---")
    lines.append(f"_Captured in Forge Capture ({idea.kind}). Original note:_")
    lines += [f"> {line}" for line in (idea.body or "").splitlines()] or ["> (no text)"]
    return "\n".join(lines).strip()
