<template>
  <div class="app-shell">
    <SettingsPage v-if="view === 'settings'" @back="view = 'main'" />

    <div
      v-else
      class="layout"
      :class="{
        'layout--resizing-sidebar': resizingSidebar,
        'layout--resizing-chat': resizingChat,
      }"
    >
    <aside class="sidebar" :style="{ width: `${sidebarWidth}px` }">
      <div class="sidebar-head">
        <h2>笔记库<span v-if="tree.total_count" class="lib-count"> · {{ tree.total_count }} 条笔记</span></h2>
        <div class="sidebar-head-actions">
          <button class="btn tiny" title="新建根文件夹" @click="createFolder(null)">+ 文件夹</button>
          <button class="btn tiny" @click="loadTree">刷新</button>
        </div>
      </div>

      <p class="save-hint">新提取默认保存到「未分类」，可拖拽或批量移动到文件夹</p>
      <p v-if="libraryTip" class="library-tip">{{ libraryTip }}</p>
      <div v-if="allRecordIds.length" class="batch-bar">
        <label class="check">
          <input
            type="checkbox"
            :checked="allSelected"
            :indeterminate.prop="someSelected && !allSelected"
            @change="toggleSelectAll"
          />
          全选
        </label>
        <span class="batch-count">{{ selectedIds.length }} 条笔记</span>
        <span class="batch-hint">框选 · 拖到文件夹</span>
        <div class="batch-actions">
          <button class="btn tiny" :disabled="!selectedIds.length" @click="batchMove">
            移动
          </button>
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

      <p v-if="!allRecordIds.length" class="empty">暂无保存笔记</p>
      <div
        v-else
        ref="treePane"
        class="sidebar-scroll"
        :class="{
          'sidebar-scroll--marquee': marquee.active,
          'sidebar-scroll--dragging': draggingRecordIds.length > 0,
        }"
        @mousedown="onMarqueeStart"
      >
        <div
          v-if="marquee.active && marquee.w > 2 && marquee.h > 2"
          class="marquee-box"
          :style="marqueeStyle"
        />
        <LibraryTree
          :folders="tree.folders"
          :uncategorized="tree.uncategorized"
          :expanded-ids="expandedIds"
          :selected-ids="selectedIds"
          :dragging-record-ids="draggingRecordIds"
          :drop-target-id="dropTargetFolderId"
          :active-record-id="result?.record_id || ''"
          :active-folder-id="activeFolderId"
          @toggle-expand="toggleExpand"
          @select-folder="selectFolder"
          @folder-action="onFolderAction"
          @open-record="openRecord"
          @toggle-select="toggleSelect"
          @remove-record="removeRecord"
          @record-drag-start="onRecordDragStart"
          @record-drag-end="onRecordDragEnd"
          @folder-drag-over="onFolderDragOver"
          @folder-drag-leave="onFolderDragLeave"
          @folder-drop="onFolderDrop"
          @folder-ref-drag-empty="onFolderRefDragEmpty"
        />
      </div>

      <div class="sidebar-footer">
        <button
          type="button"
          class="sidebar-settings"
          title="设置"
          @click="view = 'settings'"
        >
          <svg class="sidebar-settings-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
              stroke="currentColor"
              stroke-width="1.5"
            />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span>设置</span>
        </button>
      </div>
    </aside>

    <div
      class="sidebar-resizer"
      title="拖拽调整笔记库宽度"
      @mousedown="startSidebarResize"
    />

    <div class="workspace">
    <main class="main extract-pane">
      <header class="head">
        <h1>笔记提取</h1>
        <p class="hint">粘贴 B 站视频或小红书笔记链接，提取后自动保存到左侧笔记库，右侧可对话分析</p>
      </header>

      <section v-if="duplicatePrompt" class="panel duplicate">
        <p>
          本地已有该笔记
          <strong>#{{ duplicatePrompt.existing_record_id }}</strong>
          （{{ duplicatePrompt.title }}）
        </p>
        <div class="toolbar">
          <button class="btn primary" @click="viewExisting">直接查看已有笔记</button>
          <button class="btn" :disabled="loading" @click="extract(true)">
            {{ loading ? '提取中…' : '重新提取' }}
          </button>
          <button class="btn" @click="duplicatePrompt = null">取消</button>
        </div>
      </section>

      <section class="panel">
        <label class="label" for="url">链接</label>
        <input
          id="url"
          v-model="url"
          class="input"
          type="text"
          placeholder="B 站 BV 链接 / b23.tv 短链，或小红书 xhslink / explore 链接"
          @keyup.enter="extract(false)"
        />

        <div class="row">
          <span v-if="urlPlatform" class="platform-tag">{{ urlPlatformLabel }}</span>
          <template v-if="urlPlatform !== 'xiaohongshu'">
            <label class="label inline" for="page">分 P</label>
            <input id="page" v-model.number="page" class="input short" type="number" min="1" />
          </template>
          <button class="btn primary" :disabled="loading" @click="extract(false)">
            {{ loading ? '提取中…' : extractButtonLabel }}
          </button>
        </div>

        <p v-if="error" class="error">{{ error }}</p>
      </section>

      <section v-if="result" class="panel result">
        <h2 class="title">{{ result.title }}</h2>
        <p class="meta">
          <span class="source-badge">{{ result.source === 'xiaohongshu' ? '小红书' : 'B站' }}</span>
          <template v-if="result.source === 'xiaohongshu'">
            {{ result.note_id || '—' }}
            · {{ result.note_type === 'video' ? '视频' : '图文' }}
            <span v-if="result.author"> · {{ result.author }}</span>
            <span v-if="result.tags && result.tags.length"> · {{ result.tags.length }} 标签</span>
          </template>
          <template v-else>
            {{ result.bvid }} · P{{ result.page }}
            <span v-if="result.page_title">（{{ result.page_title }}）</span>
            · {{ result.lines.length }} 条
            <span v-if="result.selected_track">
              · {{ result.selected_track.lan_doc || result.selected_track.lan }}
            </span>
          </template>
          <span v-if="result.record_id"> · 已保存 #{{ result.record_id }}</span>
          <span v-if="result.duplicate" class="dup-tag">来自本地库</span>
        </p>

        <div v-if="result.source === 'xiaohongshu' && result.tags && result.tags.length" class="tracks">
          <span v-for="tag in result.tags" :key="tag" class="tag">#{{ tag }}</span>
        </div>

        <div v-if="result.source === 'xiaohongshu' && result.images && result.images.length" class="xhs-images">
          <img
            v-for="(img, idx) in result.images.slice(0, 6)"
            :key="img + idx"
            :src="img"
            alt=""
            class="xhs-thumb"
            loading="lazy"
          />
        </div>

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

    <div
      class="chat-resizer"
      title="拖拽调整对话区宽度"
      @mousedown="startChatResize"
    />

    <ChatPanel
      :width="chatWidth"
      :current-record-id="result?.record_id || ''"
      :current-record-title="result?.title || ''"
      :selected-ids="selectedIds"
      :record-map="recordMap"
      :all-records="allRecords"
      @open-record="openRecord"
    />
    </div>
    </div>
  </div>
</template>

<script>
import SettingsPage from './SettingsPage.vue';
import LibraryTree from './LibraryTree.vue';
import ChatPanel from './ChatPanel.vue';

export default {
  name: 'App',
  components: { SettingsPage, LibraryTree, ChatPanel },
  data() {
    return {
      view: 'main',
      url: '',
      page: 1,
      loading: false,
      error: '',
      result: null,
      tree: { folders: [], uncategorized: [], total_count: 0 },
      expandedIds: new Set(['__uncategorized__']),
      activeFolderId: null,
      selectedIds: [],
      copied: false,
      savedTip: '',
      duplicatePrompt: null,
      sidebarWidth: 360,
      chatWidth: 400,
      resizingSidebar: false,
      resizingChat: false,
      draggingRecordIds: [],
      dragPurpose: null,
      dropTargetFolderId: null,
      marquee: { active: false, startX: 0, startY: 0, x: 0, y: 0, w: 0, h: 0 },
      libraryTip: '',
    };
  },
  computed: {
    allRecordIds() {
      const ids = [];
      const walk = (folders) => {
        for (const f of folders || []) {
          for (const r of f.records || []) ids.push(r.id);
          walk(f.children || []);
        }
      };
      walk(this.tree.folders);
      for (const r of this.tree.uncategorized || []) ids.push(r.id);
      return ids;
    },
    allSelected() {
      return this.allRecordIds.length > 0 && this.selectedIds.length === this.allRecordIds.length;
    },
    someSelected() {
      return this.selectedIds.length > 0;
    },
    marqueeStyle() {
      return {
        left: `${this.marquee.x}px`,
        top: `${this.marquee.y}px`,
        width: `${this.marquee.w}px`,
        height: `${this.marquee.h}px`,
      };
    },
    urlPlatform() {
      const text = (this.url || '').trim().toLowerCase();
      if (!text) return '';
      if (
        text.includes('xiaohongshu.com') ||
        text.includes('xhslink.com') ||
        text.includes('xhs.cn')
      ) {
        return 'xiaohongshu';
      }
      if (
        text.includes('bilibili.com') ||
        text.includes('b23.tv') ||
        text.includes('bili2233.cn') ||
        /bv[a-z0-9]{10}/i.test(text) ||
        /\bav\d+\b/i.test(text)
      ) {
        return 'bilibili';
      }
      return '';
    },
    urlPlatformLabel() {
      if (this.urlPlatform === 'xiaohongshu') return '识别：小红书笔记';
      if (this.urlPlatform === 'bilibili') return '识别：B 站视频';
      return '';
    },
    extractButtonLabel() {
      return this.urlPlatform === 'xiaohongshu' ? '提取笔记' : '提取字幕';
    },
    recordMap() {
      const map = {};
      const collect = (records) => {
        for (const r of records || []) map[r.id] = r;
      };
      const walk = (folders) => {
        for (const f of folders || []) {
          collect(f.records);
          walk(f.children);
        }
      };
      walk(this.tree.folders);
      collect(this.tree.uncategorized);
      return map;
    },
    allRecords() {
      const out = [];
      const collect = (records) => {
        for (const r of records || []) out.push(r);
      };
      const walk = (folders) => {
        for (const f of folders || []) {
          collect(f.records);
          walk(f.children);
        }
      };
      walk(this.tree.folders);
      collect(this.tree.uncategorized);
      return out;
    },
  },
  mounted() {
    this.loadSidebarWidth();
    this.loadChatWidth();
    this.loadTree();
    this._onWindowResize = () => {
      this.sidebarWidth = this.clampSidebarWidth(this.sidebarWidth);
      this.chatWidth = this.clampChatWidth(this.chatWidth);
    };
    window.addEventListener('resize', this._onWindowResize);
  },
  beforeUnmount() {
    clearTimeout(this._libraryTipTimer);
    this.stopSidebarResize();
    this.stopChatResize();
    this.stopMarquee();
    this.onRecordDragEnd();
    if (this._onWindowResize) {
      window.removeEventListener('resize', this._onWindowResize);
    }
  },
  methods: {
    clampSidebarWidth(width) {
      const max = Math.min(720, Math.floor(window.innerWidth * 0.65));
      return Math.max(240, Math.min(max, width));
    },
    loadSidebarWidth() {
      try {
        const raw = localStorage.getItem('b-subtitle-sidebar-width');
        const n = parseInt(raw, 10);
        if (!Number.isNaN(n)) this.sidebarWidth = this.clampSidebarWidth(n);
      } catch {
        /* ponytail: localStorage 不可用时用默认宽度 */
      }
    },
    startSidebarResize(event) {
      if (window.matchMedia('(max-width: 860px)').matches) return;
      event.preventDefault();
      this.resizingSidebar = true;
      this._resizeStartX = event.clientX;
      this._resizeStartWidth = this.sidebarWidth;
      document.addEventListener('mousemove', this.onSidebarResize);
      document.addEventListener('mouseup', this.stopSidebarResize);
    },
    onSidebarResize(event) {
      const delta = event.clientX - this._resizeStartX;
      this.sidebarWidth = this.clampSidebarWidth(this._resizeStartWidth + delta);
    },
    stopSidebarResize() {
      if (!this.resizingSidebar) return;
      this.resizingSidebar = false;
      document.removeEventListener('mousemove', this.onSidebarResize);
      document.removeEventListener('mouseup', this.stopSidebarResize);
      try {
        localStorage.setItem('b-subtitle-sidebar-width', String(this.sidebarWidth));
      } catch {
        /* ignore */
      }
    },
    clampChatWidth(width) {
      const max = Math.min(960, Math.floor(window.innerWidth * 0.675));
      return Math.max(280, Math.min(max, width));
    },
    loadChatWidth() {
      try {
        const raw = localStorage.getItem('b-subtitle-chat-width');
        const n = parseInt(raw, 10);
        if (!Number.isNaN(n)) this.chatWidth = this.clampChatWidth(n);
      } catch {
        /* ponytail: localStorage 不可用时用默认宽度 */
      }
    },
    startChatResize(event) {
      if (window.matchMedia('(max-width: 860px)').matches) return;
      event.preventDefault();
      this.resizingChat = true;
      this._chatResizeStartX = event.clientX;
      this._chatResizeStartWidth = this.chatWidth;
      document.addEventListener('mousemove', this.onChatResize);
      document.addEventListener('mouseup', this.stopChatResize);
    },
    onChatResize(event) {
      const delta = this._chatResizeStartX - event.clientX;
      this.chatWidth = this.clampChatWidth(this._chatResizeStartWidth + delta);
    },
    stopChatResize() {
      if (!this.resizingChat) return;
      this.resizingChat = false;
      document.removeEventListener('mousemove', this.onChatResize);
      document.removeEventListener('mouseup', this.stopChatResize);
      try {
        localStorage.setItem('b-subtitle-chat-width', String(this.chatWidth));
      } catch {
        /* ignore */
      }
    },
    isMarqueeBlockedTarget(target) {
      if (!(target instanceof Element)) return true;
      if (target.closest('button, input, label, .tree-mini, .sidebar-resizer')) return true;
      // 点在字幕行上优先走拖拽，空白区域才拉框
      if (target.closest('.tree-record')) return true;
      return false;
    },
    rectsIntersect(a, b) {
      return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
    },
    onMarqueeStart(event) {
      if (event.button !== 0 || this.marquee.active || this.draggingRecordIds.length) return;
      if (this.isMarqueeBlockedTarget(event.target)) return;
      const pane = this.$refs.treePane;
      if (!pane) return;

      const rect = pane.getBoundingClientRect();
      const startX = event.clientX - rect.left;
      const startY = event.clientY - rect.top + pane.scrollTop;

      this._marqueePane = pane;
      this._marqueeAdditive = event.ctrlKey || event.metaKey || event.shiftKey;
      this._marqueeBase = this._marqueeAdditive ? [...this.selectedIds] : [];
      if (!this._marqueeAdditive) this.selectedIds = [];

      this.marquee = {
        active: true,
        startX,
        startY,
        x: startX,
        y: startY,
        w: 0,
        h: 0,
      };

      document.addEventListener('mousemove', this.onMarqueeMove);
      document.addEventListener('mouseup', this.onMarqueeEnd);
    },
    onMarqueeMove(event) {
      if (!this.marquee.active || !this._marqueePane) return;
      const pane = this._marqueePane;
      const rect = pane.getBoundingClientRect();
      const curX = event.clientX - rect.left;
      const curY = event.clientY - rect.top + pane.scrollTop;

      const x = Math.min(this.marquee.startX, curX);
      const y = Math.min(this.marquee.startY, curY);
      const w = Math.abs(curX - this.marquee.startX);
      const h = Math.abs(curY - this.marquee.startY);
      this.marquee = { ...this.marquee, x, y, w, h };
      this.updateMarqueeSelection();
    },
    updateMarqueeSelection() {
      const pane = this._marqueePane;
      if (!pane) return;
      const box = {
        left: this.marquee.x,
        top: this.marquee.y,
        right: this.marquee.x + this.marquee.w,
        bottom: this.marquee.y + this.marquee.h,
      };
      const paneRect = pane.getBoundingClientRect();
      const scrollTop = pane.scrollTop;
      const hit = [];
      pane.querySelectorAll('.tree-record[data-record-id]').forEach((el) => {
        const r = el.getBoundingClientRect();
        const rel = {
          left: r.left - paneRect.left,
          top: r.top - paneRect.top + scrollTop,
          right: r.right - paneRect.left,
          bottom: r.bottom - paneRect.top + scrollTop,
        };
        if (this.rectsIntersect(box, rel)) {
          hit.push(el.dataset.recordId);
        }
      });
      this.selectedIds = this._marqueeAdditive
        ? [...new Set([...this._marqueeBase, ...hit])]
        : hit;
    },
    onMarqueeEnd() {
      if (!this.marquee.active) return;
      this.marquee = { ...this.marquee, active: false };
      this.stopMarquee();
    },
    stopMarquee() {
      document.removeEventListener('mousemove', this.onMarqueeMove);
      document.removeEventListener('mouseup', this.onMarqueeEnd);
      this._marqueePane = null;
    },
    onRecordDragStart({ ids = [], purpose = 'move' }) {
      this.draggingRecordIds = ids;
      this.dragPurpose = purpose;
    },
    onRecordDragEnd() {
      this.draggingRecordIds = [];
      this.dropTargetFolderId = null;
      this.dragPurpose = null;
    },
    showLibraryTip(msg) {
      this.libraryTip = msg;
      clearTimeout(this._libraryTipTimer);
      this._libraryTipTimer = setTimeout(() => {
        if (this.libraryTip === msg) this.libraryTip = '';
      }, 2000);
    },
    onFolderRefDragEmpty() {
      this.showLibraryTip('文件夹为空');
    },
    onFolderDragOver(folderId) {
      this.dropTargetFolderId = folderId;
      if (folderId && folderId !== '__uncategorized__' && !this.expandedIds.has(folderId)) {
        const next = new Set(this.expandedIds);
        next.add(folderId);
        this.expandedIds = next;
      }
    },
    onFolderDragLeave(folderId) {
      if (this.dropTargetFolderId === folderId) {
        this.dropTargetFolderId = null;
      }
    },
    async onFolderDrop(folderId) {
      if (this.dragPurpose === 'ref' || this.dragPurpose === 'folder-ref') return;
      const ids = this.draggingRecordIds.length ? this.draggingRecordIds : [...this.selectedIds];
      const targetId = folderId === '__uncategorized__' ? null : folderId;
      await this.moveRecordsToFolder(ids, targetId);
      this.onRecordDragEnd();
    },
    async moveRecordsToFolder(ids, folderId) {
      if (!ids.length) return;
      try {
        const resp = await fetch('/api/v1/subtitle/records/batch-move', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids, folder_id: folderId }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || '移动失败';
          return;
        }
        const next = new Set(this.expandedIds);
        if (folderId) next.add(folderId);
        else next.add('__uncategorized__');
        this.expandedIds = next;
        this.activeFolderId = folderId;
        await this.loadTree();
        this.selectedIds = ids.filter((id) => this.allRecordIds.includes(id));
        if (data.moved.length) {
          this.savedTip = `已移动 ${data.moved.length} 条笔记到${folderId ? '文件夹' : '未分类'}`;
          setTimeout(() => {
            if (this.savedTip.startsWith('已移动')) this.savedTip = '';
          }, 2000);
        }
      } catch (e) {
        this.error = String(e);
      }
    },
    findFolder(folders, id) {
      for (const f of folders || []) {
        if (f.id === id) return f;
        const child = this.findFolder(f.children, id);
        if (child) return child;
      }
      return null;
    },
    flattenFolderOptions(folders, depth = 0, out = []) {
      for (const f of folders || []) {
        out.push({ id: f.id, label: `${'　'.repeat(depth)}📂 ${f.name}` });
        this.flattenFolderOptions(f.children, depth + 1, out);
      }
      return out;
    },
    async loadTree() {
      try {
        const resp = await fetch('/api/v1/subtitle/tree');
        this.tree = resp.ok
          ? await resp.json()
          : { folders: [], uncategorized: [], total_count: 0 };
        this.autoExpandFoldersWithRecords();
        this.selectedIds = this.selectedIds.filter((id) => this.allRecordIds.includes(id));
      } catch {
        this.tree = { folders: [], uncategorized: [], total_count: 0 };
        this.selectedIds = [];
      }
    },
    folderRecordCount(folder) {
      let n = (folder.records || []).length;
      for (const c of folder.children || []) n += this.folderRecordCount(c);
      return n;
    },
    autoExpandFoldersWithRecords() {
      const next = new Set(this.expandedIds);
      next.add('__uncategorized__');
      const walk = (folders) => {
        for (const f of folders || []) {
          if (this.folderRecordCount(f) > 0) next.add(f.id);
          walk(f.children);
        }
      };
      walk(this.tree.folders);
      this.expandedIds = next;
    },
    toggleExpand(id) {
      const next = new Set(this.expandedIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      this.expandedIds = next;
    },
    selectFolder(folderId) {
      this.activeFolderId = folderId;
    },
    async createFolder(parentId) {
      const name = window.prompt('文件夹名称');
      if (!name || !name.trim()) return;
      try {
        const resp = await fetch('/api/v1/subtitle/folders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: name.trim(), parent_id: parentId }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.error = data.detail || '创建失败';
          return;
        }
        const next = new Set(this.expandedIds);
        if (parentId) next.add(parentId);
        this.expandedIds = next;
        this.activeFolderId = data.id;
        await this.loadTree();
      } catch (e) {
        this.error = String(e);
      }
    },
    async onFolderAction({ action, folder }) {
      if (action === 'new-child') {
        await this.createFolder(folder.id);
        return;
      }
      if (action === 'rename') {
        const name = window.prompt('重命名文件夹', folder.name);
        if (!name || !name.trim() || name.trim() === folder.name) return;
        try {
          const resp = await fetch(`/api/v1/subtitle/folders/${folder.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.trim() }),
          });
          const data = await resp.json();
          if (!resp.ok) {
            this.error = data.detail || '重命名失败';
            return;
          }
          await this.loadTree();
        } catch (e) {
          this.error = String(e);
        }
        return;
      }
      if (action === 'delete') {
        if (!window.confirm(`删除文件夹「${folder.name}」？内部笔记将移到上级或未分类。`)) return;
        try {
          const resp = await fetch(`/api/v1/subtitle/folders/${folder.id}`, {
            method: 'DELETE',
          });
          const data = await resp.json();
          if (!resp.ok) {
            this.error = data.detail || '删除失败';
            return;
          }
          if (this.activeFolderId === folder.id) this.activeFolderId = null;
          await this.loadTree();
        } catch (e) {
          this.error = String(e);
        }
      }
    },
    async batchMove() {
      if (!this.selectedIds.length) return;
      const options = [{ id: '', label: '📁 未分类' }, ...this.flattenFolderOptions(this.tree.folders)];
      const msg = options.map((o, i) => `${i}. ${o.label}`).join('\n');
      const input = window.prompt(`移动到（输入序号）:\n${msg}`, '0');
      if (input === null) return;
      const idx = parseInt(input, 10);
      if (Number.isNaN(idx) || idx < 0 || idx >= options.length) {
        this.error = '无效的文件夹序号';
        return;
      }
      const folderId = options[idx].id || null;
      await this.moveRecordsToFolder([...this.selectedIds], folderId);
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
        this.selectedIds = [...this.allRecordIds];
      }
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
        this.error = '请输入 B 站或小红书链接';
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
            folder_id: null,
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
          this.savedTip = force ? '已重新提取并保存' : '已保存到笔记库';
        }
        await this.loadTree();
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
      this.savedTip = '已加载本地笔记';
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
      if (!window.confirm('确定删除这条笔记？')) return;
      await this._deleteIds([id]);
    },
    async batchDelete() {
      if (!this.selectedIds.length) return;
      if (!window.confirm(`确定删除选中的 ${this.selectedIds.length} 条笔记？`)) return;
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
        await this.loadTree();
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
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 20px 16px 16px;
  background: #12162a;
  box-sizing: border-box;
  overflow: hidden;
}
.sidebar-resizer {
  flex-shrink: 0;
  width: 6px;
  margin: 0 -3px;
  cursor: col-resize;
  position: relative;
  z-index: 5;
  background: transparent;
  transition: background 0.15s;
}
.sidebar-resizer:hover,
.layout--resizing-sidebar .sidebar-resizer {
  background: rgba(59, 91, 219, 0.25);
}
.sidebar-resizer::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: #252b48;
}
.layout--resizing-sidebar {
  cursor: col-resize;
  user-select: none;
}
.layout--resizing-sidebar * {
  cursor: col-resize !important;
}
.layout--resizing-chat {
  cursor: col-resize;
  user-select: none;
}
.layout--resizing-chat * {
  cursor: col-resize !important;
}
.workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  height: 100vh;
}
.chat-resizer {
  flex-shrink: 0;
  width: 6px;
  margin: 0 -3px;
  cursor: col-resize;
  position: relative;
  z-index: 5;
  background: transparent;
  transition: background 0.15s;
}
.chat-resizer:hover,
.layout--resizing-chat .chat-resizer {
  background: rgba(59, 91, 219, 0.25);
}
.chat-resizer::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: #252b48;
}
.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  flex-shrink: 0;
  gap: 8px;
}
.sidebar-head-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.save-hint {
  margin: 0 0 10px;
  padding: 6px 10px;
  background: #151a2e;
  border-radius: 6px;
  color: #8b94b8;
  font-size: 0.78rem;
  flex-shrink: 0;
}
.library-tip {
  margin: -4px 0 10px;
  padding: 6px 10px;
  background: #3a1824;
  border: 1px solid #6b3040;
  border-radius: 6px;
  color: #ffb4b4;
  font-size: 0.78rem;
  flex-shrink: 0;
}
.save-target {
  margin: 0 0 10px;
  padding: 6px 10px;
  background: #151a2e;
  border-radius: 6px;
  color: #8b94b8;
  font-size: 0.78rem;
  flex-shrink: 0;
}
.save-target strong {
  color: #a8b8ff;
}
.sidebar-head h2 {
  margin: 0;
  font-size: 1rem;
}
.lib-count {
  color: #8b94b8;
  font-weight: 400;
  font-size: 0.82rem;
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
  position: relative;
}
.sidebar-scroll--marquee {
  cursor: crosshair;
  user-select: none;
}
.sidebar-scroll--dragging {
  cursor: grabbing;
}
.marquee-box {
  position: absolute;
  z-index: 20;
  border: 1px solid rgba(59, 91, 219, 0.85);
  background: rgba(59, 91, 219, 0.18);
  pointer-events: none;
  border-radius: 4px;
}
.batch-hint {
  display: block;
  margin-top: 4px;
  color: #6b7394;
  font-size: 0.72rem;
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
.main {
  flex: 1;
  min-width: 0;
  padding: 24px 20px 48px;
  overflow-y: auto;
  height: 100vh;
  box-sizing: border-box;
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
.source-badge {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #243055;
  color: #a8b8ff;
  font-size: 0.75rem;
}
.platform-tag {
  padding: 4px 10px;
  border-radius: 6px;
  background: #1c2440;
  color: #9aa3c7;
  font-size: 0.8rem;
}
.xhs-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.xhs-thumb {
  width: 88px;
  height: 88px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #252b48;
  background: #0f1220;
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
    width: 100% !important;
    height: auto;
    max-height: 42vh;
    border-bottom: 1px solid #252b48;
  }
  .sidebar-resizer {
    display: none;
  }
  .workspace {
    flex-direction: column;
    height: auto;
    min-height: 58vh;
  }
  .main {
    height: auto;
    min-height: 40vh;
  }
  .chat-resizer {
    display: none;
  }
}
</style>
