<template>
  <div class="app-shell">
    <button
      v-if="view === 'main'"
      type="button"
      class="top-settings"
      title="设置"
      @click="view = 'settings'"
    >
      设置
    </button>

    <SettingsPage v-if="view === 'settings'" @back="view = 'main'" />

    <div v-else class="layout">
    <aside class="sidebar">
      <div class="sidebar-head">
        <h2>字幕库</h2>
        <button class="btn tiny" @click="loadRecords">刷新</button>
      </div>

      <div v-if="records.length" class="batch-bar">
        <label class="check">
          <input
            type="checkbox"
            :checked="allSelected"
            :indeterminate.prop="someSelected && !allSelected"
            @change="toggleSelectAll"
          />
          全选
        </label>
        <span class="batch-count">{{ selectedIds.length }} 条</span>
        <div class="batch-actions">
          <button class="btn tiny" :disabled="!selectedIds.length" @click="batchCopy">
            复制
          </button>
          <button class="btn tiny" :disabled="!selectedIds.length" @click="batchExport('txt')">
            导出 txt
          </button>
          <button class="btn tiny" :disabled="!selectedIds.length" @click="batchExport('json')">
            导出 json
          </button>
          <button
            class="btn tiny danger"
            :disabled="!selectedIds.length"
            @click="batchDelete"
          >
            删除
          </button>
        </div>
      </div>

      <p v-if="!records.length" class="empty">暂无保存记录</p>
      <div v-else class="sidebar-scroll">
        <ul class="card-list">
          <li
            v-for="item in records"
            :key="item.id"
            :class="[
              'record-card',
              {
                active: result?.record_id === item.id,
                selected: selectedIds.includes(item.id),
              },
            ]"
          >
            <div class="card-top">
              <label class="card-check" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedIds.includes(item.id)"
                  @change="toggleSelect(item.id)"
                />
              </label>
              <button class="card-main" type="button" @click="openRecord(item.id)">
                <h3 class="card-title" :title="item.title || item.bvid">
                  {{ item.title || item.bvid }}
                </h3>
                <p v-if="item.page_title" class="card-subtitle">{{ item.page_title }}</p>
              </button>
              <button
                class="card-del"
                type="button"
                title="删除"
                @click.stop="removeRecord(item.id)"
              >
                ×
              </button>
            </div>

            <button class="card-body" type="button" @click="openRecord(item.id)">
              <div class="card-tags">
                <span class="card-tag card-tag--bvid">{{ item.bvid }}</span>
                <span class="card-tag">P{{ item.page }}</span>
                <span v-if="item.lan_doc" class="card-tag card-tag--lan">{{ item.lan_doc }}</span>
                <span class="card-tag">{{ item.line_count }} 条</span>
              </div>
              <div class="card-footer">
                <span class="card-time">{{ formatUpdatedAt(item.updated_at) }}</span>
                <span class="card-id">#{{ item.id }}</span>
              </div>
            </button>
          </li>
        </ul>
      </div>
    </aside>

    <main class="main">
      <header class="head">
        <h1>B 站字幕提取</h1>
        <p class="hint">粘贴视频链接，提取后自动保存到左侧字幕库</p>
      </header>

      <section v-if="duplicatePrompt" class="panel duplicate">
        <p>
          本地已有该视频字幕记录
          <strong>#{{ duplicatePrompt.existing_record_id }}</strong>
          （{{ duplicatePrompt.title }}）
        </p>
        <div class="toolbar">
          <button class="btn primary" @click="viewExisting">直接查看已有记录</button>
          <button class="btn" :disabled="loading" @click="extract(true)">
            {{ loading ? '提取中…' : '重新提取' }}
          </button>
          <button class="btn" @click="duplicatePrompt = null">取消</button>
        </div>
      </section>

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
          <span v-if="result.duplicate" class="dup-tag">来自本地库</span>
        </p>

        <div v-if="result.tracks.length > 1" class="tracks">
          <span class="label inline">字幕轨：</span>
          <span v-for="t in result.tracks" :key="String(t.id) + t.lan" class="tag">
            {{ t.lan_doc || t.lan }}
          </span>
        </div>

        <div class="toolbar">
          <button class="btn" @click="copyText">复制纯文本</button>
          <span v-if="copied" class="copied">已复制</span>
          <span v-if="savedTip" class="copied">{{ savedTip }}</span>
        </div>

        <pre class="pre">{{ result.text }}</pre>
      </section>
    </main>
    </div>
  </div>
</template>

<script>
import SettingsPage from './SettingsPage.vue';

export default {
  name: 'App',
  components: { SettingsPage },
  data() {
    return {
      view: 'main',
      url: '',
      page: 1,
      loading: false,
      error: '',
      result: null,
      records: [],
      selectedIds: [],
      copied: false,
      savedTip: '',
      duplicatePrompt: null,
    };
  },
  computed: {
    allSelected() {
      return this.records.length > 0 && this.selectedIds.length === this.records.length;
    },
    someSelected() {
      return this.selectedIds.length > 0;
    },
  },
  mounted() {
    this.loadRecords();
  },
  methods: {
    async loadRecords() {
      try {
        const resp = await fetch('/api/v1/subtitle/records');
        this.records = resp.ok ? await resp.json() : [];
        this.selectedIds = this.selectedIds.filter((id) =>
          this.records.some((r) => r.id === id)
        );
      } catch {
        this.records = [];
        this.selectedIds = [];
      }
    },
    toggleSelect(id) {
      const idx = this.selectedIds.indexOf(id);
      if (idx >= 0) {
        this.selectedIds.splice(idx, 1);
      } else {
        this.selectedIds.push(id);
      }
    },
    toggleSelectAll() {
      if (this.allSelected) {
        this.selectedIds = [];
      } else {
        this.selectedIds = this.records.map((r) => r.id);
      }
    },
    formatUpdatedAt(iso) {
      if (!iso) return '—';
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },
    async extract(force) {
      this.error = '';
      if (!force) {
        this.result = null;
        this.duplicatePrompt = null;
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
            save: true,
            force: !!force,
          }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || data.message || `请求失败 (${resp.status})`;
          return;
        }
        if (data.duplicate && data.existing_record_id && !force) {
          this.duplicatePrompt = data;
          return;
        }
        this.duplicatePrompt = null;
        this.result = data;
        if (data.record_id) {
          this.savedTip = force ? '已重新提取并保存' : '已保存到库';
        }
        await this.loadRecords();
      } catch (e) {
        this.error = String(e);
      } finally {
        this.loading = false;
      }
    },
    viewExisting() {
      if (!this.duplicatePrompt) return;
      this.result = { ...this.duplicatePrompt, duplicate: true };
      this.duplicatePrompt = null;
      this.savedTip = '已加载本地记录';
    },
    async openRecord(id) {
      this.error = '';
      this.copied = false;
      this.savedTip = '';
      this.duplicatePrompt = null;
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
    async removeRecord(id) {
      if (!window.confirm('确定删除这条字幕记录？')) return;
      await this._deleteIds([id]);
    },
    async batchDelete() {
      if (!this.selectedIds.length) return;
      if (!window.confirm(`确定删除选中的 ${this.selectedIds.length} 条记录？`)) return;
      await this._deleteIds([...this.selectedIds]);
    },
    async _deleteIds(ids) {
      try {
        const resp = await fetch('/api/v1/subtitle/records/batch-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || '删除失败';
          return;
        }
        if (this.result?.record_id && ids.includes(this.result.record_id)) {
          this.result = null;
        }
        this.selectedIds = this.selectedIds.filter((id) => !data.deleted.includes(id));
        await this.loadRecords();
      } catch (e) {
        this.error = String(e);
      }
    },
    async batchCopy() {
      if (!this.selectedIds.length) return;
      try {
        const resp = await fetch('/api/v1/subtitle/records/batch-export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: this.selectedIds, format: 'txt' }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || '复制失败';
          return;
        }
        await navigator.clipboard.writeText(data.content);
        this.copied = true;
        setTimeout(() => {
          this.copied = false;
        }, 2000);
      } catch (e) {
        this.error = '复制失败：' + String(e);
      }
    },
    async batchExport(fmt) {
      if (!this.selectedIds.length) return;
      try {
        const resp = await fetch('/api/v1/subtitle/records/batch-export', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: this.selectedIds, format: fmt }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || '导出失败';
          return;
        }
        const blob = new Blob([data.content], {
          type: fmt === 'json' ? 'application/json' : 'text/plain',
        });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = data.filename || `subtitles_export.${fmt}`;
        a.click();
        URL.revokeObjectURL(a.href);
      } catch (e) {
        this.error = '导出失败：' + String(e);
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
.app-shell {
  position: relative;
  min-height: 100vh;
}
.top-settings {
  position: fixed;
  top: 16px;
  right: 20px;
  z-index: 100;
  padding: 8px 14px;
  border: 1px solid #3d4a7a;
  border-radius: 8px;
  background: #1c2440;
  color: #e8ecff;
  font-size: 0.9rem;
  cursor: pointer;
}
.top-settings:hover {
  background: #243055;
  border-color: #3b5bdb;
}
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 20px 16px 16px;
  background: #12162a;
  border-right: 1px solid #252b48;
  box-sizing: border-box;
  overflow: hidden;
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.sidebar-head h2 {
  margin: 0;
  font-size: 1rem;
}
.batch-bar {
  margin-bottom: 12px;
  padding: 8px 10px;
  background: #151a2e;
  border-radius: 8px;
  font-size: 0.82rem;
  flex-shrink: 0;
}
.batch-count {
  color: #8b94b8;
  margin-left: 8px;
}
.batch-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.sidebar-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-right: -6px;
  padding-right: 6px;
}
.sidebar-scroll::-webkit-scrollbar {
  width: 6px;
}
.sidebar-scroll::-webkit-scrollbar-thumb {
  background: #2a3358;
  border-radius: 3px;
}
.empty {
  color: #7a84a8;
  font-size: 0.88rem;
  flex-shrink: 0;
}
.card-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.record-card {
  background: #151a2e;
  border: 1px solid #252b48;
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}
.record-card:hover {
  background: #1a2038;
  border-color: #323b5c;
}
.record-card.active {
  border-color: #3b5bdb;
  box-shadow: 0 0 0 1px rgba(59, 91, 219, 0.35);
}
.record-card.selected {
  border-color: #4a6cf0;
  background: #171d34;
}
.card-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 10px 0;
}
.card-check {
  flex-shrink: 0;
  padding-top: 3px;
  cursor: pointer;
}
.card-main {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.card-title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-subtitle {
  margin: 4px 0 0;
  color: #8b94b8;
  font-size: 0.76rem;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-del {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #8b94b8;
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
}
.card-del:hover {
  background: #3a1824;
  color: #ffb4b4;
}
.card-body {
  display: block;
  width: 100%;
  margin: 0;
  padding: 8px 10px 10px 34px;
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.card-tag {
  display: inline-block;
  padding: 2px 7px;
  background: #1c2440;
  border-radius: 5px;
  color: #9aa3c7;
  font-size: 0.72rem;
  line-height: 1.4;
}
.card-tag--bvid {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #b8c0e0;
}
.card-tag--lan {
  background: #243055;
  color: #a8b8ff;
}
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  gap: 8px;
}
.card-time {
  color: #7a84a8;
  font-size: 0.72rem;
}
.card-id {
  color: #5c668a;
  font-size: 0.68rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.main {
  flex: 1;
  max-width: 900px;
  padding: 24px 20px 48px;
  overflow-y: auto;
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
.panel {
  margin-top: 20px;
  padding: 16px;
  background: #151a2e;
  border-radius: 10px;
}
.panel.duplicate {
  border: 1px solid #3b5bdb;
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
.dup-tag {
  color: #7ddea2;
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
    height: auto;
    max-height: 42vh;
    border-right: none;
    border-bottom: 1px solid #252b48;
  }
}
</style>
