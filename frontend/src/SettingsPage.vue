<template>
  <div class="settings-page">
    <header class="settings-head">
      <button class="btn" type="button" @click="$emit('back')">← 返回</button>
      <h1>设置</h1>
    </header>

    <section class="panel">
      <h2 class="section-title">B 站登录 Cookie</h2>
      <p class="hint">
        配置 <code>SESSDATA</code> 后可拉取需登录的 CC / AI 字幕。在浏览器登录 bilibili.com → F12 →
        Application → Cookies → 复制 <code>SESSDATA</code> 的值。
      </p>

      <p v-if="biliConfigured" class="status ok">
        当前已配置：<code>{{ biliMasked }}</code>
      </p>
      <p v-else class="status warn">尚未配置 SESSDATA</p>

      <label class="label" for="sessdata">BILIBILI SESSDATA</label>
      <input
        id="sessdata"
        v-model="sessdata"
        class="input"
        type="password"
        autocomplete="off"
        placeholder="粘贴 SESSDATA，留空并保存可清除"
      />
    </section>

    <section class="panel">
      <h2 class="section-title">小红书登录 Cookie</h2>
      <p class="hint">
        粘贴登录 <a href="https://www.xiaohongshu.com" target="_blank" rel="noopener">xiaohongshu.com</a>
        后的 Cookie（推荐整段复制，或至少包含 <code>web_session</code>）。尽量使用 App
        分享的完整链接（含 <code>xsec_token</code>）。
      </p>

      <p v-if="xhsConfigured" class="status ok">
        当前已配置：<code>{{ xhsMasked }}</code>
      </p>
      <p v-else class="status warn">尚未配置小红书 Cookie</p>

      <label class="label" for="xhs-cookie">XIAOHONGSHU COOKIE</label>
      <textarea
        id="xhs-cookie"
        v-model="xhsCookie"
        class="input textarea"
        rows="4"
        autocomplete="off"
        placeholder="粘贴 Cookie，留空并保存可清除"
      />

      <div class="toolbar">
        <button class="btn primary" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
        <span v-if="tip" :class="['tip', tipOk ? 'ok' : 'err']">{{ tip }}</span>
      </div>
    </section>
  </div>
</template>

<script>
export default {
  name: 'SettingsPage',
  emits: ['back'],
  data() {
    return {
      sessdata: '',
      xhsCookie: '',
      biliConfigured: false,
      biliMasked: '',
      xhsConfigured: false,
      xhsMasked: '',
      saving: false,
      tip: '',
      tipOk: true,
    };
  },
  mounted() {
    this.load();
  },
  methods: {
    async load() {
      try {
        const resp = await fetch('/api/v1/settings');
        const data = await resp.json();
        if (!resp.ok) return;
        this.biliConfigured = !!data.bilibili_sessdata_configured;
        this.biliMasked = data.bilibili_sessdata_masked || '';
        this.xhsConfigured = !!data.xiaohongshu_cookie_configured;
        this.xhsMasked = data.xiaohongshu_cookie_masked || '';
      } catch {
        /* ignore */
      }
    },
    async save() {
      this.saving = true;
      this.tip = '';
      try {
        const body = {};
        if (this.sessdata !== '') body.bilibili_sessdata = this.sessdata;
        if (this.xhsCookie !== '') body.xiaohongshu_cookie = this.xhsCookie;
        if (!Object.keys(body).length) {
          this.tip = '请填写要更新的配置项';
          this.tipOk = false;
          return;
        }

        const resp = await fetch('/api/v1/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (!resp.ok) {
          this.tip = data.detail || '保存失败';
          this.tipOk = false;
          return;
        }
        this.biliConfigured = !!data.bilibili_sessdata_configured;
        this.biliMasked = data.bilibili_sessdata_masked || '';
        this.xhsConfigured = !!data.xiaohongshu_cookie_configured;
        this.xhsMasked = data.xiaohongshu_cookie_masked || '';
        this.sessdata = '';
        this.xhsCookie = '';
        this.tip = '已保存';
        this.tipOk = true;
      } catch (e) {
        this.tip = String(e);
        this.tipOk = false;
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>

<style scoped>
.settings-page {
  min-height: 100vh;
  max-width: 640px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  box-sizing: border-box;
}
.settings-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}
.settings-head h1 {
  margin: 0;
  font-size: 1.5rem;
}
.section-title {
  margin: 0 0 12px;
  font-size: 1.05rem;
}
.panel {
  margin-top: 20px;
  padding: 16px;
  background: #151a2e;
  border-radius: 10px;
}
.hint {
  margin: 0 0 16px;
  color: #9aa3c7;
  font-size: 0.9rem;
  line-height: 1.55;
}
.hint a {
  color: #a8b8ff;
}
.hint code {
  color: #a8b8ff;
  font-size: 0.85em;
}
.status {
  margin: 0 0 16px;
  font-size: 0.88rem;
}
.status.ok {
  color: #7ddea2;
}
.status.warn {
  color: #ffb86c;
}
.status code {
  color: #e8ecff;
}
.label {
  display: block;
  margin-bottom: 6px;
  color: #b8c0e0;
  font-size: 0.9rem;
}
.input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #2a3358;
  border-radius: 8px;
  background: #0f1220;
  color: #e8ecff;
  font-size: 0.95rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.textarea {
  resize: vertical;
  min-height: 88px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}
.btn {
  padding: 8px 16px;
  border: 1px solid #3d4a7a;
  border-radius: 8px;
  background: #1c2440;
  color: #e8ecff;
  cursor: pointer;
  font-size: 0.95rem;
}
.btn.primary {
  background: #3b5bdb;
  border-color: #3b5bdb;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.tip.ok {
  color: #7ddea2;
  font-size: 0.88rem;
}
.tip.err {
  color: #ff8a8a;
  font-size: 0.88rem;
}
</style>
