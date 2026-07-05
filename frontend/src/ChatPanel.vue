<template>
  <aside class="chat-panel" :style="{ width: `${width}px` }">
    <header class="chat-head">
      <div>
        <h2 class="chat-title">对话助手</h2>
        <p class="chat-sub">引用库内内容，像 ChatGPT 一样追问</p>
      </div>
      <div class="chat-head-actions">
        <button type="button" class="btn tiny" :disabled="busy" @click="newThread">新对话</button>
        <button type="button" class="btn tiny" :disabled="busy || !messages.length" @click="clearThread">
          清空
        </button>
      </div>
    </header>

    <div ref="scrollRef" class="chat-messages">
      <p v-if="!messages.length" class="chat-empty">
        发送消息开始对话。可引用当前提取结果或左侧选中的记录作为上下文。
      </p>
      <article
        v-for="(m, idx) in messages"
        :key="idx"
        :class="['chat-msg', m.role === 'user' ? 'chat-msg--user' : 'chat-msg--assistant']"
      >
        <div class="chat-role">{{ m.role === 'user' ? '你' : '助手' }}</div>
        <div class="chat-bubble">{{ m.content }}</div>
      </article>
      <article v-if="streaming" class="chat-msg chat-msg--assistant">
        <div class="chat-role">助手</div>
        <div class="chat-bubble chat-bubble--stream">{{ streamBuffer || '…' }}</div>
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
      </div>
      <div v-if="refs.length" class="chat-ref-chips">
        <span v-for="r in refs" :key="r.id" class="chat-ref-chip">
          {{ r.title || r.id }}
          <button type="button" class="chip-x" @click="removeRef(r.id)">×</button>
        </span>
      </div>
    </div>

    <footer class="chat-composer">
      <textarea
        v-model="draft"
        class="chat-input"
        rows="3"
        placeholder="输入问题… ⌘/Ctrl+Enter 发送"
        :disabled="busy"
        @keydown="onKeydown"
      />
      <button type="button" class="btn primary chat-send" :disabled="busy || !draft.trim()" @click="send">
        {{ busy ? '生成中…' : '发送' }}
      </button>
      <p v-if="chatError" class="chat-error">{{ chatError }}</p>
    </footer>
  </aside>
</template>

<script>
const THREAD_KEY = 'b-subtitle-chat-thread';

export default {
  name: 'ChatPanel',
  props: {
    width: { type: Number, default: 400 },
    currentRecordId: { type: String, default: '' },
    currentRecordTitle: { type: String, default: '' },
    selectedIds: { type: Array, default: () => [] },
    recordMap: { type: Object, default: () => ({}) },
  },
  data() {
    return {
      threadId: '',
      messages: [],
      refs: [],
      draft: '',
      busy: false,
      streaming: false,
      streamBuffer: '',
      chatError: '',
    };
  },
  mounted() {
    this.threadId = localStorage.getItem(THREAD_KEY) || '';
    if (this.threadId) {
      this.loadMessages();
    } else {
      this.ensureThread();
    }
  },
  methods: {
    hasRef(id) {
      return this.refs.some((r) => r.id === id);
    },
    addRef(id, title) {
      if (!id || this.hasRef(id)) return;
      this.refs.push({ id, title: title || id });
    },
    removeRef(id) {
      this.refs = this.refs.filter((r) => r.id !== id);
    },
    attachCurrent() {
      if (!this.currentRecordId) return;
      this.addRef(this.currentRecordId, this.currentRecordTitle);
    },
    attachSelected() {
      for (const id of this.selectedIds) {
        const rec = this.recordMap[id];
        this.addRef(id, rec?.title || id);
      }
    },
    async ensureThread() {
      try {
        const resp = await fetch('/api/v1/chat/sessions', { method: 'POST' });
        const data = await resp.json();
        if (resp.ok && data.thread_id) {
          this.threadId = data.thread_id;
          localStorage.setItem(THREAD_KEY, this.threadId);
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
      try {
        const resp = await fetch('/api/v1/chat/sessions', { method: 'POST' });
        const data = await resp.json();
        if (resp.ok && data.thread_id) {
          this.threadId = data.thread_id;
          localStorage.setItem(THREAD_KEY, this.threadId);
          this.messages = [];
        }
      } catch {
        /* ignore */
      }
    },
    async clearThread() {
      if (!this.threadId || this.busy) return;
      await fetch(`/api/v1/chat/messages?thread_id=${encodeURIComponent(this.threadId)}`, {
        method: 'DELETE',
      });
      this.messages = [];
      this.chatError = '';
    },
    scrollToBottom() {
      const el = this.$refs.scrollRef;
      if (el) el.scrollTop = el.scrollHeight;
    },
    onKeydown(e) {
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
  max-width: 640px;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chip-x {
  border: none;
  background: transparent;
  color: #8b94b8;
  cursor: pointer;
  padding: 0 2px;
  font-size: 0.9rem;
  line-height: 1;
}
.chip-x:hover {
  color: #ffb4b4;
}
.chat-composer {
  flex-shrink: 0;
  padding: 10px 14px 14px;
  border-top: 1px solid #252b48;
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
}
</style>
