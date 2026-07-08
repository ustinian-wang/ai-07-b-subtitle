import { match, pinyin } from 'pinyin-pro';

const HAS_CJK = /[\u4e00-\u9fff]/;
const HAS_LETTER = /[a-z]/;

function normalizePy(s) {
  return (s || '').toLowerCase().replace(/ü/g, 'v');
}

function mentionSearchTexts(item, isFolder) {
  if (isFolder) {
    const extra =
      item.folderId === '__all__' ? ['全部', '所有', 'all', '根', 'quanbu'] : ['分类', '文件夹'];
    return [item.name, item.path, ...extra, '未分类'].filter(Boolean);
  }
  return [item.title, item.bvid, item.note_id, item.id].filter(Boolean);
}

function subsequenceMatch(hay, needle) {
  const h = normalizePy(hay);
  const n = normalizePy(needle);
  if (!n) return false;
  let hi = 0;
  for (let ni = 0; ni < n.length; ni += 1) {
    const ch = n[ni];
    hi = h.indexOf(ch, hi);
    if (hi === -1) return false;
    hi += 1;
  }
  return true;
}

function pinyinForms(text) {
  if (!text || !HAS_CJK.test(text)) return null;
  const fullPy = normalizePy(pinyin(text, { toneType: 'none' }).replace(/\s/g, ''));
  const syllables = normalizePy(pinyin(text, { toneType: 'none' }))
    .split(/\s+/)
    .filter(Boolean);
  const initials = normalizePy(
    pinyin(text, { pattern: 'first', toneType: 'none' }).replace(/\s/g, ''),
  );
  return { fullPy, syllables, initials };
}

/** 计算 @ 匹配得分，0 表示不匹配 */
export function mentionQueryScore(item, query, { isFolder = false } = {}) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return 1;

  const texts = mentionSearchTexts(item, isFolder);
  let best = 0;

  for (const text of texts) {
    if (!text) continue;
    const raw = text.toLowerCase();

    if (raw === q) best = Math.max(best, 1000);
    else if (raw.startsWith(q)) best = Math.max(best, 900);
    else if (raw.includes(q)) best = Math.max(best, 800);

    if (!HAS_LETTER.test(q)) continue;

    const forms = pinyinForms(text);
    if (forms) {
      const { fullPy, syllables, initials } = forms;
      if (fullPy.startsWith(q)) best = Math.max(best, 700);
      else if (fullPy.includes(q)) best = Math.max(best, 650);
      else if (subsequenceMatch(fullPy, q)) best = Math.max(best, 600);

      if (initials.startsWith(q)) best = Math.max(best, 550);
      else if (subsequenceMatch(initials, q)) best = Math.max(best, 500);

      if (syllables.some((s) => s.startsWith(q))) best = Math.max(best, 480);
      if (syllables.join('').includes(q)) best = Math.max(best, 460);

      const ranges = match(text, q, { precision: 'every', continuous: true });
      if (ranges?.length) best = Math.max(best, 450);
      const loose = match(text, q, { precision: 'every', continuous: false });
      if (loose?.length) best = Math.max(best, 420);
    } else if (raw.includes(q)) {
      best = Math.max(best, 750);
    }
  }

  return best;
}

/** @ 弹层：原文 + 全拼 + 首字母 + 子序列模糊 + pinyin-pro */
export function mentionQueryMatch(item, query, opts) {
  return mentionQueryScore(item, query, opts) > 0;
}

function _selfCheck() {
  const folder = { name: '首尔', path: '首尔', recordCount: 3 };
  const note = { title: '济州岛旅行攻略', bvid: 'BV123', id: 'abc' };
  const xjb = { title: '性价比分析', id: 'x1' };

  const must = [
    [folder, 'shouer', { isFolder: true }],
    [folder, 'se', { isFolder: true }],
    [note, 'jizhou', {}],
    [note, 'jzd', {}],
    [note, 'jzl', {}],
    [note, 'jzdlx', {}],
    [xjb, 'xingjiabi', {}],
    [xjb, 'xjb', {}],
    [xjb, 'xing', {}],
  ];
  for (const [item, q, opts] of must) {
    if (!mentionQueryMatch(item, q, opts)) throw new Error(`should match: ${item.title || item.name} / ${q}`);
  }
  if (mentionQueryMatch(note, 'zzz', {})) throw new Error('should not match zzz');

  const ranked = [
    { title: '性价比', id: 'a' },
    { title: '性能测试', id: 'b' },
  ];
  const scores = ranked.map((r) => mentionQueryScore(r, 'xing'));
  if (scores[0] < scores[1]) throw new Error('性价比 should rank above 性能测试 for xing');
}

if (import.meta.env?.DEV) {
  try {
    _selfCheck();
  } catch (e) {
    console.warn('[mentionSearch] self-check failed', e);
  }
}
