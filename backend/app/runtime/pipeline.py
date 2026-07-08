"""Agent 流水线：Router → Planner → Confirm? → Executor → Summarize。"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.runtime.context import RunContext
from app.runtime.events import StepEvent
from app.runtime.plugins.note_library import NoteLibraryPlugin, build_messages
from app.runtime.task_state import TaskPhase, TaskState
from app.runtime.tool_registry import ToolRegistry
from app.services import chat_store
from app.services.agent import memory as agent_memory
from app.services.agent import planner as agent_planner
from app.services.agent import router as agent_router
from app.services.agent.router import RouteDecision
from app.services.chat_intent import tool_choice_for_round
from app.services.chat_task_state import build_move_plan_from_history

_MAX_TOOL_ROUNDS = 5
_DELTA_CHUNK_SIZE = 48


class Pipeline:
    def __init__(self, plugins: list | None = None) -> None:
        self.plugins = tuple(plugins or [NoteLibraryPlugin()])
        self.registry = ToolRegistry()
        for plugin in self.plugins:
            plugin.register_tools(self.registry)

    def _domain_plugin(self) -> NoteLibraryPlugin:
        for p in self.plugins:
            if isinstance(p, NoteLibraryPlugin):
                return p
        return NoteLibraryPlugin()

    async def run(self, ctx: RunContext) -> AsyncIterator[StepEvent]:
        ctx.registry = self.registry
        ctx.plugins = self.plugins
        fsm = TaskState.from_memory(ctx.mem)

        if not ctx.user_message:
            yield StepEvent.error("消息不能为空")
            return

        try:
            yield StepEvent.phase("routing")
            pending = ctx.pending_plan
            route = await agent_router.route(
                ctx.client,
                ctx.model,
                ctx.user_message,
                ctx.history,
                pending_plan=pending,
                awaiting_confirmation=ctx.awaiting_confirmation,
                reference_record_ids=ctx.ref_ids,
                reference_folder_ids=ctx.folder_ids,
            )

            if route.kind == "confirm":
                yield StepEvent.phase("executing")
                fsm.transition(TaskPhase.EXECUTING)
                plan = agent_planner.plan_for_confirm(
                    pending,
                    ctx.history,
                    ctx.user_message,
                    ref_ids=ctx.ref_ids,
                    folder_ids=ctx.folder_ids,
                )
                if plan and plan.get("steps"):
                    async for ev in self._execute_plan(ctx, plan, fsm):
                        yield ev
                    return
                fallback_goal = agent_planner.infer_mutate_goal(ctx.user_message) or "classify_by_city"
                route = RouteDecision(kind="mutate", mutate_goal=fallback_goal, auto_execute=True)

            if route.kind == "cancel":
                agent_memory.clear_pending(ctx.thread_id)
                fsm.transition(TaskPhase.IDLE)
                reply = "已取消待确认方案。"
                chat_store.append_turn(ctx.thread_id, ctx.user_message, reply, None)
                yield StepEvent.delta(reply)
                yield StepEvent.done()
                return

            if route.is_mutate:
                yield StepEvent.phase("planning")
                fsm.transition(TaskPhase.PLANNING)
                plan = await agent_planner.plan_mutate(
                    ctx.client,
                    ctx.model,
                    ctx.user_message,
                    ctx.history,
                    mutate_goal=route.mutate_goal,
                    auto_execute=route.auto_execute,
                    ref_ids=ctx.ref_ids,
                    folder_ids=ctx.folder_ids,
                )
                if route.auto_execute and not plan.get("steps"):
                    hist_plan = build_move_plan_from_history(ctx.history, ctx.user_message)
                    if hist_plan and hist_plan.get("steps"):
                        plan = {**hist_plan, "requires_confirmation": False}
                if plan.get("requires_confirmation") and not plan.get("steps"):
                    hist_plan = build_move_plan_from_history(ctx.history, ctx.user_message)
                    if hist_plan and hist_plan.get("steps"):
                        plan = {**hist_plan, "requires_confirmation": True}
                if plan.get("requires_confirmation") and plan.get("steps"):
                    async for ev in self._present_plan(ctx, plan, fsm):
                        yield ev
                    return
                if plan.get("steps"):
                    yield StepEvent.phase("executing")
                    fsm.transition(TaskPhase.EXECUTING)
                    async for ev in self._execute_plan(ctx, plan, fsm):
                        yield ev
                    return
                async for ev in self._present_plan(ctx, plan, fsm):
                    yield ev
                return

            if route.kind == "query":
                yield StepEvent.phase("executing")
                fsm.transition(TaskPhase.EXECUTING)
                async for ev in self._query_tools(ctx, fsm):
                    yield ev
                return

            yield StepEvent.phase("executing")
            fsm.transition(TaskPhase.EXECUTING)
            async for ev in self._read(ctx, fsm):
                yield ev

        except Exception as err:  # noqa: BLE001
            yield StepEvent.error(str(err))

    async def _execute_plan(
        self,
        ctx: RunContext,
        plan: dict[str, Any],
        fsm: TaskState,
    ) -> AsyncIterator[StepEvent]:
        tool_steps: list[dict[str, Any]] = []
        moved_total = 0
        created: list[str] = []
        failed_moves: list[str] = []
        for step in plan.get("steps") or []:
            tool = str(step.get("tool") or "").strip()
            if not tool:
                continue
            args = step.get("args") if isinstance(step.get("args"), dict) else {}
            yield self._tool_start_event(tool)
            result = ctx.registry.execute(tool, args)
            ok = _tool_ok(result)
            preview = _tool_preview(result)
            moved_total, created, failed_moves = _accumulate_plan_summary(
                tool, result, args, moved_total, created, failed_moves
            )
            tool_steps.append(self._tool_step_dict(tool, ok=ok, preview=preview))
            yield StepEvent.tool_end(tool, ok, preview)
        summary = {
            "records_moved": moved_total,
            "folders_created": created,
            "failed_moves": failed_moves,
            "goal": plan.get("goal"),
        }

        messages = build_messages(ctx)
        messages.append(
            {"role": "user", "content": agent_planner.execution_hint(plan, summary)},
        )
        full = ""
        stream = await ctx.client.chat.completions.create(
            model=ctx.model, messages=messages, stream=True
        )
        async for event in stream:
            choice = event.choices[0] if event.choices else None
            if not choice:
                continue
            piece = choice.delta.content or ""
            if piece:
                full += piece
                yield StepEvent.delta(piece)
        if not full.strip():
            moved = summary.get("records_moved", 0)
            full = f"已执行方案，成功移动 {moved} 条笔记。"
            yield StepEvent.delta(full)
        chat_store.append_turn(ctx.thread_id, ctx.user_message, full, tool_steps or None)
        agent_memory.clear_pending(ctx.thread_id)
        fsm.transition(TaskPhase.DONE)
        fsm.transition(TaskPhase.IDLE)
        yield StepEvent.done()

    async def _present_plan(
        self,
        ctx: RunContext,
        plan: dict[str, Any],
        fsm: TaskState,
    ) -> AsyncIterator[StepEvent]:
        messages = build_messages(ctx)
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{agent_planner.presentation_hint(plan)}\n\n"
                    f"方案 JSON：\n```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```"
                ),
            }
        )
        full = ""
        stream = await ctx.client.chat.completions.create(
            model=ctx.model, messages=messages, stream=True
        )
        async for event in stream:
            choice = event.choices[0] if event.choices else None
            if not choice:
                continue
            piece = choice.delta.content or ""
            if piece:
                full += piece
                yield StepEvent.delta(piece)
        if not full.strip():
            full = "已生成变更方案；确认后可执行。"
            yield StepEvent.delta(full)
        agent_memory.save_pending(ctx.thread_id, plan)
        chat_store.append_turn(ctx.thread_id, ctx.user_message, full, None)
        fsm.transition(TaskPhase.AWAITING_CONFIRMATION)
        yield StepEvent.done()

    async def _query_tools(self, ctx: RunContext, fsm: TaskState) -> AsyncIterator[StepEvent]:
        plugin = self._domain_plugin()
        messages = build_messages(ctx, query_mode=True)
        tools = ctx.registry.get_openai_tools(intent="query")
        full = ""
        tool_steps: list[dict[str, Any]] = []

        for round_idx in range(_MAX_TOOL_ROUNDS):
            response = await ctx.client.chat.completions.create(
                model=ctx.model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice_for_round("query", round_idx),
                stream=False,
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                if msg.content:
                    full = msg.content
                break

            messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                fn = tc.function
                tool_name = fn.name or ""
                try:
                    args = json.loads(fn.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                args = plugin.repair_tool_args(tool_name, args, messages, ctx)
                yield self._tool_start_event(tool_name)
                result = ctx.registry.execute(tool_name, args)
                ok = _tool_ok(result)
                preview = _tool_preview(result)
                tool_steps.append(self._tool_step_dict(tool_name, ok=ok, preview=preview))
                yield StepEvent.tool_end(tool_name, ok, preview)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        if not full.strip():
            stream = await ctx.client.chat.completions.create(
                model=ctx.model, messages=messages, tools=tools, tool_choice="none", stream=True
            )
            async for event in stream:
                choice = event.choices[0] if event.choices else None
                if not choice:
                    continue
                piece = choice.delta.content or ""
                if piece:
                    full += piece
                    yield StepEvent.delta(piece)
        else:
            for i in range(0, len(full), _DELTA_CHUNK_SIZE):
                yield StepEvent.delta(full[i : i + _DELTA_CHUNK_SIZE])

        if not full.strip():
            full = "（模型未返回内容。）"
            yield StepEvent.delta(full)
        chat_store.append_turn(ctx.thread_id, ctx.user_message, full, tool_steps or None)
        fsm.transition(TaskPhase.DONE)
        fsm.transition(TaskPhase.IDLE)
        yield StepEvent.done()

    async def _read(self, ctx: RunContext, fsm: TaskState) -> AsyncIterator[StepEvent]:
        messages = build_messages(ctx)
        full = ""
        stream = await ctx.client.chat.completions.create(
            model=ctx.model, messages=messages, stream=True
        )
        async for event in stream:
            choice = event.choices[0] if event.choices else None
            if not choice:
                continue
            piece = choice.delta.content or ""
            if piece:
                full += piece
                yield StepEvent.delta(piece)
        if not full.strip():
            full = "（模型未返回内容。）"
            yield StepEvent.delta(full)
        chat_store.append_turn(ctx.thread_id, ctx.user_message, full, None)
        fsm.transition(TaskPhase.DONE)
        fsm.transition(TaskPhase.IDLE)
        yield StepEvent.done()

    def _tool_start_event(self, name: str) -> StepEvent:
        reg = self.registry
        return StepEvent.tool_start(
            name,
            reg.tool_label(name),
            reg.tool_category(name),
            _category_label(reg.tool_category(name)),
        )

    def _tool_step_dict(self, name: str, *, ok: bool, preview: str) -> dict[str, Any]:
        reg = self.registry
        cat = reg.tool_category(name)
        return {
            "name": name,
            "label": reg.tool_label(name),
            "category_label": _category_label(cat),
            "ok": ok,
            "preview": preview,
            "status": "done",
        }


def _accumulate_plan_summary(
    tool: str,
    result: str,
    args: dict[str, Any],
    moved_total: int,
    created: list[str],
    failed_moves: list[str],
) -> tuple[int, list[str], list[str]]:
    """ponytail: 与 chat_task_state.execute_plan 摘要逻辑对齐。"""
    try:
        parsed = json.loads(result)
        if not isinstance(parsed, dict):
            return moved_total, created, failed_moves
        if parsed.get("ok") is False or parsed.get("error"):
            return moved_total, created, failed_moves
        if tool == "create_folder":
            name = (parsed.get("folder") or {}).get("name") or args.get("name", "")
            if name:
                created.append(str(name))
        elif tool == "move_records":
            moved = parsed.get("moved") or []
            failed = parsed.get("failed") or []
            moved_total += len(moved)
            failed_moves.extend(failed)
    except json.JSONDecodeError:
        pass
    return moved_total, created, failed_moves


def _category_label(cat: str) -> str:
    from app.runtime.tool_registry import TOOL_CATEGORIES

    return TOOL_CATEGORIES.get(cat, {}).get("label", "")


def _tool_preview(result: str) -> str:
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            if parsed.get("error"):
                return str(parsed["error"])[:120]
            if parsed.get("title"):
                return str(parsed["title"])[:120]
            if parsed.get("count") is not None:
                return f"count={parsed['count']}"
            moved = parsed.get("moved")
            if isinstance(moved, list) and moved:
                bc = parsed.get("batch_count")
                if bc:
                    return f"moved={len(moved)}, batches={bc}"
                return f"moved={len(moved)}"
    except json.JSONDecodeError:
        pass
    return (result or "")[:120]


def _tool_ok(result: str) -> bool:
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            if parsed.get("ok") is False:
                return False
            if parsed.get("error"):
                return False
    except json.JSONDecodeError:
        pass
    return True


default_pipeline = Pipeline()


def _self_check() -> None:
    p = Pipeline()
    assert len(p.registry.get_openai_tools()) == 8
    assert p._tool_step_dict("list_records", ok=True, preview="count=1")["name"] == "list_records"
    fsm = TaskState()
    fsm.transition(TaskPhase.EXECUTING)
    fsm.transition(TaskPhase.DONE)
    fsm.transition(TaskPhase.IDLE)
    assert fsm.phase == TaskPhase.IDLE
    moved, created, failed = _accumulate_plan_summary(
        "move_records",
        '{"ok":true,"moved":["a","b"],"failed":[]}',
        {},
        0,
        [],
        [],
    )
    assert moved == 2 and created == [] and failed == []


if __name__ == "__main__":
    _self_check()
    print("runtime.pipeline ok")
