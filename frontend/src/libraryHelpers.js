import { ALL_FOLDER_ID, UNCATEGORIZED_FOLDER_ID } from './dragMime.js';

export const EXPANDED_IDS_STORAGE_KEY = 'b-subtitle-expanded-folder-ids';

export function findFolder(folders, id) {
  for (const f of folders || []) {
    if (f.id === id) return f;
    const child = findFolder(f.children, id);
    if (child) return child;
  }
  return null;
}

export function folderRecordCount(folder) {
  let n = (folder.records || []).length;
  for (const c of folder.children || []) n += folderRecordCount(c);
  return n;
}

export function collectDescendantFolderIds(folders, folderId) {
  const folder = findFolder(folders, folderId);
  if (!folder) return new Set();
  const ids = new Set();
  const walk = (node) => {
    for (const child of node.children || []) {
      ids.add(child.id);
      walk(child);
    }
  };
  walk(folder);
  return ids;
}

export function canDropFolderOn({
  folderId,
  draggingFolderId,
  dragPurpose,
  folders,
}) {
  const src = draggingFolderId;
  if (!src || dragPurpose !== 'folder-move') return false;
  if (folderId === UNCATEGORIZED_FOLDER_ID) return false;
  if (folderId === src) return false;
  if (
    folderId &&
    folderId !== ALL_FOLDER_ID &&
    collectDescendantFolderIds(folders, src).has(folderId)
  ) {
    return false;
  }
  return true;
}

export function collectKnownFolderIds(folders) {
  const ids = new Set([ALL_FOLDER_ID, UNCATEGORIZED_FOLDER_ID]);
  const walk = (items) => {
    for (const f of items || []) {
      if (f.id) ids.add(f.id);
      walk(f.children);
    }
  };
  walk(folders);
  return ids;
}

export function sanitizeExpandedIds(expandedIds, folders) {
  const valid = collectKnownFolderIds(folders);
  const next = new Set();
  for (const id of expandedIds) {
    if (valid.has(id)) next.add(id);
  }
  return next;
}

export function restoreExpandedIds(storage = localStorage) {
  try {
    const raw = storage.getItem(EXPANDED_IDS_STORAGE_KEY);
    if (!raw) return { expandedIds: null, fromStorage: false };
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr) || !arr.length) return { expandedIds: null, fromStorage: false };
    return {
      expandedIds: new Set(arr.filter((id) => typeof id === 'string' && id)),
      fromStorage: true,
    };
  } catch {
    return { expandedIds: null, fromStorage: false };
  }
}

export function saveExpandedIds(expandedIds, storage = localStorage) {
  try {
    storage.setItem(EXPANDED_IDS_STORAGE_KEY, JSON.stringify([...expandedIds]));
    return true;
  } catch {
    return false;
  }
}

export function autoExpandFoldersWithRecords(expandedIds, folders) {
  const next = new Set(expandedIds);
  next.add(ALL_FOLDER_ID);
  next.add(UNCATEGORIZED_FOLDER_ID);
  const walk = (items) => {
    for (const f of items || []) {
      if (folderRecordCount(f) > 0) next.add(f.id);
      walk(f.children);
    }
  };
  walk(folders);
  return next;
}

export function flattenFolderOptions(folders, depth = 0, out = []) {
  for (const f of folders || []) {
    out.push({ id: f.id, label: `${'　'.repeat(depth)}📂 ${f.name}` });
    flattenFolderOptions(f.children, depth + 1, out);
  }
  return out;
}

export function resolveFolderDropParent(folderId) {
  return folderId === ALL_FOLDER_ID ? null : folderId;
}

export function resolveRecordDropFolderId(folderId) {
  return folderId === UNCATEGORIZED_FOLDER_ID ? null : folderId;
}
