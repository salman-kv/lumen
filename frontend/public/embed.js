/*! Lumen embed: adds a floating chat bubble that opens the organization's assistant in an iframe.
 *  Usage: <script src="https://YOUR-HOST/embed.js" data-token="ast_..." async></script>
 *  Only the public assistant token is exposed here. It cannot reach the admin dashboard or any private document. */
(function () {
  var script = document.currentScript || document.querySelector('script[data-token][src*="embed.js"]');
  if (!script) return;
  var token = script.getAttribute('data-token');
  if (!token) { console.warn('[Lumen] embed.js needs a data-token attribute.'); return; }
  var origin = new URL(script.src, location.href).origin;
  var color = script.getAttribute('data-color') || '#0b8f6e';
  var open = false, iframe = null;

  var css = document.createElement('style');
  css.textContent =
    '.lumen-btn{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:60px;height:60px;border:0;border-radius:20px;cursor:pointer;display:grid;place-items:center;box-shadow:0 10px 30px rgba(0,0,0,.28);transition:transform .2s ease,border-radius .2s ease}' +
    '.lumen-btn:hover{transform:translateY(-2px) scale(1.04)}.lumen-btn:active{transform:scale(.96)}' +
    '.lumen-btn svg{width:28px;height:28px;transition:transform .25s ease}' +
    '.lumen-panel{position:fixed;right:20px;bottom:92px;z-index:2147483000;width:400px;max-width:calc(100vw - 24px);height:min(680px,calc(100dvh - 116px));border-radius:20px;overflow:hidden;background:#fff;box-shadow:0 20px 60px rgba(0,0,0,.3);opacity:0;transform:translateY(16px) scale(.97);transform-origin:bottom right;pointer-events:none;transition:opacity .22s ease,transform .22s cubic-bezier(.16,1,.3,1)}' +
    '.lumen-panel.lumen-open{opacity:1;transform:none;pointer-events:auto}.lumen-panel iframe{width:100%;height:100%;border:0;display:block}' +
    '@media (max-width:520px){.lumen-panel{right:0;bottom:0;width:100vw;max-width:100vw;height:100dvh;border-radius:0}.lumen-btn[aria-expanded=true]{display:none}.lumen-close{display:grid!important}}' +
    '.lumen-close{display:none;position:absolute;top:12px;right:12px;z-index:2;width:34px;height:34px;border:0;border-radius:10px;background:rgba(0,0,0,.08);cursor:pointer;place-items:center;font-size:20px;line-height:1}' +
    '@media (prefers-reduced-motion:reduce){.lumen-btn,.lumen-panel,.lumen-btn svg{transition:none}}';
  document.head.appendChild(css);

  var btn = document.createElement('button');
  btn.className = 'lumen-btn';
  btn.type = 'button';
  btn.setAttribute('aria-label', 'Open assistant');
  btn.setAttribute('aria-expanded', 'false');
  btn.style.background = color;
  var ICON_CHAT = '<svg viewBox="0 0 256 256" fill="#fff" aria-hidden="true"><path d="M216 48H40a16 16 0 0 0-16 16v160a15.84 15.84 0 0 0 9.25 14.5A16.05 16.05 0 0 0 40 240a15.89 15.89 0 0 0 10.25-3.78l.09-.07L83 208h133a16 16 0 0 0 16-16V64a16 16 0 0 0-16-16Zm0 144H83a8 8 0 0 0-5.1 1.83L40 224V64h176Z"/></svg>';
  var ICON_X = '<svg viewBox="0 0 256 256" fill="#fff" aria-hidden="true"><path d="M205.66 194.34a8 8 0 0 1-11.32 11.32L128 139.31l-66.34 66.35a8 8 0 0 1-11.32-11.32L116.69 128 50.34 61.66a8 8 0 0 1 11.32-11.32L128 116.69l66.34-66.35a8 8 0 0 1 11.32 11.32L139.31 128Z"/></svg>';
  btn.innerHTML = ICON_CHAT;

  var panel = document.createElement('div');
  panel.className = 'lumen-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Assistant');
  var close = document.createElement('button');
  close.className = 'lumen-close';
  close.type = 'button';
  close.setAttribute('aria-label', 'Close assistant');
  close.textContent = '×';
  panel.appendChild(close);

  function toggle(force) {
    open = typeof force === 'boolean' ? force : !open;
    if (open && !iframe) {
      iframe = document.createElement('iframe');
      iframe.src = origin + '/a/' + encodeURIComponent(token) + '?embed=1';
      iframe.title = 'Assistant chat';
      iframe.allow = 'clipboard-write';
      panel.appendChild(iframe);
    }
    panel.classList.toggle('lumen-open', open);
    btn.setAttribute('aria-expanded', String(open));
    btn.setAttribute('aria-label', open ? 'Close assistant' : 'Open assistant');
    btn.innerHTML = open ? ICON_X : ICON_CHAT;
  }
  btn.addEventListener('click', function () { toggle(); });
  close.addEventListener('click', function () { toggle(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && open) toggle(false); });

  // Match the organization's brand color (public, non-sensitive config).
  fetch(origin + '/api/public/assistant/' + encodeURIComponent(token))
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (cfg) { if (cfg && cfg.color) btn.style.background = cfg.color; })
    .catch(function () {});

  function mount() { document.body.appendChild(panel); document.body.appendChild(btn); }
  if (document.body) mount(); else document.addEventListener('DOMContentLoaded', mount);
})();
