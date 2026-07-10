import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import TreeFolder from '../src/TreeFolder.vue';
import { sampleFolders } from './fixtures/libraryTree.js';
import { folderMoveDragEvent, folderRefDragEvent } from './helpers/dragEvent.js';

function mountFolder(overrides = {}) {
  return mount(TreeFolder, {
    props: {
      folder: sampleFolders[0],
      expandedIds: new Set(),
      selectedIds: [],
      draggingRecordIds: [],
      draggingFolderId: null,
      dropTargetId: null,
      activeRecordId: '',
      activeFolderId: null,
      ...overrides.props,
    },
    global: {
      stubs: {
        TreeRecord: {
          template: '<div class="stub-record" />',
        },
      },
    },
  });
}

describe('TreeFolder', () => {
  it('点击文件夹名称选中并展开', async () => {
    const wrapper = mountFolder();
    await wrapper.get('.tree-folder-name').trigger('click');
    expect(wrapper.emitted('select-folder')?.[0]).toEqual(['f-seoul']);
    expect(wrapper.emitted('toggle-expand')?.[0]).toEqual(['f-seoul']);
  });

  it('已展开时不重复 toggle-expand', async () => {
    const wrapper = mountFolder({ props: { expandedIds: new Set(['f-seoul']) } });
    await wrapper.get('.tree-folder-name').trigger('click');
    expect(wrapper.emitted('select-folder')?.[0]).toEqual(['f-seoul']);
    expect(wrapper.emitted('toggle-expand')).toBeUndefined();
  });

  it('新建子文件夹动作', async () => {
    const wrapper = mountFolder();
    await wrapper.get('[title="新建子文件夹"]').trigger('click');
    expect(wrapper.emitted('folder-action')?.[0]).toEqual([
      { action: 'new-child', folder: sampleFolders[0] },
    ]);
  });

  it('拖拽文件夹触发 folder-drag-start', async () => {
    const wrapper = mountFolder();
    const event = {
      dataTransfer: {
        effectAllowed: '',
        types: [],
        setData() {},
        getData() {
          return '';
        },
      },
      target: wrapper.get('.tree-folder').element,
      preventDefault() {},
    };
    event.target.closest = () => null;

    await wrapper.vm.onDragStart(event);
    expect(wrapper.emitted('folder-drag-start')?.[0]).toEqual([{ folderId: 'f-seoul' }]);
  });

  it('文件夹移动拖拽经过时触发 folder-drag-over', async () => {
    const wrapper = mountFolder();
    await wrapper.vm.onDragOver(folderMoveDragEvent('f-empty', '空目录'));
    expect(wrapper.emitted('folder-drag-over')?.[0]).toEqual(['f-seoul']);
  });

  it('文件夹引用拖拽经过时不触发落点', async () => {
    const wrapper = mountFolder();
    await wrapper.vm.onDragOver(folderRefDragEvent('f-empty', '空目录', ['r1']));
    expect(wrapper.emitted('folder-drag-over')).toBeUndefined();
  });

  it('文件夹移动 drop 触发 folder-drop', async () => {
    const wrapper = mountFolder();
    await wrapper.vm.onDrop(folderMoveDragEvent('f-empty', '空目录'));
    expect(wrapper.emitted('folder-drop')?.[0]).toEqual(['f-seoul']);
  });

  it('拖拽中的文件夹显示 dragging 样式', () => {
    const wrapper = mountFolder({ props: { draggingFolderId: 'f-seoul' } });
    expect(wrapper.get('.tree-folder').classes()).toContain('dragging');
  });

  it('展开后渲染子文件夹与笔记', () => {
    const wrapper = mountFolder({ props: { expandedIds: new Set(['f-seoul']) } });
    expect(wrapper.findAll('.stub-record').length).toBe(1);
    expect(wrapper.text()).toContain('江南');
  });
});
