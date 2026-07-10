<template>
  <Teleport to="body">
    <div v-if="visible" class="cfd-overlay" @mousedown.self="onCancel">
      <div class="cfd-dialog" role="dialog" aria-labelledby="cfd-title" aria-modal="true">
        <header class="cfd-head">
          <h3 id="cfd-title">新建文件夹</h3>
          <button type="button" class="cfd-close" aria-label="关闭" @click="onCancel">×</button>
        </header>

        <div class="cfd-body">
          <p class="cfd-location">
            <span class="cfd-location-label">将添加到</span>
            <span class="cfd-location-path">{{ selectedParentPath }}</span>
          </p>

          <label class="cfd-label" for="cfd-parent">父级目录</label>
          <select id="cfd-parent" v-model="parentId" class="cfd-select">
            <option v-for="opt in parentOptions" :key="opt.id || '__root__'" :value="opt.id">
              {{ opt.label }}
            </option>
          </select>

          <label class="cfd-label" for="cfd-name">文件夹名称</label>
          <input
            id="cfd-name"
            ref="nameInput"
            v-model="name"
            class="cfd-input"
            type="text"
            maxlength="80"
            placeholder="输入名称"
            @keydown.enter.prevent="onSubmit"
            @keydown.esc.prevent="onCancel"
          />
          <p v-if="displayError" class="cfd-error">{{ displayError }}</p>
        </div>

        <footer class="cfd-foot">
          <button type="button" class="cfd-btn" @click="onCancel">取消</button>
          <button type="button" class="cfd-btn cfd-btn--primary" :disabled="submitting" @click="onSubmit">
            {{ submitting ? '创建中…' : '创建' }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<script>
const ROOT_PARENT_ID = '';

export default {
  name: 'CreateFolderDialog',
  props: {
    visible: { type: Boolean, default: false },
    folders: { type: Array, default: () => [] },
    initialParentId: { type: String, default: null },
    submitting: { type: Boolean, default: false },
    externalError: { type: String, default: '' },
  },
  emits: ['close', 'submit'],
  data() {
    return {
      parentId: ROOT_PARENT_ID,
      name: '',
      error: '',
    };
  },
  computed: {
    parentOptions() {
      const out = [{ id: ROOT_PARENT_ID, label: '📁 根目录（全部下）', path: '全部' }];
      const walk = (items, depth = 0, path = '全部') => {
        for (const f of items || []) {
          const nextPath = `${path} / ${f.name}`;
          out.push({
            id: f.id,
            label: `${'　'.repeat(depth)}📂 ${f.name}`,
            path: nextPath,
          });
          walk(f.children, depth + 1, nextPath);
        }
      };
      walk(this.folders);
      return out;
    },
    parentOptionMap() {
      const map = {};
      for (const opt of this.parentOptions) {
        map[opt.id || ROOT_PARENT_ID] = opt;
      }
      return map;
    },
    selectedParentPath() {
      const key = this.parentId || ROOT_PARENT_ID;
      return this.parentOptionMap[key]?.path || '全部';
    },
    displayError() {
      return this.error || this.externalError;
    },
  },
  watch: {
    visible(open) {
      if (!open) return;
      this.resetForm();
      this.$nextTick(() => {
        this.$refs.nameInput?.focus();
      });
    },
    initialParentId() {
      if (this.visible) this.syncParentId();
    },
  },
  methods: {
    syncParentId() {
      const id = this.initialParentId || ROOT_PARENT_ID;
      const exists = this.parentOptionMap[id];
      this.parentId = exists ? id : ROOT_PARENT_ID;
    },
    resetForm() {
      this.name = '';
      this.error = '';
      this.syncParentId();
    },
    onCancel() {
      if (this.submitting) return;
      this.$emit('close');
    },
    onSubmit() {
      const trimmed = (this.name || '').trim();
      if (!trimmed) {
        this.error = '请输入文件夹名称';
        this.$refs.nameInput?.focus();
        return;
      }
      this.error = '';
      const parentId = this.parentId || null;
      this.$emit('submit', { name: trimmed, parentId });
    },
  },
};
</script>

<style scoped>
.cfd-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(8, 10, 20, 0.72);
  backdrop-filter: blur(2px);
}
.cfd-dialog {
  width: min(420px, 100%);
  background: #151a2e;
  border: 1px solid #2a3358;
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.45);
}
.cfd-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid #222a48;
}
.cfd-head h3 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}
.cfd-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #9aa3c7;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}
.cfd-close:hover {
  background: #1c2440;
  color: #e8ecff;
}
.cfd-body {
  padding: 14px 16px 6px;
}
.cfd-location {
  margin: 0 0 14px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #1a2038;
  border: 1px solid #2a3358;
  font-size: 0.88rem;
  line-height: 1.45;
}
.cfd-location-label {
  display: block;
  margin-bottom: 4px;
  color: #8b94b8;
  font-size: 0.78rem;
}
.cfd-location-path {
  color: #c8d0f0;
  font-weight: 600;
  word-break: break-word;
}
.cfd-label {
  display: block;
  margin: 0 0 6px;
  color: #b8c0e0;
  font-size: 0.88rem;
}
.cfd-select,
.cfd-input {
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid #2a3358;
  border-radius: 8px;
  background: #0f1220;
  color: #e8ecff;
  font-size: 0.95rem;
}
.cfd-select {
  cursor: pointer;
}
.cfd-input:focus,
.cfd-select:focus {
  outline: none;
  border-color: #3b5bdb;
  box-shadow: 0 0 0 2px rgba(59, 91, 219, 0.25);
}
.cfd-error {
  margin: -4px 0 8px;
  color: #ff8a8a;
  font-size: 0.85rem;
}
.cfd-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px 14px;
}
.cfd-btn {
  padding: 8px 16px;
  border: 1px solid #3d4a7a;
  border-radius: 8px;
  background: #1c2440;
  color: #e8ecff;
  font-size: 0.92rem;
  cursor: pointer;
}
.cfd-btn--primary {
  background: #3b5bdb;
  border-color: #3b5bdb;
}
.cfd-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
