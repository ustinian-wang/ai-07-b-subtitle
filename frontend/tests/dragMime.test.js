import { describe, expect, it } from 'vitest';
import {
  DRAG_FOLDER_MIME,
  DRAG_FOLDER_MOVE_MIME,
  hasDragType,
  isFolderMoveDrag,
  isFolderRefDrag,
} from '../src/dragMime.js';
import { createDragEvent } from './helpers/dragEvent.js';

describe('dragMime', () => {
  it('识别文件夹移动拖拽', () => {
    const event = createDragEvent({ types: [DRAG_FOLDER_MOVE_MIME] });
    expect(isFolderMoveDrag(event)).toBe(true);
    expect(isFolderRefDrag(event)).toBe(false);
  });

  it('识别文件夹引用拖拽', () => {
    const event = createDragEvent({ types: [DRAG_FOLDER_MIME], effectAllowed: 'copy' });
    expect(isFolderRefDrag(event)).toBe(true);
    expect(isFolderMoveDrag(event)).toBe(false);
  });

  it('hasDragType 在无 dataTransfer 时返回 false', () => {
    expect(hasDragType({}, DRAG_FOLDER_MOVE_MIME)).toBe(false);
  });
});
