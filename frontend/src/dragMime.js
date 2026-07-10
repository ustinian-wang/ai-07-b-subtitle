export const DRAG_RECORD_MIME = 'application/x-subtitle-ids';
export const DRAG_FOLDER_MIME = 'application/x-subtitle-folder';
export const DRAG_FOLDER_MOVE_MIME = 'application/x-subtitle-folder-move';
export const ALL_FOLDER_ID = '__all__';
export const ALL_FOLDER_NAME = '全部';
export const UNCATEGORIZED_FOLDER_ID = '__uncategorized__';

export function hasDragType(event, mime) {
  const types = event.dataTransfer?.types;
  if (!types) return false;
  return Array.from(types).includes(mime);
}

export function isFolderMoveDrag(event) {
  return hasDragType(event, DRAG_FOLDER_MOVE_MIME);
}

export function isFolderRefDrag(event) {
  return hasDragType(event, DRAG_FOLDER_MIME);
}
