<template>
  <ul class="tree-root">
    <li class="tree-branch tree-branch--virtual">
      <div
        :class="[
          'tree-folder',
          {
            active: activeFolderId === ALL_FOLDER_ID,
            'drop-target': dropTargetId === ALL_FOLDER_ID,
          },
        ]"
        draggable="true"
        @click="$emit('select-folder', ALL_FOLDER_ID)"
        @dragstart="onAllDragStart"
        @dragend="onAllDragEnd"
        @dragover.prevent="onAllDragOver"
        @dragenter.prevent="onAllDragOver"
        @dragleave="onAllDragLeave"
        @drop.prevent="onAllDrop"
      >
        <button
          type="button"
          class="tree-toggle"
          :aria-expanded="expandedIds.has(ALL_FOLDER_ID)"
          @click.stop="$emit('toggle-expand', ALL_FOLDER_ID)"
        >
          {{ expandedIds.has(ALL_FOLDER_ID) ? '▾' : '▸' }}
        </button>
        <span class="tree-folder-icon">🗂️</span>
        <span class="tree-folder-name">{{ ALL_FOLDER_NAME }}</span>
        <span class="tree-folder-system" title="系统分类，包含所有笔记">系统</span>
        <span class="tree-folder-count">{{ totalCount }}</span>
      </div>

      <ul v-if="expandedIds.has(ALL_FOLDER_ID)" class="tree-children tree-children--nested">
        <li class="tree-branch tree-branch--virtual">
          <div
            :class="[
              'tree-folder',
              'tree-folder--nested',
              {
                active: activeFolderId === null && !activeRecordId,
                'drop-target': dropTargetId === UNCATEGORIZED_FOLDER_ID,
              },
            ]"
            draggable="true"
            @click="$emit('select-folder', null)"
            @dragstart="onUncatDragStart"
            @dragend="onUncatDragEnd"
            @dragover.prevent="onUncatDragOver"
            @dragenter.prevent="onUncatDragOver"
            @dragleave="onUncatDragLeave"
            @drop.prevent="onUncatDrop"
          >
            <button
              type="button"
              class="tree-toggle"
              :aria-expanded="expandedIds.has(UNCATEGORIZED_FOLDER_ID)"
              @click.stop="$emit('toggle-expand', UNCATEGORIZED_FOLDER_ID)"
            >
              {{ expandedIds.has(UNCATEGORIZED_FOLDER_ID) ? '▾' : '▸' }}
            </button>
            <span class="tree-folder-icon">📁</span>
            <span class="tree-folder-name">未分类</span>
            <span class="tree-folder-system" title="系统分类，不可删除">系统</span>
            <span class="tree-folder-count">{{ uncategorized.length }}</span>
          </div>
          <ul v-if="expandedIds.has(UNCATEGORIZED_FOLDER_ID)" class="tree-children">
            <li v-for="item in uncategorized" :key="item.id">
              <TreeRecord
                :item="item"
                :depth="2"
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
            <li v-if="!uncategorized.length" class="tree-empty">暂无笔记 · 可拖入笔记</li>
          </ul>
        </li>

        <li v-for="folder in folders" :key="folder.id" class="tree-branch">
          <TreeFolder
            :folder="folder"
            :depth="1"
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
      </ul>
    </li>
  </ul>
</template>

<script>
import TreeFolder from './TreeFolder.vue';
import TreeRecord from './TreeRecord.vue';
import {
  ALL_FOLDER_ID,
  ALL_FOLDER_NAME,
  DRAG_FOLDER_MIME,
  UNCATEGORIZED_FOLDER_ID,
  isFolderMoveDrag,
  isFolderRefDrag,
} from './dragMime.js';

export default {
  name: 'LibraryTree',
  components: { TreeFolder, TreeRecord },
  props: {
    folders: { type: Array, default: () => [] },
    uncategorized: { type: Array, default: () => [] },
    allRecordIds: { type: Array, default: () => [] },
    totalCount: { type: Number, default: 0 },
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
  data() {
    return {
      ALL_FOLDER_ID,
      ALL_FOLDER_NAME,
      UNCATEGORIZED_FOLDER_ID,
    };
  },
  methods: {
    isRefDrag(event) {
      return isFolderRefDrag(event);
    },
    onAllDragOver(event) {
      if (!isFolderMoveDrag(event)) return;
      this.$emit('folder-drag-over', ALL_FOLDER_ID);
    },
    onAllDragLeave(event) {
      if (event.currentTarget.contains(event.relatedTarget)) return;
      this.$emit('folder-drag-leave', ALL_FOLDER_ID);
    },
    onAllDrop(event) {
      if (!isFolderMoveDrag(event)) return;
      this.$emit('folder-drop', ALL_FOLDER_ID);
    },
    folderRefPayload(folderId, name, recordIds) {
      return {
        folder_id: folderId,
        name,
        record_ids: recordIds,
        record_count: recordIds.length,
      };
    },
    onAllDragStart(event) {
      if (event.target.closest('.tree-toggle')) {
        event.preventDefault();
        return;
      }
      const recordIds = [...this.allRecordIds];
      if (!recordIds.length) {
        event.preventDefault();
        this.$emit('folder-ref-drag-empty');
        return;
      }
      const payload = this.folderRefPayload(ALL_FOLDER_ID, ALL_FOLDER_NAME, recordIds);
      event.dataTransfer.effectAllowed = 'copy';
      event.dataTransfer.setData(DRAG_FOLDER_MIME, JSON.stringify(payload));
      event.dataTransfer.setData('text/plain', `${ALL_FOLDER_NAME} · ${recordIds.length} 条笔记`);
      this.$emit('record-drag-start', { purpose: 'folder-ref' });
    },
    onAllDragEnd() {
      this.$emit('record-drag-end');
    },
    onUncatDragStart(event) {
      if (event.target.closest('.tree-toggle')) {
        event.preventDefault();
        return;
      }
      const recordIds = this.uncategorized.map((r) => r.id);
      if (!recordIds.length) {
        event.preventDefault();
        this.$emit('folder-ref-drag-empty');
        return;
      }
      const payload = this.folderRefPayload(UNCATEGORIZED_FOLDER_ID, '未分类', recordIds);
      event.dataTransfer.effectAllowed = 'copy';
      event.dataTransfer.setData(DRAG_FOLDER_MIME, JSON.stringify(payload));
      event.dataTransfer.setData('text/plain', `未分类 · ${recordIds.length} 条笔记`);
      this.$emit('record-drag-start', { purpose: 'folder-ref' });
    },
    onUncatDragEnd() {
      this.$emit('record-drag-end');
    },
    onUncatDragOver(event) {
      if (this.isRefDrag(event) || isFolderMoveDrag(event)) return;
      this.$emit('folder-drag-over', UNCATEGORIZED_FOLDER_ID);
    },
    onUncatDragLeave(event) {
      if (event.currentTarget.contains(event.relatedTarget)) return;
      this.$emit('folder-drag-leave', UNCATEGORIZED_FOLDER_ID);
    },
    onUncatDrop(event) {
      if (this.isRefDrag(event) || isFolderMoveDrag(event)) return;
      this.$emit('folder-drop', UNCATEGORIZED_FOLDER_ID);
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
.tree-children--nested {
  padding-left: 4px;
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
  cursor: grab;
  user-select: none;
  border: 1px solid transparent;
  transition: background 0.12s, border-color 0.12s;
}
.tree-folder--nested {
  padding-left: 22px;
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
.tree-folder-system {
  flex-shrink: 0;
  padding: 1px 5px;
  border-radius: 4px;
  background: #243055;
  color: #8ea4ff;
  font-size: 0.58rem;
  font-weight: 600;
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
