<template>
  <aside
    class="chat-panel"
    :class="{ 'chat-panel--drop-target': dropActive }"
    :style="{ width: `${width}px` }"
    @dragenter="onDropZoneEnter"
    @dragleave="onDropZoneLeave"
    @dragover="onDropZoneDragOver"
    @drop="onDropZoneDrop"
  >
    <header class="chat-head">
      <div class="chat-head-main">
        <h2 class="chat-title">对话助手</h2>
        <p v-if="activeSessionTitle" class="chat-active-session" :title="activeSessionTitle">
          {{ activeSessionTitle }}
        </p>
        <p v-else class="chat-sub">引用笔记，多轮对话分析</p>
      </div>
      <div class="chat-head-actions">
        <button
          type="button"
          class="btn tiny"
          :class="{ 'btn--active': sessionsOpen }"
          :disabled="busy"
          @click="sessionsOpen = !sessionsOpen"
        >
          历史{{ sessions.length ? ` (${sessions.length})` : '' }}
        </button>
        <button type="button" class="btn tiny" :disabled="busy" @click="newThread">新对话</button>
      </div>
    </header>

    <div v-if="sessionsOpen" class="chat-sessions">
      <p v-if="!sessions.length" class="chat-sessions-empty">暂无历史会话</p>
      <div
        v-for="s in sessions"
        :key="s.thread_id"
        :class="['chat-session-row', { active: s.thread_id === threadId }]"
      >
        <button type="button" class="chat-session-btn" :disabled="busy" @click="selectSession(s.thread_id)">
          <span class="chat-session-title">{{ s.title || '新对话' }}</span>
          <span class="chat-session-meta">{{ s.message_count }} 条 · {{ formatSessionTime(s.updated_at) }}</span>
        </button>
        <button
          type="button"
          class="chat-session-del"
          title="删除会话"
          :disabled="busy"
          @click="deleteSession(s.thread_id)"
        >
          ×
        </button>
      </div>
    </div>

    <div ref="scrollRef" class="chat-messages">
      <p v-if="!messages.length" class="chat-empty">
        发送消息开始对话。可 @ 引用库内笔记、从左侧拖入笔记，或使用「引用当前 / 选中」按钮。
      </p>
      <article
        v-for="(m, idx) in messages"
        :key="idx"
        :class="['chat-msg', m.role === 'user' ? 'chat-msg--user' : 'chat-msg--assistant']"
      >
        <div class="chat-role">{{ m.role === 'user' ? '你' : '助手' }}</div>
        <div class="chat-bubble">
          <template v-for="(seg, si) in parseMessageContent(m.content)" :key="`${idx}-${si}`">
            <span v-if="seg.type === 'text'" class="chat-text">{{ seg.text }}</span>
            <button
              v-else
              type="button"
              class="msg-ref"
              :title="`打开笔记：${seg.displayTitle}`"
              @click="onRefClick(seg.id)"
            >
              <span
                :class="[
                  'ref-source',
                  seg.source === 'xiaohongshu' ? 'ref-source--xhs' : 'ref-source--bili',
                ]"
              >
                {{ seg.source === 'xiaohongshu' ? '小红书' : 'B站' }}
              </span>
              <span class="ref-title">{{ seg.displayTitle }}</span>
            </button>
          </template>
        </div>
      </article>
      <article v-if="streaming" class="chat-msg chat-msg--assistant">
        <div class="chat-role">助手</div>
        <div class="chat-bubble chat-bubble--stream">
          <template v-if="streamBuffer">
            <template v-for="(seg, si) in parseMessageContent(streamBuffer)" :key="`stream-${si}`">
              <span v-if="seg.type === 'text'" class="chat-text">{{ seg.text }}</span>
              <button
                v-else
                type="button"
                class="msg-ref"
                :title="`打开笔记：${seg.displayTitle}`"
                @click="onRefClick(seg.id)"
              >
                <span
                  :class="[
                    'ref-source',
                    seg.source === 'xiaohongshu' ? 'ref-source--xhs' : 'ref-source--bili',
                  ]"
                >
                  {{ seg.source === 'xiaohongshu' ? '小红书' : 'B站' }}
                </span>
                <span class="ref-title">{{ seg.displayTitle }}</span>
              </button>
            </template>
          </template>
          <span v-else>…</span>
        </div>
      </article>
    </div>

    <div class="chat-refs">
      <div class="chat-refs-bar">
        <button
          type="button"
          class="btn tiny"
          :disabled="!currentRecordId || hasRef(currentRecordId)"
          @click="attachCurrent"
        >
          引用当前
        </button>
        <button
          type="button"
          class="btn tiny"
          :disabled="!selectedIds.length"
          @click="attachSelected"
        >
          引用选中 {{ selectedIds.length ? `(${selectedIds.length})` : '' }}
        </button>
        <span class="chat-refs-hint">@ 引用 · 拖入笔记</span>
      </div>
      <p v-if="refHint" class="chat-ref-toast">{{ refHint }}</p>
      <div v-if="refs.length" class="chat-ref-chips">
        <span v-for="r in refs" :key="r.id" class="chat-ref-chip">
          <span
            :class="['ref-source', r.source === 'xiaohongshu' ? 'ref-source--xhs' : 'ref-source--bili']"
          >
            {{ r.source === 'xiaohongshu' ? '小红书' : 'B站' }}
          </span>
          <span class="ref-title">{{ r.title || r.id }}</span>
          <button type="button" class="chip-x" title="移除引用" @click="removeRef(r.id)">×</button>
        </span>
      </div>
    </div>

    <footer class="chat-composer">
      <div class="chat-input-wrap">
        <textarea
          ref="inputRef"
          v-model="draft"
          class="chat-input"
          rows="3"
          placeholder="输入问题，@ 引用笔记，或从左侧拖入… ⌘/Ctrl+Enter 发送"
          :disabled="busy"
          @input="onInput"
          @keydown="onKeydown"
          @dragover="onComposerDragOver"
          @drop="onComposerDrop"
        />
        <ul v-if="mention.active && mentionItems.length" class="mention-popup">
          <li
            v-for="(rec, idx) in mentionItems"
            :key="rec.id"
            :class="['mention-item', { 'mention-item--active': idx === mention.index }]"
            @mousedown.prevent="selectMention(rec)"
          >
            <span
              :class="['ref-source', rec.source === 'xiaohongshu' ? 'ref-source--xhs' : 'ref-source--bili']"
            >
              {{ rec.source === 'xiaohongshu' ? '小红书' : 'B站' }}
            </span>
            <span class="mention-title">{{ mentionLabel(rec) }}</span>
            <span class="mention-meta">{{ mentionMeta(rec) }}</span>
          </li>
        </ul>
        <p v-else-if="mention.active && !mentionItems.length" class="mention-empty">无匹配笔记</p>
      </div>
      <button type="button" class="btn primary chat-send" :disabled="busy || !draft.trim()" @click="send">
        {{ busy ? '生成中…' : '发送' }}
      </button>
      <p v-if="chatError" class="chat-error">{{ chatError }}</p>
    </footer>
  </aside>
</template>

<script>
const THREAD_KEY = 'b-subtitle-chat-thread';
const DRAG_MIME = 'application/x-subtitle-ids';

const MSG_REF_RE = /@\[([^\]]*)\]\(([^)]+)\)/g;

export default {
  name: 'ChatPanel',
  emits: ['open-record'],
  props: {
    width: { type: Number, default: 400 },
    currentRecordId: { type: String, default: '' },
    currentRecordTitle: { type: String, default: '' },
    selectedIds: { type: Array, default: () => [] },
    recordMap: { type: Object, default: () => ({}) },
    allRecords: { type: Array, default: () => [] },
  },
  data() {
    return {
      threadId: '',
      sessions: [],
      sessionsOpen: false,
      messages: [],
      refs: [],
      draft: '',
      busy: false,
      streaming: false,
      streamBuffer: '',
      chatError: '',
      dropActive: false,
      dropDepth: 0,
      refHint: '',
      mention: { active: false, query: '', start: 0, index: 0 },
    };
  },
  computed: {
    activeSessionTitle() {
      const cur = this.sessions.find((s) => s.thread_id === this.threadId);
      return cur?.title || '';
    },
    mentionItems() {
      if (!this.mention.active) return [];
      const q = this.mention.query.toLowerCase();
      const list = this.allRecords.length ? this.allRecords : Object.values(this.recordMap);
      if (!q) return list.slice(0, 20);
      return list.filter((r) => this.mentionMatch(r, q)).slice(0, 20);
    },
  },
  mounted() {
    this.threadId = localStorage.getItem(THREAD_KEY) || '';
    this.loadSessions().then(() => {
      if (this.threadId) {
        this.loadMessages();
      } else if (this.sessions.length) {
        this.selectSession(this.sessions[0].thread_id, false);
      } else {
        this.ensureThread();
      }
    });
  },
  beforeUnmount() {
    clearTimeout(this._refHintTimer);
  },
  methods: {
    hasRef(id) {
      return this.refs.some((r) => r.id === id);
    },
    addRef(id, title, source) {
      if (!id || this.hasRef(id)) return false;
      const rec = this.recordMap[id];
      this.refs.push({
        id,
        title: title || rec?.title || id,
        source: source || rec?.source || 'bilibili',
      });
      return true;
    },
    attachRecordAsMention(id, { at, after, focus = false } = {}) {
      const rec = this.recordMap[id];
      if (!rec) return false;
      const title = this.mentionLabel(rec);
      const insert = `@[${title}](${id})`;
      this.addRef(id, title, rec.source);
      if (at != null) {
        const ta = this.$refs.inputRef;
        const afterPos = after ?? ta?.selectionStart ?? this.draft.length;
        const before = this.draft.slice(0, at);
        const afterText = this.draft.slice(afterPos);
        this.draft = `${before}${insert} ${afterText}`;
        if (focus && ta) {
          this.$nextTick(() => {
            const pos = before.length + insert.length + 1;
            ta.focus();
            ta.setSelectionRange(pos, pos);
          });
        }
      } else {
        const prefix = this.draft.length && !/\s$/.test(this.draft) ? ' ' : '';
        this.draft = `${this.draft}${prefix}${insert} `;
        this.closeMention();
        this.$nextTick(() => {
          const ta = this.$refs.inputRef;
          if (ta) {
            ta.focus();
            ta.setSelectionRange(this.draft.length, this.draft.length);
          }
        });
      }
      return true;
    },
    addRefsFromIds(ids) {
      let attached = 0;
      for (const id of ids) {
        if (this.attachRecordAsMention(id)) attached += 1;
      }
      if (attached) this.showRefHint(`已引用 ${attached} 条笔记`);
      else if (ids.length) this.showRefHint('所选笔记已在引用中');
    },
    showRefHint(msg) {
      this.refHint = msg;
      clearTimeout(this._refHintTimer);
      this._refHintTimer = setTimeout(() => {
        this.refHint = '';
      }, 2500);
    },
    removeRef(id) {
      this.refs = this.refs.filter((r) => r.id !== id);
    },
    attachCurrent() {
      if (!this.currentRecordId) return;
      if (this.addRef(this.currentRecordId, this.currentRecordTitle)) {
        this.showRefHint('已引用当前笔记');
      }
    },
    attachSelected() {
      const before = this.refs.length;
      for (const id of this.selectedIds) {
        const rec = this.recordMap[id];
        this.addRef(id, rec?.title, rec?.source);
      }
      const added = this.refs.length - before;
      if (added) this.showRefHint(`已引用 ${added} 条笔记`);
    },
    hasSubtitleDrag(e) {
      const types = e.dataTransfer?.types;
      if (!types) return false;
      for (let i = 0; i < types.length; i += 1) {
        if (types[i] === DRAG_MIME) return true;
      }
      return false;
    },
    onDropZoneDragOver(e) {
      if (!this.hasSubtitleDrag(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    },
    onComposerDragOver(e) {
      if (!this.hasSubtitleDrag(e)) return;
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = 'copy';
    },
    onComposerDrop(e) {
      if (!this.hasSubtitleDrag(e)) return;
      e.preventDefault();
      e.stopPropagation();
      this.onDropZoneDrop(e);
    },
    onDropZoneEnter(e) {
      if (!this.hasSubtitleDrag(e)) return;
      this.dropDepth += 1;
      this.dropActive = true;
    },
    onDropZoneLeave(e) {
      if (!this.hasSubtitleDrag(e)) return;
      this.dropDepth -= 1;
      if (this.dropDepth <= 0) {
        this.dropDepth = 0;
        this.dropActive = false;
      }
    },
    onDropZoneDrop(e) {
      e.preventDefault();
      this.dropActive = false;
      this.dropDepth = 0;
      const raw = e.dataTransfer.getData(DRAG_MIME);
      if (!raw) return;
      try {
        const parsed = JSON.parse(raw);
        const ids = Array.isArray(parsed) ? parsed : [parsed];
        this.addRefsFromIds(ids.filter(Boolean));
      } catch {
        /* ponytail: 非法拖拽数据直接忽略 */
      }
    },
    refMeta(id, fallbackTitle) {
      const rec = this.recordMap[id];
      return {
        source: rec?.source || 'bilibili',
        displayTitle: rec ? this.mentionLabel(rec) : fallbackTitle || id,
      };
    },
    parseMessageContent(text) {
      if (!text) return [{ type: 'text', text: '' }];
      const segments = [];
      let lastIndex = 0;
      MSG_REF_RE.lastIndex = 0;
      let match = MSG_REF_RE.exec(text);
      while (match) {
        if (match.index > lastIndex) {
          segments.push({ type: 'text', text: text.slice(lastIndex, match.index) });
        }
        const id = match[2];
        segments.push({
          type: 'ref',
          id,
          ...this.refMeta(id, match[1]),
        });
        lastIndex = MSG_REF_RE.lastIndex;
        match = MSG_REF_RE.exec(text);
      }
      if (lastIndex < text.length) {
        segments.push({ type: 'text', text: text.slice(lastIndex) });
      }
      return segments.length ? segments : [{ type: 'text', text }];
    },
    onRefClick(id) {
      if (!id) return;
      this.$emit('open-record', id);
    },
    mentionLabel(rec) {
      return rec.title || rec.bvid || rec.note_id || rec.id;
    },
    mentionMeta(rec) {
      if (rec.source === 'xiaohongshu') return rec.note_id || rec.id;
      return rec.bvid ? `${rec.bvid} · P${rec.page || 1}` : rec.id;
    },
    mentionMatch(rec, q) {
      const hay = [rec.title, rec.bvid, rec.note_id, rec.id].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(q);
    },
    closeMention() {
      this.mention = { active: false, query: '', start: 0, index: 0 };
    },
    onInput(e) {
      const ta = e.target;
      const pos = ta.selectionStart;
      const text = this.draft.slice(0, pos);
      const atIdx = text.lastIndexOf('@');
      if (atIdx === -1 || (atIdx > 0 && !/\s/.test(text[atIdx - 1]))) {
        this.closeMention();
        return;
      }
      const query = text.slice(atIdx + 1);
      if (/\s/.test(query)) {
        this.closeMention();
        return;
      }
      this.mention = { active: true, query, start: atIdx, index: 0 };
    },
    selectMention(record) {
      const ta = this.$refs.inputRef;
      if (!ta) return;
      const title = this.mentionLabel(record);
      this.attachRecordAsMention(record.id, {
        at: this.mention.start,
        after: ta.selectionStart,
        focus: true,
      });
      this.showRefHint(`已 @ 引用：${title}`);
      this.closeMention();
    },
    formatSessionTime(iso) {
      if (!iso) return '';
      try {
        const d = new Date(iso);
        const now = new Date();
        const diff = now - d;
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
        return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      } catch {
        return '';
      }
    },
    async loadSessions() {
      try {
        const resp = await fetch('/api/v1/chat/sessions');
        const data = await resp.json();
        if (resp.ok) {
          this.sessions = data.sessions || [];
        }
      } catch {
        this.sessions = [];
      }
    },
    async selectSession(tid, closePanel = true) {
      if (!tid || this.busy || tid === this.threadId) {
        if (closePanel) this.sessionsOpen = false;
        return;
      }
      this.threadId = tid;
      localStorage.setItem(THREAD_KEY, tid);
      this.refs = [];
      this.chatError = '';
      this.closeMention();
      await this.loadMessages();
      if (closePanel) this.sessionsOpen = false;
    },
    async deleteSession(tid) {
      if (!tid || this.busy) return;
      if (!window.confirm('删除该会话及全部聊天记录？')) return;
      try {
        await fetch(`/api/v1/chat/sessions/${encodeURIComponent(tid)}`, { method: 'DELETE' });
        await this.loadSessions();
        if (tid === this.threadId) {
          if (this.sessions.length) {
            await this.selectSession(this.sessions[0].thread_id, false);
          } else {
            await this.newThread();
          }
        }
      } catch {
        /* ignore */
      }
    },
    async ensureThread() {
      try {
        const resp = await fetch('/api/v1/chat/sessions', { method: 'POST' });
        const data = await resp.json();
        if (resp.ok && data.thread_id) {
          this.threadId = data.thread_id;
          localStorage.setItem(THREAD_KEY, this.threadId);
          await this.loadSessions();
        }
      } catch {
        /* ignore */
      }
    },
    async loadMessages() {
      if (!this.threadId) return;
      try {
        const resp = await fetch(`/api/v1/chat/messages?thread_id=${encodeURIComponent(this.threadId)}`);
        const data = await resp.json();
        if (resp.ok) {
          this.messages = data.messages || [];
          this.$nextTick(this.scrollToBottom);
        }
      } catch {
        /* ignore */
      }
    },
    async newThread() {
      if (this.busy) return;
      this.refs = [];
      this.chatError = '';
      this.closeMention();
      try {
        const resp = await fetch('/api/v1/chat/sessions', { method: 'POST' });
        const data = await resp.json();
        if (resp.ok && data.thread_id) {
          this.threadId = data.thread_id;
          localStorage.setItem(THREAD_KEY, this.threadId);
          this.messages = [];
          await this.loadSessions();
          this.sessionsOpen = false;
        }
      } catch {
        /* ignore */
      }
    },
    scrollToBottom() {
      const el = this.$refs.scrollRef;
      if (el) el.scrollTop = el.scrollHeight;
    },
    onKeydown(e) {
      if (this.mention.active && this.mentionItems.length) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          this.mention.index = (this.mention.index + 1) % this.mentionItems.length;
          return;
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          this.mention.index =
            (this.mention.index - 1 + this.mentionItems.length) % this.mentionItems.length;
          return;
        }
        if (e.key === 'Enter' && !e.metaKey && !e.ctrlKey) {
          e.preventDefault();
          this.selectMention(this.mentionItems[this.mention.index]);
          return;
        }
      }
      if (e.key === 'Escape' && this.mention.active) {
        e.preventDefault();
        this.closeMention();
        return;
      }
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        this.send();
      }
    },
    async send() {
      const text = this.draft.trim();
      if (!text || this.busy) return;
      if (!this.threadId) await this.ensureThread();

      this.busy = true;
      this.streaming = true;
      this.streamBuffer = '';
      this.chatError = '';
      this.closeMention();
      this.messages.push({ role: 'user', content: text });
      this.draft = '';
      this.$nextTick(this.scrollToBottom);

      try {
        const resp = await fetch('/api/v1/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            thread_id: this.threadId,
            message: text,
            reference_record_ids: this.refs.map((r) => r.id),
          }),
        });

        const newTid = resp.headers.get('X-Thread-Id');
        if (newTid) {
          this.threadId = newTid;
          localStorage.setItem(THREAD_KEY, newTid);
        }

        if (!resp.ok || !resp.body) {
          const err = await resp.json().catch(() => ({}));
          throw new Error(err.detail || `请求失败 (${resp.status})`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const payload = JSON.parse(line.slice(6));
            if (payload.error) throw new Error(payload.error);
            if (payload.delta) {
              this.streamBuffer += payload.delta;
              this.scrollToBottom();
            }
            if (payload.done) {
              this.messages.push({ role: 'assistant', content: this.streamBuffer });
              this.streamBuffer = '';
              this.streaming = false;
              this.loadSessions();
            }
          }
        }
      } catch (e) {
        this.chatError = String(e.message || e);
        this.messages.pop();
        this.draft = text;
      } finally {
        this.busy = false;
        this.streaming = false;
        this.streamBuffer = '';
        this.$nextTick(this.scrollToBottom);
      }
    },
  },
};
</script>

<style scoped>
.chat-panel {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #101428;
  border-left: 1px solid #252b48;
  box-sizing: border-box;
  min-width: 280px;
  max-width: 960px;
  transition: box-shadow 0.15s, background 0.15s;
}
.chat-panel--drop-target {
  box-shadow: inset 0 0 0 2px rgba(59, 91, 219, 0.55);
  background: #121836;
}
.chat-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 16px 14px 10px;
  flex-shrink: 0;
  border-bottom: 1px solid #252b48;
}
.chat-head-main {
  min-width: 0;
  flex: 1;
}
.chat-active-session {
  margin: 4px 0 0;
  color: #a8b8ff;
  font-size: 0.75rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chat-sessions {
  flex-shrink: 0;
  max-height: 200px;
  overflow-y: auto;
  border-bottom: 1px solid #252b48;
  background: #0f1220;
}
.chat-sessions-empty {
  margin: 0;
  padding: 10px 14px;
  color: #7a84a8;
  font-size: 0.8rem;
}
.chat-session-row {
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid #1a2038;
}
.chat-session-row.active {
  background: #1a2240;
}
.chat-session-btn {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 10px 8px 14px;
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.chat-session-btn:hover {
  background: #171d34;
}
.chat-session-title {
  font-size: 0.82rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}
.chat-session-meta {
  font-size: 0.68rem;
  color: #7a84a8;
}
.chat-session-del {
  flex-shrink: 0;
  width: 32px;
  border: none;
  background: transparent;
  color: #8b94b8;
  font-size: 1rem;
  cursor: pointer;
  opacity: 0;
}
.chat-session-row:hover .chat-session-del {
  opacity: 1;
}
.chat-session-del:hover {
  color: #ffb4b4;
  background: #3a1824;
}
.btn--active {
  border-color: #3b5bdb;
  background: #243055;
}
.chat-title {
  margin: 0;
  font-size: 1rem;
}
.chat-sub {
  margin: 4px 0 0;
  color: #7a84a8;
  font-size: 0.75rem;
}
.chat-head-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 14px;
}
.chat-empty {
  margin: 0;
  color: #7a84a8;
  font-size: 0.85rem;
  line-height: 1.5;
}
.chat-msg {
  margin-bottom: 14px;
}
.chat-role {
  font-size: 0.72rem;
  color: #8b94b8;
  margin-bottom: 4px;
}
.chat-bubble {
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 0.88rem;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-msg--user .chat-bubble {
  background: #243055;
  border: 1px solid #3d4a7a;
}
.chat-msg--assistant .chat-bubble {
  background: #151a2e;
  border: 1px solid #252b48;
}
.chat-bubble--stream {
  opacity: 0.95;
}
.chat-text {
  white-space: pre-wrap;
}
.msg-ref {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px 1px 4px;
  margin: 0 1px;
  vertical-align: baseline;
  background: #1c2440;
  border: 1px solid #3d4a7a;
  border-radius: 999px;
  font-size: 0.78rem;
  color: #b8c0e0;
  cursor: pointer;
  font-family: inherit;
  line-height: 1.45;
  max-width: min(100%, 280px);
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.msg-ref:hover {
  background: #243055;
  border-color: #4a6cf0;
  color: #e8ecff;
}
.chat-msg--user .msg-ref {
  background: #1a2240;
  border-color: #4a6cf0;
}
.chat-msg--user .msg-ref:hover {
  background: #243055;
}
.chat-refs {
  flex-shrink: 0;
  padding: 8px 14px;
  border-top: 1px solid #252b48;
  background: #12162a;
}
.chat-refs-bar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.chat-refs-hint {
  margin-left: auto;
  color: #6b7394;
  font-size: 0.68rem;
}
.chat-ref-toast {
  margin: 6px 0 0;
  color: #7ddea2;
  font-size: 0.75rem;
}
.chat-ref-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.chat-ref-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: #1c2440;
  border-radius: 999px;
  font-size: 0.72rem;
  color: #b8c0e0;
  max-width: 100%;
}
.ref-source {
  flex-shrink: 0;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.58rem;
  font-weight: 600;
  line-height: 1.3;
}
.ref-source--bili {
  background: #243055;
  color: #a8b8ff;
}
.ref-source--xhs {
  background: #3a1824;
  color: #ffb4c8;
}
.ref-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.chip-x {
  border: none;
  background: transparent;
  color: #8b94b8;
  cursor: pointer;
  padding: 0 2px;
  font-size: 0.9rem;
  line-height: 1;
  flex-shrink: 0;
}
.chip-x:hover {
  color: #ffb4b4;
}
.chat-composer {
  flex-shrink: 0;
  padding: 10px 14px 14px;
  border-top: 1px solid #252b48;
}
.chat-input-wrap {
  position: relative;
}
.chat-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #2a3358;
  border-radius: 8px;
  background: #0f1220;
  color: #e8ecff;
  font-size: 0.9rem;
  resize: vertical;
  min-height: 72px;
  font-family: inherit;
}
.chat-panel--drop-target .chat-input {
  border-color: #3b5bdb;
}
.mention-popup {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 6px);
  margin: 0;
  padding: 4px 0;
  list-style: none;
  max-height: 220px;
  overflow-y: auto;
  background: #151a2e;
  border: 1px solid #3d4a7a;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  z-index: 10;
}
.mention-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 0.82rem;
}
.mention-item:hover,
.mention-item--active {
  background: #243055;
}
.mention-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mention-meta {
  flex-shrink: 0;
  color: #7a84a8;
  font-size: 0.68rem;
}
.mention-empty {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 6px);
  margin: 0;
  padding: 8px 10px;
  background: #151a2e;
  border: 1px solid #3d4a7a;
  border-radius: 8px;
  color: #7a84a8;
  font-size: 0.8rem;
  z-index: 10;
}
.chat-send {
  width: 100%;
  margin-top: 8px;
}
.chat-error {
  margin: 8px 0 0;
  color: #ff8a8a;
  font-size: 0.82rem;
}
.btn {
  padding: 8px 16px;
  border: 1px solid #3d4a7a;
  border-radius: 8px;
  background: #1c2440;
  color: #e8ecff;
  cursor: pointer;
  font-size: 0.95rem;
}
.btn.tiny {
  padding: 4px 10px;
  font-size: 0.8rem;
}
.btn.primary {
  background: #3b5bdb;
  border-color: #3b5bdb;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
@media (max-width: 860px) {
  .chat-panel {
    width: 100% !important;
    max-width: none;
    height: auto;
    min-height: 50vh;
    border-left: none;
    border-top: 1px solid #252b48;
  }
  .chat-refs-hint {
    display: none;
  }
}
</style>
