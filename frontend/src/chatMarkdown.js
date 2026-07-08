import { marked } from 'marked';

marked.setOptions({
  breaks: true,
  gfm: true,
});

/** 将 Markdown 文本转为 HTML（仅用于本地对话内容展示） */
export function renderMarkdownHtml(text) {
  const src = (text || '').trim();
  if (!src) return '';
  return marked.parse(src);
}
