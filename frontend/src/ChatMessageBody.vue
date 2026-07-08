<template>
  <div class="chat-message-body">
    <div v-for="(seg, si) in segments" :key="si" class="chat-segment">
      <div
        v-if="seg.type === 'text' && seg.text"
        class="chat-md"
        v-html="markdownHtml(seg.text)"
      />
      <button
        v-else-if="seg.type === 'ref'"
        type="button"
        class="msg-ref"
        :title="`打开笔记：${seg.displayTitle}`"
        @click="$emit('open-record', seg.id)"
      >
        <span
          :class="['ref-source', seg.source === 'xiaohongshu' ? 'ref-source--xhs' : 'ref-source--bili']"
        >
          {{ seg.source === 'xiaohongshu' ? '小红书' : 'B站' }}
        </span>
        <span class="ref-title">{{ seg.displayTitle }}</span>
      </button>
      <span v-else-if="seg.type === 'folder-ref'" class="msg-ref msg-ref--folder">
        <span class="ref-folder-icon">📂</span>
        <span class="ref-folder-label">分类</span>
        <span class="ref-title">{{ seg.displayName }}</span>
      </span>
    </div>
  </div>
</template>

<script>
import { renderMarkdownHtml } from './chatMarkdown.js';
import { parseMessageSegments } from './messageContent.js';

export default {
  name: 'ChatMessageBody',
  emits: ['open-record'],
  props: {
    content: { type: String, default: '' },
    recordMap: { type: Object, default: () => ({}) },
  },
  computed: {
    segments() {
      return parseMessageSegments(this.content, this.recordMap);
    },
  },
  methods: {
    markdownHtml(text) {
      return renderMarkdownHtml(text);
    },
  },
};
</script>

<style scoped>
.chat-message-body {
  display: block;
}
.chat-segment {
  display: inline;
}
.chat-md {
  display: inline;
}
.chat-md :deep(p) {
  margin: 0.35em 0;
}
.chat-md :deep(p:first-child) {
  margin-top: 0;
}
.chat-md :deep(p:last-child) {
  margin-bottom: 0;
}
.chat-md :deep(ul),
.chat-md :deep(ol) {
  margin: 0.35em 0;
  padding-left: 1.25em;
}
.chat-md :deep(li) {
  margin: 0.15em 0;
}
.chat-md :deep(h1),
.chat-md :deep(h2),
.chat-md :deep(h3),
.chat-md :deep(h4) {
  margin: 0.5em 0 0.35em;
  font-size: 1em;
  font-weight: 600;
  line-height: 1.35;
}
.chat-md :deep(h1) {
  font-size: 1.05em;
}
.chat-md :deep(blockquote) {
  margin: 0.35em 0;
  padding-left: 10px;
  border-left: 3px solid #3d4a7a;
  color: #9aa8d8;
}
.chat-md :deep(pre) {
  margin: 0.5em 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #0d1117;
  border: 1px solid #252b48;
  overflow-x: auto;
  font-size: 0.82rem;
  line-height: 1.45;
}
.chat-md :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.86em;
}
.chat-md :deep(:not(pre) > code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: #1a2040;
  border: 1px solid #2a3358;
}
.chat-md :deep(table) {
  width: 100%;
  margin: 0.5em 0;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.chat-md :deep(th),
.chat-md :deep(td) {
  border: 1px solid #3d4a7a;
  padding: 4px 8px;
  text-align: left;
}
.chat-md :deep(th) {
  background: #1a2040;
}
.chat-md :deep(a) {
  color: #7ea8ff;
  text-decoration: underline;
}
.chat-md :deep(hr) {
  border: none;
  border-top: 1px solid #3d4a7a;
  margin: 0.6em 0;
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
.msg-ref--folder {
  cursor: default;
}
.ref-source {
  flex-shrink: 0;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 600;
}
.ref-source--bili {
  background: #fb729933;
  color: #fb7299;
}
.ref-source--xhs {
  background: #ff244233;
  color: #ff6b81;
}
.ref-folder-icon {
  flex-shrink: 0;
}
.ref-folder-label {
  flex-shrink: 0;
  font-size: 0.68rem;
  color: #8ea4ff;
}
.ref-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
