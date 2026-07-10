import { DRAG_FOLDER_MIME, DRAG_FOLDER_MOVE_MIME, DRAG_RECORD_MIME } from '../../src/dragMime.js';

export function createDataTransfer({ types = [], effectAllowed = 'move', data = {} } = {}) {
  const store = { ...data };
  return {
    types,
    effectAllowed,
    setData(type, value) {
      store[type] = value;
    },
    getData(type) {
      return store[type] || '';
    },
  };
}

export function createDragEvent({
  types = [],
  effectAllowed = 'move',
  data = {},
  targetHtml = '<div class="drag-target"></div>',
} = {}) {
  const el = document.createElement('div');
  el.innerHTML = targetHtml;
  const target = el.firstElementChild || el;
  target.closest = (selector) => target.querySelector(selector) || null;
  return {
    dataTransfer: createDataTransfer({ types, effectAllowed, data }),
    target,
    currentTarget: target,
    relatedTarget: null,
    preventDefault() {},
    stopPropagation() {},
  };
}

export function folderMoveDragEvent(folderId, name) {
  return createDragEvent({
    types: [DRAG_FOLDER_MOVE_MIME],
    effectAllowed: 'move',
    data: {
      [DRAG_FOLDER_MOVE_MIME]: JSON.stringify({ folder_id: folderId, name }),
    },
  });
}

export function folderRefDragEvent(folderId, name, recordIds) {
  return createDragEvent({
    types: [DRAG_FOLDER_MIME],
    effectAllowed: 'copy',
    data: {
      [DRAG_FOLDER_MIME]: JSON.stringify({
        folder_id: folderId,
        name,
        record_ids: recordIds,
        record_count: recordIds.length,
      }),
    },
  });
}

export function recordDragEvent(ids) {
  return createDragEvent({
    types: [DRAG_RECORD_MIME],
    effectAllowed: 'copyMove',
    data: {
      [DRAG_RECORD_MIME]: JSON.stringify(ids),
    },
  });
}
