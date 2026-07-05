<template>
  <ul class="tree-root">
    <li class="tree-branch tree-branch--virtual">
      <div
        :class="[
          'tree-folder',
          {
            active: activeFolderId === null && !activeRecordId,
            'drop-target': dropTargetId === '__uncategorized__',
          },
        ]"
        @click="$emit('select-folder', null)"
        @dragover.prevent="onUncatDragOver"
        @dragenter.prevent="onUncatDragOver"
        @dragleave="onUncatDragLeave"
        @drop.prevent="onUncatDrop"
      >
        <button
          type="button"
          class="tree-toggle"
          :aria-expanded="expandedIds.has('__uncategorized__')"
          @click.stop="$emit('toggle-expand', '__uncategorized__')"
        >
          {{ expandedIds.has('__uncategorized__') ? '▾' : '▸' }}
        </button>
        <span class="tree-folder-icon">📁</span>
        <span class="tree-folder-name">未分类</span>
        <span class="tree-folder-count">{{ uncategorized.length }}</span>
      </div>
      <ul v-if="expandedIds.has('__uncategorized__')" class="tree-children">
        <li v-for="item in uncategorized" :key="item.id">
          <TreeRecord
            :item="item"
            :depth="1"
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
        <li v-if="!uncategorized.length" class="tree-empty">暂无记录 · 可拖入字幕</li>
      </ul>
    </li>

    <li v-for="folder in folders" :key="folder.id" class="tree-branch">
      <TreeFolder
        :folder="folder"
        :depth="0"
        :expanded-ids="expandedIds"
        :selected-ids="selectedIds"
        :dragging-record-ids="draggingRecordIds"
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
        @folder-drag-over="$emit('folder-drag-over', $event)"
        @folder-drag-leave="$emit('folder-drag-leave', $event)"
        @folder-drop="$emit('folder-drop', $event)"
      />
    </li>
  </ul>
</template>

<script>
import TreeFolder from './TreeFolder.vue';
import TreeRecord from './TreeRecord.vue';

export default {
  name: 'LibraryTree',
  components: { TreeFolder, TreeRecord },
  props: {
    folders: { type: Array, default: () => [] },
    uncategorized: { type: Array, default: () => [] },
    expandedIds: { type: Object, required: true },
    selectedIds: { type: Array, default: () => [] },
    draggingRecordIds: { type: Array, default: () => [] },
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
    'folder-drag-over',
    'folder-drag-leave',
    'folder-drop',
  ],
  methods: {
    onUncatDragOver() {
      this.$emit('folder-drag-over', '__uncategorized__');
    },
    onUncatDragLeave(event) {
      if (event.currentTarget.contains(event.relatedTarget)) return;
      this.$emit('folder-drag-leave', '__uncategorized__');
    },
    onUncatDrop() {
      this.$emit('folder-drop', '__uncategorized__');
    },
  },
};
</script>

<style scoped>
.tree-root {
  list-style: none;
  margin: 0;
  padding: 0;
  min-height: 100%;
  padding-bottom: 48px;
}
.tree-branch {
  margin: 0;
  padding: 0;
}
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
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
  border: 1px solid transparent;
  transition: background 0.12s, border-color 0.12s;
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
</style>
