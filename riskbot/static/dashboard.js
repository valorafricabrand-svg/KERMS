const $ = (selector) => document.querySelector(selector);
let timezone = 'Africa/Nairobi';
const money = (minor) => `KES ${new Intl.NumberFormat('en-KE', {
  maximumFractionDigits: 0,
}).format(minor / 100)}`;

function localTimestamp(hoursAgo = 0) {
  return new Date(Date.now() - hoursAgo * 60 * 60 * 1000).toISOString();
}

const demoData = {
  mode: 'demo',
  business_date: new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Nairobi' }).format(new Date()),
  rules: {
    max_single_transaction_kes: '100000',
    max_daily_payer_total_kes: '250000',
    max_daily_payer_transactions: 20,
  },
  transactions: [
    { receipt_number: 'TILL8A2F1', amount_minor: 12500000, payer_phone: '254 712 ••• 482', transaction_time: localTimestamp(0.35), account_reference: 'ORDER-284' },
    { receipt_number: 'TILL73C90', amount_minor: 4825000, payer_phone: '254 701 ••• 119', transaction_time: localTimestamp(1.1), account_reference: 'INVOICE-108' },
    { receipt_number: 'TILL1B601', amount_minor: 2200000, payer_phone: '254 728 ••• 031', transaction_time: localTimestamp(2.4), account_reference: 'ORDER-281' },
    { receipt_number: 'TILL9DA17', amount_minor: 8650000, payer_phone: '254 712 ••• 482', transaction_time: localTimestamp(3.2), account_reference: 'ORDER-279' },
    { receipt_number: 'TILL55F0A', amount_minor: 1350000, payer_phone: '254 733 ••• 560', transaction_time: localTimestamp(4.7), account_reference: 'WALK-IN' },
    { receipt_number: 'TILL2E041', amount_minor: 6720000, payer_phone: '254 701 ••• 119', transaction_time: localTimestamp(6.1), account_reference: 'INVOICE-106' },
  ],
};

let currentData = demoData;
let demoTransactions = [...demoData.transactions];
let toastTimer;

function getSummary(data) {
  if (data.mode === 'live') {
    return {
      count: data.transaction_count,
      total: data.total_minor,
      risks: data.risks || [],
    };
  }

  const countByPayer = new Map();
  let total = 0;
  const risks = [];
  for (const transaction of demoTransactions) {
    total += transaction.amount_minor;
    const payer = transaction.payer_phone || transaction.receipt_number;
    const payerSummary = countByPayer.get(payer) || { count: 0, total: 0 };
    payerSummary.count += 1;
    payerSummary.total += transaction.amount_minor;
    countByPayer.set(payer, payerSummary);

    if (transaction.amount_minor > Number(data.rules.max_single_transaction_kes) * 100) {
      risks.push(`Large payment: ${money(transaction.amount_minor)} (receipt ${transaction.receipt_number}, payer ${payer}).`);
    }
  }
  for (const [payer, summary] of countByPayer) {
    if (summary.total > Number(data.rules.max_daily_payer_total_kes) * 100) {
      risks.push(`Daily payer total is high: ${money(summary.total)} across ${summary.count} payment(s) for ${payer}.`);
    }
    if (summary.count > Number(data.rules.max_daily_payer_transactions)) {
      risks.push(`High payment frequency: ${summary.count} payments from ${payer} today.`);
    }
  }
  return { count: demoTransactions.length, total, risks };
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-KE', {
    timeZone: timezone, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: true,
  }).format(date);
}

function payerInitials(payer) {
  const digits = String(payer || '').replace(/\D/g, '');
  return digits.slice(-2) || 'MP';
}

function setConnection(mode, error = '') {
  const live = mode === 'live';
  $('#connection-label').textContent = live ? 'Live data connected' : 'Demo preview';
  $('.connection-dot').style.background = live ? '#69a780' : '#d3a158';
  $('.connection-dot').style.boxShadow = live ? '0 0 0 3px #e6f2e9' : '0 0 0 3px #f5ead7';
  $('#demo-banner').hidden = live;
  $('#simulate-payment').hidden = live;
  $('#connect-open').textContent = live ? 'Disconnect' : 'Connect live data';
  $('#demo-connect').textContent = error || 'Connect your data →';
  $('#demo-connect').disabled = Boolean(error);
}

function renderRisks(risks) {
  const status = $('#risk-status');
  const list = $('#risk-list');
  status.classList.toggle('has-risks', risks.length > 0);
  if (risks.length === 0) {
    status.innerHTML = '<span class="status-check">✓</span><div><strong>Looking good</strong><span>No unusual activity found</span></div>';
    list.innerHTML = '';
    return;
  }
  status.innerHTML = `<span class="status-check">!</span><div><strong>${risks.length} item${risks.length === 1 ? '' : 's'} to review</strong><span>Take a look at the flagged activity</span></div>`;
  list.innerHTML = risks.slice(0, 4).map((risk) => `<div class="risk-item"><i></i><span>${escapeHtml(risk)}</span></div>`).join('');
}

function render(data) {
  currentData = data;
  timezone = data.timezone || timezone;
  const summary = getSummary(data);
  const transactions = data.mode === 'live' ? data.transactions : demoTransactions;
  const rules = data.rules;

  $('#today-label').textContent = new Intl.DateTimeFormat('en-KE', {
    timeZone: 'Africa/Nairobi', weekday: 'long', month: 'long', day: 'numeric',
  }).format(new Date()).toUpperCase();
  $('#stat-total').textContent = money(summary.total);
  $('#stat-count').textContent = summary.count.toLocaleString();
  $('#stat-risks').innerHTML = `${summary.risks.length} <small>alert${summary.risks.length === 1 ? '' : 's'}</small>`;
  $('#stat-total-foot').textContent = `${summary.count} payment${summary.count === 1 ? '' : 's'} received`;
  $('#stat-risk-foot').textContent = summary.risks.length ? 'Review the activity below' : 'No flagged activity';
  $('#risk-meter-fill').style.width = `${Math.min(summary.risks.length * 15, 100)}%`;
  $('#nav-payment-count').textContent = summary.count;
  $('#rule-single').textContent = money(Number(rules.max_single_transaction_kes) * 100);
  $('#rule-daily').textContent = money(Number(rules.max_daily_payer_total_kes) * 100);
  $('#rule-frequency').textContent = `Over ${rules.max_daily_payer_transactions} / day`;
  renderRisks(summary.risks);

  const rows = $('#transaction-rows');
  $('#empty-state').hidden = transactions.length > 0;
  rows.innerHTML = transactions.slice(0, 10).map((transaction) => {
    const flagged = transaction.amount_minor > Number(rules.max_single_transaction_kes) * 100;
    const reference = transaction.account_reference || '—';
    const phone = transaction.payer_phone || 'Payer unavailable';
    const label = phone.includes('•') ? 'M-Pesa customer' : `M-Pesa · ${phone.slice(-4)}`;
    return `<tr>
      <td><div class="payer-cell"><span class="payer-avatar">${escapeHtml(payerInitials(phone))}</span><span class="payer-name"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(transaction.receipt_number)}</span></span></div></td>
      <td>${escapeHtml(formatDate(transaction.transaction_time))}</td>
      <td>${escapeHtml(reference)}</td>
      <td class="amount-cell">${escapeHtml(money(transaction.amount_minor))}</td>
      <td><span class="status-pill ${flagged ? 'flagged' : ''}"><i></i>${flagged ? 'Review' : 'Received'}</span></td>
    </tr>`;
  }).join('');
  $('#table-summary').textContent = `Showing ${Math.min(transactions.length, 10)} recent payment${transactions.length === 1 ? '' : 's'}`;
  setConnection(data.mode);
}

function showToast(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 3200);
}

async function fetchLiveData(token) {
  const response = await fetch('/api/dashboard', {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    cache: 'no-store',
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error || `Dashboard request failed (${response.status})`);
  }
  const data = await response.json();
  if (data.mode !== 'live' || !Array.isArray(data.transactions) || !data.rules) {
    throw new Error('The server returned an unexpected dashboard response.');
  }
  return data;
}

function openConnect() {
  if (currentData.mode === 'live') {
    sessionStorage.removeItem('riskbot-dashboard-token');
    demoTransactions = [...demoData.transactions];
    render(demoData);
    showToast('Disconnected. You are back in the sample dashboard.');
    return;
  }
  $('#connect-error').textContent = '';
  $('#dashboard-token').value = '';
  $('#connect-dialog').showModal();
}

async function connectLive() {
  const token = $('#dashboard-token').value.trim();
  if (!token) {
    $('#connect-error').textContent = 'Enter your dashboard token to connect.';
    return;
  }
  $('#connect-submit').disabled = true;
  $('#connect-error').textContent = 'Connecting securely…';
  try {
    const data = await fetchLiveData(token);
    sessionStorage.setItem('riskbot-dashboard-token', token);
    render(data);
    $('#connect-dialog').close();
    showToast('Live transaction data connected.');
  } catch (error) {
    $('#connect-error').textContent = `${error.message} Check your token and server, or keep exploring the demo.`;
  } finally {
    $('#connect-submit').disabled = false;
  }
}

$('#connect-open').addEventListener('click', openConnect);
$('#demo-connect').addEventListener('click', openConnect);
$('#connect-submit').addEventListener('click', connectLive);
$('#stay-demo').addEventListener('click', () => $('#connect-dialog').close());
$('#dashboard-token').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') connectLive();
});

$('#simulate-payment').addEventListener('click', () => {
  const receipt = `DEMO${Math.random().toString(36).slice(2, 7).toUpperCase()}`;
  const transaction = {
    receipt_number: receipt,
    amount_minor: 12500000,
    payer_phone: '254 711 ••• 904',
    transaction_time: new Date().toISOString(),
    account_reference: 'SIMULATED',
  };
  demoTransactions = [transaction, ...demoTransactions];
  render({ ...demoData, transactions: demoTransactions });
  showToast('Sample KES 125,000 payment added. No real data was changed.');
});

$('#view-all').addEventListener('click', () => {
  document.querySelector('#payments').scrollIntoView({ behavior: 'smooth', block: 'center' });
  showToast('This view shows your 10 most recent payments.');
});
$('#rules-info').addEventListener('click', () => {
  showToast('Payments above a limit are flagged for owner review, not blocked.');
});

render(demoData);
const savedToken = sessionStorage.getItem('riskbot-dashboard-token');
if (savedToken) {
  fetchLiveData(savedToken)
    .then(render)
    .catch(() => {
      sessionStorage.removeItem('riskbot-dashboard-token');
      render(demoData);
      setConnection('demo', 'Live connection expired');
    });
}
