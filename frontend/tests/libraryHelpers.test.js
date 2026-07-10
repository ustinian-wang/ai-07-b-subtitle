import { describe, expect, it, beforeEach } from 'vitest';
import {
  ALL_FOLDER_ID,
  UNCATEGORIZED_FOLDER_ID,
} from '../src/dragMime.js';
import {
  EXPANDED_IDS_STORAGE_KEY,
  autoExpandFoldersWithRecords,
  canDropFolderOn,
  collectDescendantFolderIds,
  findFolder,
  flattenFolderOptions,
  folderRecordCount,
  restoreExpandedIds,
  sanitizeExpandedIds,
  saveExpandedIds,
  resolveFolderDropParent,
  resolveRecordDropFolderId,
} from '../src/libraryHelpers.js';
import { sampleFolders, sampleTree } from './fixtures/libraryTree.js';

describe('libraryHelpers', () => {
  describe('findFolder / folderRecordCount', () => {
    it('按 id 查找嵌套文件夹', () => {
      expect(findFolder(sampleFolders, 'f-gangnam')?.name).toBe('江南');
      expect(findFolder(sampleFolders, 'missing')).toBeNull();
    });

    it('统计文件夹及子级笔记数量', () => {
      expect(folderRecordCount(sampleFolders[0])).toBe(2);
      expect(folderRecordCount(sampleFolders[1])).toBe(0);
    });
  });

  describe('flattenFolderOptions', () => {
    it('生成带缩进的批量移动选项', () => {
      const options = flattenFolderOptions(sampleFolders);
      expect(options).toHaveLength(3);
      expect(options[0]).toEqual({ id: 'f-seoul', label: '📂 首尔' });
      expect(options[1].id).toBe('f-gangnam');
      expect(options[1].label).toContain('江南');
    });
  });

  describe('canDropFolderOn', () => {
    const base = {
      draggingFolderId: 'f-seoul',
      dragPurpose: 'folder-move',
      folders: sampleFolders,
    };

    it('允许拖到同级文件夹', () => {
      expect(canDropFolderOn({ ...base, folderId: 'f-empty' })).toBe(true);
    });

    it('允许拖到全部（根目录）', () => {
      expect(canDropFolderOn({ ...base, folderId: ALL_FOLDER_ID })).toBe(true);
      expect(resolveFolderDropParent(ALL_FOLDER_ID)).toBeNull();
    });

    it('禁止拖到自身、子文件夹、未分类', () => {
      expect(canDropFolderOn({ ...base, folderId: 'f-seoul' })).toBe(false);
      expect(canDropFolderOn({ ...base, folderId: 'f-gangnam' })).toBe(false);
      expect(canDropFolderOn({ ...base, folderId: UNCATEGORIZED_FOLDER_ID })).toBe(false);
      expect(resolveRecordDropFolderId(UNCATEGORIZED_FOLDER_ID)).toBeNull();
    });

    it('非 folder-move 意图不可落点', () => {
      expect(
        canDropFolderOn({ ...base, folderId: 'f-empty', dragPurpose: 'move' }),
      ).toBe(false);
    });
  });

  describe('collectDescendantFolderIds', () => {
    it('收集全部子孙文件夹 id', () => {
      const ids = collectDescendantFolderIds(sampleFolders, 'f-seoul');
      expect([...ids]).toEqual(['f-gangnam']);
    });
  });

  describe('展开状态持久化', () => {
    let storage;

    beforeEach(() => {
      storage = {
        store: {},
        getItem(key) {
          return this.store[key] ?? null;
        },
        setItem(key, value) {
          this.store[key] = value;
        },
      };
    });

    it('保存并恢复展开 id', () => {
      const expanded = new Set([ALL_FOLDER_ID, 'f-seoul']);
      expect(saveExpandedIds(expanded, storage)).toBe(true);
      const restored = restoreExpandedIds(storage);
      expect(restored.fromStorage).toBe(true);
      expect([...restored.expandedIds]).toEqual([ALL_FOLDER_ID, 'f-seoul']);
      expect(storage.store[EXPANDED_IDS_STORAGE_KEY]).toBeTruthy();
    });

    it('清理已删除文件夹的展开记录', () => {
      const expanded = new Set([ALL_FOLDER_ID, 'deleted-folder', 'f-seoul']);
      const sanitized = sanitizeExpandedIds(expanded, sampleTree.folders);
      expect([...sanitized]).toEqual([ALL_FOLDER_ID, 'f-seoul']);
    });

    it('首次访问自动展开有笔记的文件夹', () => {
      const next = autoExpandFoldersWithRecords(new Set(), sampleTree.folders);
      expect(next.has(ALL_FOLDER_ID)).toBe(true);
      expect(next.has(UNCATEGORIZED_FOLDER_ID)).toBe(true);
      expect(next.has('f-seoul')).toBe(true);
      expect(next.has('f-gangnam')).toBe(true);
      expect(next.has('f-empty')).toBe(false);
    });
  });
});
