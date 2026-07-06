"""对话轮次意图：read / query / write，驱动 tool_choice 编排（非 system prompt 堆砌）。"""
from __future__ import annotations

import re

# 只读：分析、总结、对比
_READ_ONLY = re.compile(
    r"(分析|总结|概括|对比|解释|什么意思|是什么|怎么样|评价|优缺点|推荐吗|值得吗|帮我看|看看这)",
    re.I,
)

# 库查询：列目录、搜笔记，不改数据
_QUERY = re.compile(
    r"(有哪些|有什么|列出|列一下|查看|查询|搜索|找一下|显示|目录|文件夹列表|分类列表|"
    r"list\s*folder|show\s*folder|树形|结构)",
    re.I,
)

# 写库：分类、移动、新建、删除、导入
_WRITE = re.compile(
    r"(自动分类|按城市|按地区|重新分类|重新分配|调整.*分类|对笔记.*分类|归类到|归类|"
    r"移动到|移到|创建文件夹|新建文件夹|新建分类|"
    r"删除|移除|导入|抓取|下载|整理笔记|帮我分|帮我移|执行分类|开始分|开始整理|落库|"
    r"create_folder|move_record|delete_record|fetch)",
    re.I,
)

_CONFIRM = re.compile(r"^(好|好的|可以|行|确认|开始|执行|按这个|就这样|ok|yes|go)\.?$", re.I)
_CLASSIFY_CONTINUE = re.compile(r"^(继续|搞下|执行吧|按此执行|按此|落库)\.?$", re.I)

_CLASSIFY_SCOPE = re.compile(
    r"(自动分类|按城市|按地区|归类|整理|帮我分|开始分|重新分类|重新分配|分类|落库)",
    re.I,
)

_ASSISTANT_CLASSIFY = re.compile(
    r"(分类|文件夹|移动|create_folder|move_records|落库|归类|未分类)",
    re.I,
)


def _last_assistant_text(history: list[dict[str, str]]) -> str:
    for m in reversed(history):
        if m.get("role") == "assistant":
            return m.get("content") or ""
    return ""


def classify_turn(
    user_message: str,
    history: list[dict[str, str]],
    *,
    reference_folder_ids: list[str] | None = None,
    reference_record_ids: list[str] | None = None,
) -> str:
    """
    返回 read | query | write。
    - query：列文件夹/搜笔记，首轮强制 list_folders
    - write：改库；引用分类/分类关键词 → 预分析 + 工具链
    """
    t = (user_message or "").strip()
    if not t:
        return "read"

    has_refs = bool(reference_folder_ids or reference_record_ids)
    last_assistant = _last_assistant_text(history)

    if (_CONFIRM.match(t) or _CLASSIFY_CONTINUE.match(t)) and history:
        if _WRITE.search(last_assistant) or _ASSISTANT_CLASSIFY.search(last_assistant):
            return "write"

    if history and _ASSISTANT_CLASSIFY.search(last_assistant):
        if re.search(r"(搞下|按此|落库|执行)", t, re.I):
            return "write"

    if _QUERY.search(t) and not _WRITE.search(t):
        return "query"

    if _WRITE.search(t):
        return "write"

    if has_refs and _CLASSIFY_SCOPE.search(t) and not _READ_ONLY.search(t):
        return "write"

    if has_refs and _READ_ONLY.search(t):
        return "read"

    return "read"


def is_classify_mutate_turn(
    user_message: str,
    history: list[dict[str, str]],
    *,
    reference_folder_ids: list[str] | None = None,
    reference_record_ids: list[str] | None = None,
) -> bool:
    """是否走服务端自动分类（不交给 LLM 调 create/move/get_record）。"""
    if classify_turn(
        user_message,
        history,
        reference_folder_ids=reference_folder_ids,
        reference_record_ids=reference_record_ids,
    ) != "write":
        return False
    from app.services.chat_classify_plan import build_classify_plan

    plan = build_classify_plan(reference_record_ids, reference_folder_ids)
    return plan["total_scanned"] > 0


def tool_choice_for_round(intent: str, round_idx: int) -> str | dict[str, object]:
    """write/query 首轮指定 list_folders；write 后续 auto（工具集已收窄）。"""
    if round_idx == 0:
        if intent in ("write", "query"):
            return {"type": "function", "function": {"name": "list_folders"}}
        return "auto"
    return "auto"


def _self_check() -> None:
    assert classify_turn("帮我总结引用笔记", []) == "read"
    assert classify_turn("有哪些分类", []) == "query"
    assert classify_turn("帮我把笔记按城市自动分类", [], reference_folder_ids=["__uncategorized__"]) == "write"
    assert classify_turn("帮我把这些笔记重新分类", [], reference_folder_ids=["__uncategorized__"]) == "write"
    assert classify_turn("根据笔记的内容，对笔记重新分类", [], reference_folder_ids=["__uncategorized__"]) == "write"
    assert (
        classify_turn(
            "继续",
            [{"role": "assistant", "content": "移动清单如下，可按文件夹批量归类"}],
            reference_folder_ids=["__uncategorized__"],
        )
        == "write"
    )
    assert (
        classify_turn(
            "行，你帮我搞下",
            [{"role": "assistant", "content": "我可以帮你新建分类文件夹并移动笔记"}],
            reference_folder_ids=["__uncategorized__"],
        )
        == "write"
    )
    assert is_classify_mutate_turn(
        "帮我把笔记按城市自动分类", [], reference_folder_ids=["__uncategorized__"]
    )
    assert tool_choice_for_round("write", 0) == {"type": "function", "function": {"name": "list_folders"}}


if __name__ == "__main__":
    _self_check()
    print("chat_intent ok")
