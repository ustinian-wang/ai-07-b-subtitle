import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import TreeRecord from '../src/TreeRecord.vue';
import { DRAG_RECORD_MIME } from '../src/dragMime.js';
import { sampleRecords } from './fixtures/libraryTree.js';
import { recordDragEvent } from './helpers/dragEvent.js';

describe('TreeRecord', () => {
  const baseProps = {
    item: sampleRecords.r1,
    selectedIds: [],
    draggingIds: [],
  };

  it('点击主区域打开笔记', async () => {
    const wrapper = mount(TreeRecord, { props: baseProps });
    await wrapper.get('.tree-record-main').trigger('click');
    expect(wrapper.emitted('open')).toHaveLength(1);
  });

  it('勾选切换选中', async () => {
    const wrapper = mount(TreeRecord, { props: baseProps });
    await wrapper.get('input[type="checkbox"]').setValue(true);
    expect(wrapper.emitted('toggle-select')).toHaveLength(1);
  });

  it('拖拽单条笔记时携带自身 id', async () => {
    const wrapper = mount(TreeRecord, { props: baseProps });
    const event = recordDragEvent(['r1']);
    await wrapper.vm.onDragStart(event);

    expect(wrapper.emitted('drag-start')?.[0]).toEqual([{ ids: ['r1'], purpose: 'move' }]);
    expect(event.dataTransfer.getData(DRAG_RECORD_MIME)).toBe(JSON.stringify(['r1']));
  });

  it('多选时拖拽携带全部选中 id', async () => {
    const wrapper = mount(TreeRecord, {
      props: {
        ...baseProps,
        item: sampleRecords.r2,
        selected: true,
        selectedIds: ['r2', 'r3'],
      },
    });
    const event = recordDragEvent(['r2', 'r3']);
    await wrapper.vm.onDragStart(event);

    expect(wrapper.emitted('drag-start')?.[0]).toEqual([{ ids: ['r2', 'r3'], purpose: 'move' }]);
  });

  it('从操作按钮区域拖拽不触发移动', async () => {
    const wrapper = mount(TreeRecord, { props: baseProps });
    const delBtn = wrapper.get('.tree-record-del').element;
    const event = recordDragEvent(['r1']);
    event.target = delBtn;
    delBtn.closest = (selector) => (selector.includes('tree-record-del') ? delBtn : null);
    event.preventDefault = () => {};

    await wrapper.vm.onDragStart(event);
    expect(wrapper.emitted('drag-start')).toBeUndefined();
  });
});
