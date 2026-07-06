"""分类变更预分析：扫描引用笔记，生成可执行的 move/create 建议（注入 mutate 上下文）。"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from app.services.folder_store import (
    UNCATEGORIZED_FOLDER_ID,
    create_folder,
    is_uncategorized_folder_id,
    list_user_folders,
)
from app.services.subtitle_store import get_record, list_record_ids_in_folder, move_records_to_folder

# ponytail: 韩国旅行常见城市/地区 → 建议文件夹名（可按需扩展）
_CITY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("首尔", ("首尔",)),
    ("济州岛", ("济州岛", "济州")),
    ("釜山", ("釜山",)),
    ("仁川", ("仁川",)),
    ("大邱", ("大邱",)),
    ("光州", ("光州",)),
    ("蔚山", ("蔚山",)),
    ("江原道", ("江原道", "束草", "春川", "江陵", "襄阳", "三陟", "原州")),
    ("全州", ("全州",)),
    ("木浦", ("木浦",)),
    ("丽水", ("丽水",)),
    ("浦项", ("浦项",)),
    ("庆州", ("庆州",)),
    ("群山", ("群山", "古群山")),
]

_COLLECTION_HINTS = (
    "十城",
    "十个地方",
    "十个",
    "多个地方",
    "合集",
    "多城",
    "三城",
    "四城",
    "五城",
    "待定",
    "周边城市",
    "周边",
    "一样精彩",
)
_MULTI_CITY_SEP = re.compile(r"[、，,/＋+与和及]")


def _title_of(rec: dict[str, Any]) -> str:
    return str(rec.get("title") or rec.get("note_id") or rec.get("bvid") or rec.get("id") or "")


def cities_in_title(title: str) -> list[str]:
    found: list[str] = []
    for folder_name, keywords in _CITY_RULES:
        if any(kw in title for kw in keywords):
            if folder_name not in found:
                found.append(folder_name)
    return found


def _is_collection_note(title: str, cities: list[str]) -> bool:
    if any(h in title for h in _COLLECTION_HINTS):
        return True
    if len(cities) >= 2:
        return True
    # 「A、B、C」式标题且命中 ≥2 城市
    if len(cities) >= 2 and _MULTI_CITY_SEP.search(title):
        return True
    return False


def analyze_record(record_id: str) -> dict[str, Any] | None:
    rec = get_record(record_id)
    if not rec:
        return None
    title = _title_of(rec)
    cities = cities_in_title(title)
    base = {"record_id": record_id, "title": title, "cities": cities}
    if _is_collection_note(title, cities):
        return {**base, "action": "skip_collection", "reason": "多城/合集/待定，勿单城移动"}
    if len(cities) == 1:
        return {**base, "action": "move", "suggested_folder_name": cities[0]}
    return {**base, "action": "skip_unknown", "reason": "标题未识别出单一城市"}


def _folder_name_index() -> dict[str, str]:
    """文件夹名（小写）→ id。"""
    out: dict[str, str] = {}
    for f in list_user_folders():
        name = (f.get("name") or "").strip()
        fid = f.get("id")
        if name and fid:
            out[name.lower()] = fid
    return out


def collect_record_ids(
    reference_record_ids: list[str],
    reference_folder_ids: list[str],
) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for rid in reference_record_ids:
        if rid and rid not in seen:
            seen.add(rid)
            ordered.append(rid)
    for fid in reference_folder_ids:
        if not fid:
            continue
        for rid in list_record_ids_in_folder(fid):
            if rid not in seen:
                seen.add(rid)
                ordered.append(rid)
    return ordered


def build_classify_plan(
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
) -> dict[str, Any]:
    record_ids = collect_record_ids(
        [x for x in (reference_record_ids or []) if x],
        [x for x in (reference_folder_ids or []) if x],
    )
    name_to_id = _folder_name_index()
    movable: list[dict[str, Any]] = []
    skip_collection: list[dict[str, Any]] = []
    skip_unknown: list[dict[str, Any]] = []
    folders_to_create: set[str] = set()

    for rid in record_ids:
        row = analyze_record(rid)
        if not row:
            continue
        action = row.get("action")
        if action == "move":
            fname = row["suggested_folder_name"]
            existing_id = name_to_id.get(fname.lower())
            entry = {
                "record_id": row["record_id"],
                "title": row["title"],
                "suggested_folder_name": fname,
                "existing_folder_id": existing_id,
            }
            movable.append(entry)
            if not existing_id:
                folders_to_create.add(fname)
        elif action == "skip_collection":
            skip_collection.append(
                {"record_id": row["record_id"], "title": row["title"], "cities": row.get("cities") or []}
            )
        else:
            skip_unknown.append({"record_id": row["record_id"], "title": row["title"]})

    return {
        "total_scanned": len(record_ids),
        "movable": movable,
        "skip_collection": skip_collection,
        "skip_unknown": skip_unknown,
        "folders_to_create": sorted(folders_to_create),
        "existing_folders": [{"name": n, "id": i} for n, i in sorted(name_to_id.items())],
    }


def build_classify_plan_block(
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
) -> str:
    """mutate 时注入 system，指导模型按清单调工具。"""
    plan = build_classify_plan(reference_record_ids, reference_folder_ids)
    if plan["total_scanned"] == 0:
        return ""

    lines = [
        "## 自动分类预分析（编排上下文，请按此调用工具）",
        f"- 扫描笔记：{plan['total_scanned']} 条",
        f"- 可单城移动：{len(plan['movable'])} 条",
        f"- 合集/多城跳过：{len(plan['skip_collection'])} 条",
        f"- 未识别城市跳过：{len(plan['skip_unknown'])} 条",
    ]
    if plan["folders_to_create"]:
        lines.append(f"- 需新建文件夹：{', '.join(plan['folders_to_create'])}")
    if plan["existing_folders"]:
        names = ", ".join(f"{x['name']}(#{x['id']})" for x in plan["existing_folders"][:12])
        lines.append(f"- 已有用户文件夹：{names}")

    lines.append("")
    lines.append("执行顺序：1) list_folders 核对 2) create_folder 补缺失 3) move_records 逐批移动。")
    lines.append("禁止调用 list_records / get_record；record_id 与目标文件夹已在下方清单，无需读正文。")
    lines.append("合集/多城笔记不要 move；可保留未分类或询问用户是否建「合集」文件夹。")
    lines.append("")
    lines.append("可移动清单（JSON）：")
    lines.append("```json")
    lines.append(json.dumps(plan["movable"], ensure_ascii=False, indent=2))
    lines.append("```")
    if plan["skip_collection"]:
        lines.append("")
        lines.append("跳过（合集/多城）：")
        for x in plan["skip_collection"]:
            cities = "、".join(x.get("cities") or []) or "—"
            lines.append(f"- {x['title']} (#{x['record_id']}) [{cities}]")
    return "\n".join(lines)


def apply_classify_plan(
    reference_record_ids: list[str] | None = None,
    reference_folder_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    服务端执行分类变更，返回 (tool_steps, plan)。
    每步：{name, ok, preview, result}
    """
    plan = build_classify_plan(reference_record_ids, reference_folder_ids)
    steps: list[dict[str, Any]] = []
    name_to_id = _folder_name_index()

    folders = list_user_folders()
    list_result = json.dumps(
        {"ok": True, "count": len(folders), "folders": folders},
        ensure_ascii=False,
    )
    steps.append(
        {
            "name": "list_folders",
            "ok": True,
            "preview": f"count={len(folders)}",
            "result": list_result,
        }
    )

    for fname in plan["folders_to_create"]:
        if fname.lower() in name_to_id:
            continue
        try:
            folder = create_folder(fname)
            name_to_id[fname.lower()] = folder["id"]
            result = json.dumps({"ok": True, "folder": folder}, ensure_ascii=False)
            steps.append(
                {
                    "name": "create_folder",
                    "ok": True,
                    "preview": fname,
                    "result": result,
                }
            )
        except ValueError as err:
            result = json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False)
            steps.append(
                {
                    "name": "create_folder",
                    "ok": False,
                    "preview": str(err)[:120],
                    "result": result,
                }
            )

    groups: dict[str, list[str]] = defaultdict(list)
    for item in plan["movable"]:
        fname = item["suggested_folder_name"]
        fid = item.get("existing_folder_id") or name_to_id.get(fname.lower())
        if fid:
            groups[fid].append(item["record_id"])

    for fid, ids in groups.items():
        outcome = move_records_to_folder(ids, fid)
        moved = len(outcome.get("moved") or [])
        failed = len(outcome.get("failed") or [])
        ok = failed == 0 and moved > 0
        preview = f"moved={moved}" + (f", failed={failed}" if failed else "")
        result = json.dumps({"ok": ok, **outcome}, ensure_ascii=False)
        steps.append(
            {
                "name": "move_records",
                "ok": ok,
                "preview": preview,
                "result": result,
            }
        )

    return steps, plan


def execution_summary(steps: list[dict[str, Any]], plan: dict[str, Any]) -> str:
    created = [s.get("preview") for s in steps if s.get("name") == "create_folder" and s.get("ok")]
    moved = sum(
        len(json.loads(s["result"]).get("moved") or [])
        for s in steps
        if s.get("name") == "move_records" and s.get("ok")
    )
    return json.dumps(
        {
            "folders_created": created,
            "records_moved": moved,
            "skipped_collection": len(plan.get("skip_collection") or []),
            "skipped_unknown": len(plan.get("skip_unknown") or []),
        },
        ensure_ascii=False,
    )


def _self_check() -> None:
    assert cities_in_title("韩国釜山旅行攻略") == ["釜山"]
    assert cities_in_title("首尔仁川一日游")[0] in ("首尔", "仁川")
    multi = analyze_record  # noqa: F841
    title = "韩国十城合集"
    assert _is_collection_note(title, cities_in_title(title))
    plan = build_classify_plan([], [UNCATEGORIZED_FOLDER_ID])
    assert "total_scanned" in plan
    assert is_uncategorized_folder_id(UNCATEGORIZED_FOLDER_ID)


if __name__ == "__main__":
    _self_check()
    steps, plan = apply_classify_plan([], [UNCATEGORIZED_FOLDER_ID])
    print("chat_classify_plan ok", execution_summary(steps, plan), len(steps))
