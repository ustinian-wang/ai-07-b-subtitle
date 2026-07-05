<template>
  <div class="wrap">
    <h1>{{ title }}</h1>
    <p class="hint">GET /api/health（经 Vite 代理）</p>
    <pre class="pre">{{ text }}</pre>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return { title: 'AI 沙箱', text: '加载中…' };
  },
  mounted() {
    fetch('/api/health')
      .then((r) => r.json())
      .then((d) => {
        this.text = JSON.stringify(d, null, 2);
      })
      .catch((e) => {
        this.text = String(e);
      });
  },
};
</script>

<style>
body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: #0f1220;
  color: #e8ecff;
}
.wrap {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px;
}
.hint {
  color: #9aa3c7;
}
.pre {
  background: #151a2e;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
}
</style>
