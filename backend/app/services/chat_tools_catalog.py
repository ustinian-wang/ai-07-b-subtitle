"""对话助手工具目录（按操作分类）。"""
from __future__ import annotations

from typing import Any

from app.services import chat_tools


def _summarize_parameters(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"properties": [], "required": []}
    props_in = schema.get("properties")
    if not isinstance(props_in, dict):
        props_in = {}
    required = schema.get("required")
    req_set = set(required) if isinstance(required, list) else set()
    properties: list[dict[str, Any]] = []
    for key, spec in props_in.items():
        if not isinstance(spec, dict):
            continue
        properties.append(
            {
                "name": key,
                "type": spec.get("type") or "any",
                "description": str(spec.get("description") or "")[:300],
                "required": key in req_set,
                "enum": spec.get("enum"),
            }
        )
    return {"properties": properties, "required": list(req_set)}


def get_tools_catalog() -> dict[str, Any]:
    """按 category 分组返回工具列表。"""
    by_cat: dict[str, list[dict[str, Any]]] = {k: [] for k in chat_tools.TOOL_CATEGORIES}
    flat: list[dict[str, Any]] = []

    for entry in chat_tools.get_openai_tools():
        fn = entry.get("function") if isinstance(entry, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "")
        category = chat_tools.tool_category(name)
        item = {
            "name": name,
            "label": chat_tools.tool_label(name),
            "category": category,
            "category_label": chat_tools.TOOL_CATEGORIES.get(category, {}).get("label", category),
            "description": str(fn.get("description") or ""),
            "parameters": _summarize_parameters(fn.get("parameters")),
        }
        flat.append(item)
        by_cat.setdefault(category, []).append(item)

    categories = []
    for cat_id, meta in sorted(
        chat_tools.TOOL_CATEGORIES.items(),
        key=lambda x: x[1].get("order", 99),
    ):
        tools = by_cat.get(cat_id) or []
        categories.append(
            {
                "id": cat_id,
                "label": meta.get("label") or cat_id,
                "order": meta.get("order", 99),
                "tools": tools,
                "count": len(tools),
            }
        )

    return {
        "categories": categories,
        "tools": flat,
        "total_count": len(flat),
    }
