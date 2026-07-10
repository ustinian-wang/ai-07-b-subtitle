import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import LibraryTree from '../src/LibraryTree.vue';
import { ALL_FOLDER_ID, DRAG_FOLDER_MIME, UNCATEGORIZED_FOLDER_ID } from '../src/dragMime.js';
import { sampleRecords, sampleTree } from './fixtures/libraryTree.js';
import { folderMoveDragEvent } from './helpers/dragEvent.js';

function mountTree(overrides = {}) {
  return mount(LibraryTree, {
    props: {
      folders: sampleTree.folders,
      uncategorized: sampleTree.uncategorized,
      allRecordIds: ['r1', 'r2', 'r3'],
      totalCount: sampleTree.total_count,
      expandedIds: new Set([ALL_FOLDER_ID, UNCATEGORIZED_FOLDER_ID, 'f-seoul']),
      selectedIds: [],
      draggingRecordIds: [],
      draggingFolderId: null,
      dropTargetId: null,
      activeRecordId: '',
      activeFolderId: null,
      ...overrides,
    },
    global: {
      stubs: {
        TreeRecord: {
          props: ['item'],
          template: '<div class="stub-record">{{ item.id }}</div>',
        },
      },
    },
  });
}

function rowByText(wrapper, text) {
  return wrapper.findAll('.tree-folder').find((w) => w.text().includes(text));
}

describe('LibraryTree', () => {
  it('渲染全部、未分类与用户文件夹', () => {
    const wrapper = mountTree();
    expect(wrapper.text()).toContain('全部');
    expect(wrapper.text()).toContain('未分类');
    expect(wrapper.text()).toContain('首尔');
    expect(wrapper.text()).toContain('r2');
  });

  it('点击全部选中', async () => {
    const wrapper = mountTree();
    await rowByText(wrapper, '全部').trigger('click');
    expect(wrapper.emitted('select-folder')?.[0]).toEqual([ALL_FOLDER_ID]);
  });

  it('全部文件夹引用拖拽携带所有笔记 id', async () => {
    const wrapper = mountTree();
    const event = {
      dataTransfer: {
        effectAllowed: '',
        types: [],
        data: {},
        setData(type, value) {
          this.data[type] = value;
        },
        getData(type) {
          return this.data[type] || '';
        },
      },
      target: rowByText(wrapper, '全部').element,
      preventDefault() {},
    };
    event.target.closest = () => null;

    await wrapper.vm.onAllDragStart(event);
    const payload = JSON.parse(event.dataTransfer.getData(DRAG_FOLDER_MIME));
    expect(payload.record_ids).toEqual(['r1', 'r2', 'r3']);
    expect(wrapper.emitted('record-drag-start')?.[0]).toEqual([{ purpose: 'folder-ref' }]);
  });

  it('未分类为空时引用拖拽提示', async () => {
    const wrapper = mountTree({ uncategorized: [] });
    const event = {
      dataTransfer: { effectAllowed: '', types: [], setData() {}, getData: () => '' },
      target: rowByText(wrapper, '未分类').element,
      preventDefault() {},
    };
    event.target.closest = () => null;
    await wrapper.vm.onUncatDragStart(event);
    expect(wrapper.emitted('folder-ref-drag-empty')).toHaveLength(1);
  });

  it('未分类引用拖拽携带未分类笔记', async () => {
    const wrapper = mountTree();
    const event = {
      dataTransfer: {
        effectAllowed: '',
        types: [],
        data: {},
        setData(type, value) {
          this.data[type] = value;
        },
        getData(type) {
          return this.data[type] || '';
        },
      },
      target: rowByText(wrapper, '未分类').element,
      preventDefault() {},
    };
    event.target.closest = () => null;
    await wrapper.vm.onUncatDragStart(event);
    const payload = JSON.parse(event.dataTransfer.getData(DRAG_FOLDER_MIME));
    expect(payload.record_ids).toEqual([sampleRecords.r2.id]);
  });

  it('文件夹移动到全部触发 folder-drop', async () => {
    const wrapper = mountTree();
    await wrapper.vm.onAllDrop(folderMoveDragEvent('f-seoul', '首尔'));
    expect(wrapper.emitted('folder-drop')?.[0]).toEqual([ALL_FOLDER_ID]);
  });

  it('文件夹移动经过未分类不触发落点', async () => {
    const wrapper = mountTree();
    await wrapper.vm.onUncatDragOver(folderMoveDragEvent('f-seoul', '首尔'));
    expect(wrapper.emitted('folder-drag-over')).toBeUndefined();
  });

  it('笔记移动到未分类触发 folder-drop', async () => {
    const wrapper = mountTree();
    const event = {
      dataTransfer: { types: ['application/x-subtitle-ids'], effectAllowed: 'move' },
      preventDefault() {},
    };
    await wrapper.vm.onUncatDrop(event);
    expect(wrapper.emitted('folder-drop')?.[0]).toEqual([UNCATEGORIZED_FOLDER_ID]);
  });
});
