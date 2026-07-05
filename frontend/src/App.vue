<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-head">
        <h2>字幕库</h2>
        <button class="btn tiny" @click="loadRecords">刷新</button>
      </div>
      <p v-if="!records.length" class="empty">暂无保存记录</p>
      <ul v-else class="record-list">
        <li
          v-for="item in records"
          :key="item.id"
          :class="['record-item', { active: result?.record_id === item.id }]"
          @click="openRecord(item.id)"
        >
          <div class="record-title">{{ item.title || item.bvid }}</div>
          <div class="record-meta">
            {{ item.bvid }} · P{{ item.page }} · {{ item.line_count }} 条
          </div>
          <button class="btn tiny danger" @click.stop="removeRecord(item.id)">删除</button>
        </li>
      </ul>
    </aside>

    <main class="main">
      <header class="head">
        <h1>B 站字幕提取</h1>
        <p class="hint">粘贴视频链接，提取 CC / AI 字幕并保存到本地库</p>
      </header>

      <section class="panel">
        <label class="label" for="url">视频链接</label>
        <input
          id="url"
          v-model="url"
          class="input"
          type="text"
          placeholder="https://www.bilibili.com/video/BVxxxx 或 b23.tv 短链"
          @keyup.enter="extract(false)"
        />

        <div class="row">
          <label class="label inline" for="page">分 P</label>
          <input id="page" v-model.number="page" class="input short" type="number" min="1" />
          <label class="check">
            <input v-model="autoSave" type="checkbox" />
            提取后自动保存
          </label>
          <button class="btn primary" :disabled="loading" @click="extract(false)">
            {{ loading ? '提取中…' : '提取字幕' }}
          </button>
        </div>

        <p v-if="error" class="error">{{ error }}</p>
      </section>

      <section v-if="result" class="panel result">
        <h2 class="title">{{ result.title }}</h2>
        <p class="meta">
          {{ result.bvid }} · P{{ result.page }}
          <span v-if="result.page_title">（{{ result.page_title }}）</span>
          · {{ result.lines.length }} 条
          <span v-if="result.selected_track">
            · {{ result.selected_track.lan_doc || result.selected_track.lan }}
          </span>
          <span v-if="result.record_id"> · 已保存 #{{ result.record_id }}</span>
        </p>

        <div v-if="result.tracks.length > 1" class="tracks">
          <span class="label inline">字幕轨：</span>
          <span v-for="t in result.tracks" :key="String(t.id) + t.lan" class="tag">
            {{ t.lan_doc || t.lan }}
          </span>
        </div>

        <div class="toolbar">
          <button class="btn" @click="copyText">复制纯文本</button>
          <button v-if="!result.record_id" class="btn" :disabled="saving" @click="saveCurrent">
            {{ saving ? '保存中…' : '保存到库' }}
          </button>
          <span v-if="copied" class="copied">已复制</span>
          <span v-if="savedTip" class="copied">{{ savedTip }}</span>
        </div>

        <pre class="pre">{{ result.text }}</pre>
      </section>
    </main>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return {
      url: '',
      page: 1,
      autoSave: true,
      loading: false,
      saving: false,
      error: '',
      result: null,
      records: [],
      copied: false,
      savedTip: '',
    };
  },
  mounted() {
    this.loadRecords();
  },
  methods: {
    async loadRecords() {
      try {
        const resp = await fetch('/api/v1/subtitle/records');
        this.records = resp.ok ? await resp.json() : [];
      } catch {
        this.records = [];
      }
    },
    async extract(fromRecord) {
      this.error = '';
      if (!fromRecord) {
        this.result = null;
      }
      this.copied = false;
      this.savedTip = '';
      if (!this.url.trim()) {
        this.error = '请输入 B 站视频链接';
        return;
      }
      this.loading = true;
      try {
        const resp = await fetch('/api/v1/subtitle/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: this.url.trim(),
            page: this.page || 1,
            save: this.autoSave,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || data.message || `请求失败 (${resp.status})`;
          return;
        }
        this.result = data;
        if (data.record_id) {
          this.savedTip = '已自动保存';
          await this.loadRecords();
        }
      } catch (e) {
        this.error = String(e);
      } finally {
        this.loading = false;
      }
    },
    async openRecord(id) {
      this.error = '';
      this.copied = false;
      this.savedTip = '';
      try {
        const resp = await fetch(`/api/v1/subtitle/records/${id}`);
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || '加载失败';
          return;
        }
        this.result = data;
        this.url = data.source_url || `https://www.bilibili.com/video/${data.bvid}`;
        this.page = data.page || 1;
      } catch (e) {
        this.error = String(e);
      }
    },
    async saveCurrent() {
      if (!this.result) return;
      this.saving = true;
      this.savedTip = '';
      try {
        const resp = await fetch('/api/v1/subtitle/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_url: this.result.source_url || this.url.trim(),
            bvid: this.result.bvid,
            aid: this.result.aid,
            cid: this.result.cid,
            title: this.result.title,
            page: this.result.page,
            page_title: this.result.page_title,
            selected_track: this.result.selected_track,
            lines: this.result.lines,
            text: this.result.text,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || '保存失败';
          return;
        }
        this.result.record_id = data.id;
        this.savedTip = '已保存到库';
        await this.loadRecords();
      } catch (e) {
        this.error = String(e);
      } finally {
        this.saving = false;
      }
    },
    async removeRecord(id) {
      if (!window.confirm('确定删除这条字幕记录？')) return;
      try {
        const resp = await fetch(`/api/v1/subtitle/records/${id}`, { method: 'DELETE' });
        if (!resp.ok) {
          const data = await resp.json();
          this.error = data.detail || '删除失败';
          return;
        }
        if (this.result?.record_id === id) {
          this.result = null;
        }
        await this.loadRecords();
      } catch (e) {
        this.error = String(e);
      }
    },
    async copyText() {
      if (!this.result?.text) return;
      try {
        await navigator.clipboard.writeText(this.result.text);
        this.copied = true;
        setTimeout(() => {
          this.copied = false;
        }, 2000);
      } catch (e) {
        this.error = '复制失败：' + String(e);
      }
    },
  },
};
</script>

<style>
body {
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
  background: #0f1220;
  color: #e8ecff;
}
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 280px;
  flex-shrink: 0;
  padding: 20px 16px;
  background: #12162a;
  border-right: 1px solid #252b48;
  box-sizing: border-box;
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.sidebar-head h2 {
  margin: 0;
  font-size: 1rem;
}
.main {
  flex: 1;
  max-width: 900px;
  padding: 24px 20px 48px;
}
.head h1 {
  margin: 0 0 6px;
  font-size: 1.6rem;
}
.hint {
  margin: 0;
  color: #9aa3c7;
  font-size: 0.95rem;
}
.empty {
  color: #7a84a8;
  font-size: 0.88rem;
}
.record-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.record-item {
  position: relative;
  margin-bottom: 8px;
  padding: 10px 10px 28px;
  background: #151a2e;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
}
.record-item.active {
  border-color: #3b5bdb;
}
.record-item:hover {
  background: #1a2038;
}
.record-title {
  font-size: 0.92rem;
  line-height: 1.35;
  margin-bottom: 4px;
}
.record-meta {
  color: #8b94b8;
  font-size: 0.78rem;
}
.record-item .btn.danger {
  position: absolute;
  right: 8px;
  bottom: 6px;
}
.panel {
  margin-top: 20px;
  padding: 16px;
  background: #151a2e;
  border-radius: 10px;
}
.label {
  display: block;
  margin-bottom: 6px;
  color: #b8c0e0;
  font-size: 0.9rem;
}
.label.inline {
  display: inline;
  margin: 0 8px 0 0;
}
.input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #2a3358;
  border-radius: 8px;
  background: #0f1220;
  color: #e8ecff;
  font-size: 1rem;
}
.input.short {
  width: 72px;
  margin-right: 12px;
}
.row {
  display: flex;
  align-items: center;
  margin-top: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #b8c0e0;
  font-size: 0.88rem;
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
.btn.danger {
  border-color: #6b3040;
  background: #3a1824;
  color: #ffb4b4;
}
.btn.primary {
  background: #3b5bdb;
  border-color: #3b5bdb;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error {
  margin: 12px 0 0;
  color: #ff8a8a;
  font-size: 0.92rem;
  line-height: 1.5;
}
.result .title {
  margin: 0 0 8px;
  font-size: 1.15rem;
}
.meta {
  margin: 0 0 12px;
  color: #9aa3c7;
  font-size: 0.88rem;
}
.tracks {
  margin-bottom: 12px;
}
.tag {
  display: inline-block;
  margin: 0 6px 6px 0;
  padding: 2px 8px;
  background: #1c2440;
  border-radius: 6px;
  font-size: 0.85rem;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.copied {
  color: #7ddea2;
  font-size: 0.85rem;
}
.pre {
  margin: 0;
  max-height: 480px;
  padding: 12px;
  background: #0f1220;
  border-radius: 8px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.9rem;
  line-height: 1.55;
}
@media (max-width: 860px) {
  .layout {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid #252b48;
  }
}
</style>
