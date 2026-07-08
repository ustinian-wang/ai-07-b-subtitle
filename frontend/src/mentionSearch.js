import { match, pinyin } from 'pinyin-pro';

const HAS_CJK = /[\u4e00-\u9fff]/;

function normalizePy(s) {
  return (s || '').toLowerCase().replace(/ü/g, 'v');
}

function mentionSearchTexts(item, isFolder) {
  if (isFolder) {
    return [item.name, item.path, '分类', '文件夹', '未分类'].filter(Boolean);
  }
  return [item.title, item.bvid, item.note_id, item.id].filter(Boolean);
}

/** @ 弹层：原文 + 全拼 + 首字母 + pinyin-pro 连续匹配 */
export function mentionQueryMatch(item, query, { isFolder = false } = {}) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return true;

  const texts = mentionSearchTexts(item, isFolder);
  const hay = texts.join(' ').toLowerCase();
  if (hay.includes(q)) return true;

  for (const text of texts) {
    if (!text || !HAS_CJK.test(text)) continue;
    const ranges = match(text, q, { precision: 'every', continuous: true });
    if (ranges?.length) return true;
    const fullPy = normalizePy(pinyin(text, { toneType: 'none' }).replace(/\s/g, ''));
    if (fullPy.includes(normalizePy(q))) return true;
    const initials = normalizePy(
      pinyin(text, { pattern: 'first', toneType: 'none' }).replace(/\s/g, ''),
    );
    if (initials.includes(normalizePy(q))) return true;
  }
  return false;
}

function _selfCheck() {
  const folder = { name: '首尔', path: '首尔', recordCount: 3 };
  const note = { title: '济州岛旅行攻略', bvid: 'BV123', id: 'abc' };
  if (!mentionQueryMatch(folder, 'shouer', { isFolder: true })) throw new Error('shouer');
  if (!mentionQueryMatch(folder, 'se', { isFolder: true })) throw new Error('se initials');
  if (!mentionQueryMatch(note, 'jizhou', { isFolder: false })) throw new Error('jizhou');
  if (!mentionQueryMatch(note, 'jzd', { isFolder: false })) throw new Error('jzd');
  if (!mentionQueryMatch(note, 'lvxing', { isFolder: false })) throw new Error('lvxing');
  if (mentionQueryMatch(note, 'zzz', { isFolder: false })) throw new Error('should not match zzz');
}

if (import.meta.env?.DEV) {
  try {
    _selfCheck();
  } catch (e) {
    console.warn('[mentionSearch] self-check failed', e);
  }
}
