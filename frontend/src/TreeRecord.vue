<template>
  <div
    :data-record-id="item.id"
    :class="[
      'tree-record',
      {
        active,
        selected,
        dragging: draggingIds.includes(item.id),
      },
    ]"
    :style="{ paddingLeft: `${8 + depth * 14}px` }"
    draggable="true"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
  >
    <label class="tree-record-check" @click.stop>
      <input type="checkbox" :checked="selected" @change="$emit('toggle-select')" />
    </label>
    <button type="button" class="tree-record-main" @click="$emit('open')">
      <span class="tree-record-icon">{{ item.source === 'xiaohongshu' ? '📕' : '📄' }}</span>
      <span class="tree-record-body">
        <span class="tree-record-title" :title="item.title || item.bvid || item.note_id">
          {{ item.title || item.bvid || item.note_id }}
        </span>
        <span class="tree-record-meta">
          <template v-if="item.source === 'xiaohongshu'">
            小红书 · {{ item.note_id || '—' }}
            <span v-if="item.lan_doc"> · {{ item.lan_doc }}</span>
          </template>
          <template v-else>
            {{ item.bvid }} · P{{ item.page }}
            <span v-if="item.lan_doc"> · {{ item.lan_doc }}</span>
            · {{ item.line_count }} 条
          </template>
        </span>
      </span>
    </button>
    <button type="button" class="tree-record-del" title="删除" @click.stop="$emit('remove')">×</button>
  </div>
</template>

<script>
export default {
  name: 'TreeRecord',
  props: {
    item: { type: Object, required: true },
    depth: { type: Number, default: 0 },
    selected: { type: Boolean, default: false },
    active: { type: Boolean, default: false },
    selectedIds: { type: Array, default: () => [] },
    draggingIds: { type: Array, default: () => [] },
  },
  emits: ['open', 'toggle-select', 'remove', 'drag-start', 'drag-end'],
  methods: {
    dragIds() {
      if (this.selectedIds.includes(this.item.id) && this.selectedIds.length) {
        return [...this.selectedIds];
      }
      return [this.item.id];
    },
    onDragStart(event) {
      if (event.target.closest('input, .tree-record-del')) {
        event.preventDefault();
        return;
      }
      const ids = this.dragIds();
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('application/x-subtitle-ids', JSON.stringify(ids));
      event.dataTransfer.setData('text/plain', `${ids.length} 条字幕`);
      this.$emit('drag-start', { ids });
    },
    onDragEnd() {
      this.$emit('drag-end');
    },
  },
};
</script>

<style scoped>
.tree-record {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  padding: 4px 8px 4px 0;
  margin: 2px 0;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: grab;
}
.tree-record:active {
  cursor: grabbing;
}
.tree-record:hover {
  background: #171d34;
  border-color: #252b48;
}
.tree-record.active {
  border-color: #3b5bdb;
  background: #171d34;
}
.tree-record.selected {
  border-color: #4a6cf0;
  background: #1a2240;
}
.tree-record.dragging {
  opacity: 0.45;
}
.tree-record-check {
  flex-shrink: 0;
  padding: 4px 0 0 4px;
  cursor: pointer;
}
.tree-record-main {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: 6px;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: inherit;
}
.tree-record-icon {
  flex-shrink: 0;
  font-size: 0.8rem;
  padding-top: 2px;
}
.tree-record-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.tree-record-title {
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.tree-record-meta {
  color: #7a84a8;
  font-size: 0.68rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-record-del {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  margin-top: 2px;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #8b94b8;
  font-size: 1rem;
  cursor: pointer;
  opacity: 0;
}
.tree-record:hover .tree-record-del {
  opacity: 1;
}
.tree-record-del:hover {
  background: #3a1824;
  color: #ffb4b4;
}
</style>
