// ── 共用 Domain 設定 ─────────────────────────────────────────────────────────
// 所有工具頁面共用此檔，新增/修改環境只需改這裡
(function () {
  const DOMAINS = [
    {
      group: '🧪 測試環境', items: [
        { label: 'DEV 環境', value: 'https://tiger-dev.servicelab.sh' },
        { label: 'STG 環境', value: 'https://tiger-stg.servicelab.sh' },
        { label: 'UAT 環境', value: 'https://gw-tiger-api.agkhcf12.com' },
      ]
    },
    {
      group: '🏢 正式環境 (mppwr.com)', items: [
        { label: '長城 (pd1)',  value: 'https://vd001-tiger-api.mppwr.com' },
        { label: '谷哥 (pd2)',  value: 'https://vd002-tiger-api.mppwr.com' },
        { label: '大眾 (pd3)',  value: 'https://vd003-tiger-api.mppwr.com' },
        { label: '瑞銀 (pd4)',  value: 'https://vd004-tiger-api.mppwr.com' },
        { label: '勇士 (pd6)',  value: 'https://vd006-tiger-api.mppwr.com' },
        { label: '蘋果 (pd7)',  value: 'https://vd007-tiger-api.mppwr.com' },
        { label: '芒果 (pd8)',  value: 'https://vd008-tiger-api.mppwr.com' },
        { label: '非凡 (pd9)',  value: 'https://vd009-tiger-api.mppwr.com' },
        { label: '英偉達 (p11)', value: 'https://vd011-tiger-api.mppwr.com' },
        { label: '特斯拉 (p12)', value: 'https://vd012-tiger-api.mppwr.com' },
        { label: 'Meta (p13)',  value: 'https://vd013-tiger-api.mppwr.com' },
        { label: 'ByBet (p14)', value: 'https://tiger-prod-vd014.servicezone.io' },
      ]
    },
    {
      group: '✏️ 自訂', items: [
        { label: '自訂 URL...', value: '__custom__' },
      ]
    },
  ];

  // 將 Domain 選單注入到指定容器（需含 class="field"）
  window.renderDomainSelect = function (targetId) {
    const container = document.getElementById(targetId);
    if (!container) return;

    let opts = `<option value="">-- 請選擇環境 --</option>`;
    for (const g of DOMAINS) {
      opts += `<optgroup label="${g.group}">`;
      for (const item of g.items) {
        opts += `<option value="${item.value}">${item.label}</option>`;
      }
      opts += `</optgroup>`;
    }

    container.innerHTML = `
      <label>Domain URL</label>
      <select id="domainUrlSelect" onchange="onDomainSelectChange()"
        style="width:100%;background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:8px 10px;border-radius:6px;font-size:13px;">
        ${opts}
      </select>
      <input id="domainUrl" type="text" placeholder="https://api.example.com" value=""
        style="display:none;margin-top:6px;width:100%;background:#0f172a;border:1px solid #334155;color:#e2e8f0;padding:8px 10px;border-radius:6px;font-size:13px;">
    `;
  };

  window.onDomainSelectChange = function () {
    const sel   = document.getElementById('domainUrlSelect');
    const input = document.getElementById('domainUrl');
    if (sel.value === '__custom__') {
      input.style.display = 'block';
      input.value = '';
      input.focus();
    } else {
      input.style.display = 'none';
      input.value = sel.value;
    }
  };

  window.getBase = function () {
    const sel   = document.getElementById('domainUrlSelect');
    const input = document.getElementById('domainUrl');
    const d = (sel.value === '__custom__' ? input.value : sel.value).trim().replace(/\/$/, '');
    if (!d || sel.value === '') { alert('請選擇 Domain URL'); throw new Error('no domain'); }
    return d;
  };
})();
