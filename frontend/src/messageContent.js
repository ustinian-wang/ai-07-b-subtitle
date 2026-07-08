/** 解析消息中的 @[title](id) / @[分类:name](folder:id) 引用片段 */
export const MSG_REF_RE = /@\[([^\]]*)\]\(([^)]+)\)/g;

function refMeta(recordMap, id, fallbackTitle) {
  const rec = recordMap[id];
  return {
    source: rec?.source || 'bilibili',
    displayTitle: rec
      ? rec.title || rec.bvid || rec.note_id || rec.id
      : fallbackTitle || id,
  };
}

export function parseMessageSegments(text, recordMap = {}) {
  if (!text) return [{ type: 'text', text: '' }];
  const segments = [];
  let lastIndex = 0;
  MSG_REF_RE.lastIndex = 0;
  let match = MSG_REF_RE.exec(text);
  while (match) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', text: text.slice(lastIndex, match.index) });
    }
    const id = match[2];
    if (id.startsWith('folder:')) {
      const folderId = id.slice('folder:'.length);
      const displayName = (match[1] || '').replace(/^分类:/, '') || folderId;
      segments.push({ type: 'folder-ref', folderId, displayName });
    } else {
      segments.push({ type: 'ref', id, ...refMeta(recordMap, id, match[1]) });
    }
    lastIndex = MSG_REF_RE.lastIndex;
    match = MSG_REF_RE.exec(text);
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', text: text.slice(lastIndex) });
  }
  return segments.length ? segments : [{ type: 'text', text }];
}
