import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import CreateFolderDialog from '../src/CreateFolderDialog.vue';
import { sampleFolders } from './fixtures/libraryTree.js';

const teleportStub = { global: { stubs: { Teleport: true } } };

describe('CreateFolderDialog', () => {
  it('隐藏时不渲染弹窗', () => {
    const wrapper = mount(CreateFolderDialog, {
      props: { visible: false, folders: sampleFolders },
      ...teleportStub,
    });
    expect(wrapper.find('.cfd-dialog').exists()).toBe(false);
  });

  it('显示当前父级路径并支持切换', async () => {
    const wrapper = mount(CreateFolderDialog, {
      props: {
        visible: false,
        folders: sampleFolders,
        initialParentId: 'f-seoul',
      },
      ...teleportStub,
    });
    await wrapper.setProps({ visible: true });

    expect(wrapper.find('.cfd-location-path').text()).toBe('全部 / 首尔');

    await wrapper.get('#cfd-parent').setValue('f-gangnam');
    expect(wrapper.find('.cfd-location-path').text()).toBe('全部 / 首尔 / 江南');
  });

  it('空名称提交显示错误', async () => {
    const wrapper = mount(CreateFolderDialog, {
      props: { visible: true, folders: sampleFolders },
      ...teleportStub,
    });

    await wrapper.get('.cfd-btn--primary').trigger('click');
    expect(wrapper.find('.cfd-error').text()).toBe('请输入文件夹名称');
    expect(wrapper.emitted('submit')).toBeUndefined();
  });

  it('提交时 emit name 与 parentId', async () => {
    const wrapper = mount(CreateFolderDialog, {
      props: {
        visible: false,
        folders: sampleFolders,
        initialParentId: 'f-seoul',
      },
      ...teleportStub,
    });
    await wrapper.setProps({ visible: true });

    await wrapper.get('#cfd-name').setValue(' 新目录 ');
    await wrapper.get('.cfd-btn--primary').trigger('click');

    expect(wrapper.emitted('submit')?.[0]).toEqual([{ name: '新目录', parentId: 'f-seoul' }]);
  });

  it('展示外部错误信息', () => {
    const wrapper = mount(CreateFolderDialog, {
      props: {
        visible: true,
        folders: sampleFolders,
        externalError: '名称已存在',
      },
      ...teleportStub,
    });
    expect(wrapper.find('.cfd-error').text()).toBe('名称已存在');
  });

  it('取消时 emit close', async () => {
    const wrapper = mount(CreateFolderDialog, {
      props: { visible: true, folders: sampleFolders },
      ...teleportStub,
    });
    await wrapper.get('.cfd-close').trigger('click');
    expect(wrapper.emitted('close')).toHaveLength(1);
  });
});
