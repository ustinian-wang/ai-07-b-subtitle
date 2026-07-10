<template>
  <div>
    <div
      :class="[
        'tree-folder',
        {
          active: activeFolderId === folder.id,
          'drop-target': dropTargetId === folder.id,
          dragging: draggingFolderId === folder.id,
        },
      ]"
      :style="{ paddingLeft: `${8 + depth * 14}px` }"
      draggable="true"
      @dragstart="onDragStart"
      @dragend="onDragEnd"
      @dragover.prevent="onDragOver"
      @dragenter.prevent="onDragEnter"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <button
        type="button"
        class="tree-toggle"
        :aria-expanded="expandedIds.has(folder.id)"
        @click.stop="$emit('toggle-expand', folder.id)"
      >
        {{ expandedIds.has(folder.id) ? '▾' : '▸' }}
      </button>
      <span class="tree-folder-icon" @click="onSelect">📂</span>
      <span class="tree-folder-name" @click="onSelect">{{ folder.name }}</span>
      <span class="tree-folder-count">{{ folderCount }}</span>
      <div class="tree-folder-actions" @click.stop>
        <button type="button" class="tree-mini" title="新建子文件夹" @click="onAction('new-child')">+</button>
        <button type="button" class="tree-mini" title="重命名" @click="onAction('rename')">✎</button>
        <button type="button" class="tree-mini danger" title="删除" @click="onAction('delete')">×</button>
      </div>
    </div>

    <ul v-if="expandedIds.has(folder.id)" class="tree-children">
      <li v-for="child in folder.children || []" :key="child.id">
        <TreeFolder
          :folder="child"
          :depth="depth + 1"
          :expanded-ids="expandedIds"
          :selected-ids="selectedIds"
          :dragging-record-ids="draggingRecordIds"
          :dragging-folder-id="draggingFolderId"
          :drop-target-id="dropTargetId"
          :active-record-id="activeRecordId"
          :active-folder-id="activeFolderId"
          @toggle-expand="$emit('toggle-expand', $event)"
          @select-folder="$emit('select-folder', $event)"
          @folder-action="$emit('folder-action', $event)"
          @open-record="$emit('open-record', $event)"
          @toggle-select="$emit('toggle-select', $event)"
          @remove-record="$emit('remove-record', $event)"
          @record-drag-start="$emit('record-drag-start', $event)"
          @record-drag-end="$emit('record-drag-end', $event)"
          @folder-drag-start="$emit('folder-drag-start', $event)"
          @folder-drag-over="$emit('folder-drag-over', $event)"
          @folder-drag-leave="$emit('folder-drag-leave', $event)"
          @folder-drop="$emit('folder-drop', $event)"
          @folder-ref-drag-empty="$emit('folder-ref-drag-empty')"
        />
      </li>
      <li v-for="item in folder.records || []" :key="item.id">
        <TreeRecord
          :item="item"
          :depth="depth + 1"
          :selected="selectedIds.includes(item.id)"
          :selected-ids="selectedIds"
          :dragging-ids="draggingRecordIds"
          :active="activeRecordId === item.id"
          @open="$emit('open-record', item.id)"
          @toggle-select="$emit('toggle-select', item.id)"
          @remove="$emit('remove-record', item.id)"
          @drag-start="$emit('record-drag-start', $event)"
          @drag-end="$emit('record-drag-end', $event)"
        />
      </li>
      <li v-if="!(folder.records || []).length && !(folder.children || []).length" class="tree-empty">
        空文件夹 · 可拖入笔记或子文件夹
      </li>
    </ul>
  </div>
</template>

<script>
import TreeRecord from './TreeRecord.vue';
import { DRAG_FOLDER_MOVE_MIME, isFolderRefDrag } from './dragMime.js';

export default {
  name: 'TreeFolder',
  components: { TreeRecord },
  props: {
    folder: { type: Object, required: true },
    depth: { type: Number, default: 0 },
    expandedIds: { type: Object, required: true },
    selectedIds: { type: Array, default: () => [] },
    draggingRecordIds: { type: Array, default: () => [] },
    draggingFolderId: { type: String, default: null },
    dropTargetId: { type: String, default: null },
    activeRecordId: { type: String, default: '' },
    activeFolderId: { type: String, default: null },
  },
  emits: [
    'toggle-expand',
    'select-folder',
    'folder-action',
    'open-record',
    'toggle-select',
    'remove-record',
    'record-drag-start',
    'record-drag-end',
    'folder-drag-start',
    'folder-drag-over',
    'folder-drag-leave',
    'folder-drop',
    'folder-ref-drag-empty',
  ],
  computed: {
    folderCount() {
      const countRecords = (node) => {
        let n = (node.records || []).length;
        for (const c of node.children || []) n += countRecords(c);
        return n;
      };
      return countRecords(this.folder);
    },
  },
  methods: {
    onSelect() {
      this.$emit('select-folder', this.folder.id);
      if (!this.expandedIds.has(this.folder.id)) {
        this.$emit('toggle-expand', this.folder.id);
      }
    },
    onAction(action) {
      this.$emit('folder-action', { action, folder: this.folder });
    },
    onDragStart(event) {
      if (event.target.closest('.tree-toggle, .tree-folder-actions, .tree-mini')) {
        event.preventDefault();
        return;
      }
      const payload = {
        folder_id: this.folder.id,
        name: this.folder.name,
      };
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData(DRAG_FOLDER_MOVE_MIME, JSON.stringify(payload));
      event.dataTransfer.setData('text/plain', this.folder.name);
      this.$emit('folder-drag-start', { folderId: this.folder.id });
    },
    onDragEnd() {
      this.$emit('record-drag-end');
    },
    onDragOver(event) {
      if (isFolderRefDrag(event)) return;
      this.$emit('folder-drag-over', this.folder.id);
    },
    onDragEnter(event) {
      if (isFolderRefDrag(event)) return;
      this.$emit('folder-drag-over', this.folder.id);
    },
    onDragLeave(event) {
      if (event.currentTarget.contains(event.relatedTarget)) return;
      this.$emit('folder-drag-leave', this.folder.id);
    },
    onDrop(event) {
      if (isFolderRefDrag(event)) return;
      this.$emit('folder-drop', this.folder.id);
    },
  },
};
</script>

<style scoped>
.tree-children {
  list-style: none;
  margin: 0;
  padding: 0;
}
.tree-empty {
  padding: 6px 12px 6px 36px;
  color: #6b7394;
  font-size: 0.78rem;
}
.tree-folder {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 6px;
  padding-bottom: 6px;
  padding-right: 8px;
  border-radius: 8px;
  cursor: grab;
  user-select: none;
  border: 1px solid transparent;
  transition: background 0.12s, border-color 0.12s;
}
.tree-folder:active {
  cursor: grabbing;
}
.tree-folder:hover {
  background: #1a2038;
}
.tree-folder.active {
  background: #243055;
}
.tree-folder.drop-target {
  background: rgba(59, 91, 219, 0.22);
  border-color: #3b5bdb;
  box-shadow: inset 0 0 0 1px rgba(59, 91, 219, 0.35);
}
.tree-folder.dragging {
  opacity: 0.45;
}
.tree-toggle {
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: transparent;
  color: #8b94b8;
  font-size: 0.75rem;
  cursor: pointer;
  flex-shrink: 0;
}
.tree-folder-icon {
  flex-shrink: 0;
  font-size: 0.85rem;
}
.tree-folder-name {
  flex: 1;
  min-width: 0;
  font-size: 0.86rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-folder-count {
  flex-shrink: 0;
  padding: 1px 6px;
  background: #1c2440;
  border-radius: 10px;
  color: #8b94b8;
  font-size: 0.68rem;
}
.tree-folder-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}
.tree-folder:hover .tree-folder-actions {
  opacity: 1;
}
.tree-mini {
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: #1c2440;
  color: #b8c0e0;
  font-size: 0.72rem;
  cursor: pointer;
  line-height: 1;
}
.tree-mini:hover {
  background: #2a3358;
}
.tree-mini.danger:hover {
  background: #3a1824;
  color: #ffb4b4;
}
</style>
