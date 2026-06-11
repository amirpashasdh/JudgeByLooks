const API_BASE = '';

let recommendations = [];
let ratings = {};
// ratings[product_id] = { contextual_fit: null, general_taste: null }

// ── Boot ──────────────────────────────────────────────────────────────────────

window.addEventListener('load', () => {
  window.scrollTo(0, 0);
  init();
});

async function init() {
  const sessionId = sessionStorage.getItem('session_id');
  const personId  = sessionStorage.getItem('person_id');

  if (!sessionId || !personId) {
    window.location.href = '/static/index.html';
    return;
  }

  renderKeywordPills();

  try {
    const res = await fetch(`${API_BASE}/api/recommendations/${sessionId}/${personId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    recommendations = data.products || [];
  } catch (err) {
    document.getElementById('productGrid').innerHTML =
      `<p style="color:#C0392B;font-size:14px;grid-column:1/-1">
         Failed to load recommendations. <a href="/static/index.html">Try again</a>
       </p>`;
    return;
  }

  recommendations.forEach(p => {
    ratings[p.product_id] = { contextual_fit: null, general_taste: null };
  });

  renderCards(recommendations);
  updateProgress();
}

// ── Keyword pills ─────────────────────────────────────────────────────────────

function renderKeywordPills() {
  const raw = sessionStorage.getItem('keywords');
  if (!raw) return;
  let kw;
  try { kw = JSON.parse(raw); } catch { return; }

  const top5 = Object.entries(kw)
    .filter(([, v]) => v > 0.4)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const wrap = document.getElementById('keywordPills');
  wrap.innerHTML = top5.map(([k]) =>
    `<span class="style-pill">${k.replace(/_/g, ' ')}</span>`
  ).join('');
}

// ── Card rendering ────────────────────────────────────────────────────────────

function renderCards(products) {
  const grid = document.getElementById('productGrid');
  grid.innerHTML = '';

  products.forEach(p => {
    const matchPct = Math.round((p.similarity_score || 0) * 100);
    const price    = p.price ? `${p.currency || ''} ${p.price}`.trim() : '';

    const topKw = Object.entries(p.matched_keywords || {})
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([k]) => `<span class="kw-pill">${k.replace(/_/g, ' ')}</span>`)
      .join('');

    const card = document.createElement('div');
    card.className = 'product-card';
    card.dataset.productId = p.product_id;

    card.innerHTML = `
      <div class="card-image-wrap">
        <img
          src="${escHtml(p.image_url)}"
          alt="${escHtml(p.name)}"
          loading="lazy"
          onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"
        />
        <div class="img-placeholder" style="display:none">${initials(p.brand, p.name)}</div>
        <span class="match-badge">${matchPct}% match</span>
        <span class="rated-check">✓</span>
      </div>

      <div class="card-info">
        <div class="card-brand">${escHtml(p.brand)}</div>
        <div class="card-name">${escHtml(p.name)}</div>
        ${price ? `<div class="card-price">${escHtml(price)}</div>` : ''}
        <div class="card-keywords">${topKw}</div>
      </div>

      <div class="card-ratings">
        <div class="rating-row">
          <span class="rating-label">Fits your current look?</span>
          <div class="stars" data-product="${escHtml(p.product_id)}" data-q="contextual_fit">
            ${starsHtml()}
          </div>
        </div>
        <div class="rating-row">
          <span class="rating-label">Matches your overall taste?</span>
          <div class="stars" data-product="${escHtml(p.product_id)}" data-q="general_taste">
            ${starsHtml()}
          </div>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });

  attachStarListeners();
}

function starsHtml() {
  return [1,2,3,4,5].map(n =>
    `<span class="star" data-value="${n}">★</span>`
  ).join('');
}

function initials(brand, name) {
  const src = brand || name || '?';
  return src.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Star interactions ─────────────────────────────────────────────────────────

function attachStarListeners() {
  document.querySelectorAll('.stars').forEach(group => {
    const productId = group.dataset.product;
    const question  = group.dataset.q;
    const stars     = group.querySelectorAll('.star');

    stars.forEach(star => {
      const val = parseInt(star.dataset.value, 10);

      star.addEventListener('mouseenter', () => {
        if (ratings[productId][question]) return; // already locked
        stars.forEach(s => {
          s.classList.toggle('hover', parseInt(s.dataset.value, 10) <= val);
        });
      });

      star.addEventListener('mouseleave', () => {
        if (ratings[productId][question]) return;
        stars.forEach(s => s.classList.remove('hover'));
      });

      star.addEventListener('click', () => {
        handleStarClick(productId, question, val);
      });
    });
  });
}

function handleStarClick(productId, question, value) {
  ratings[productId][question] = value;

  // Update display for this star group
  const group = document.querySelector(
    `.stars[data-product="${CSS.escape(productId)}"][data-q="${question}"]`
  );
  if (group) {
    group.querySelectorAll('.star').forEach(s => {
      const v = parseInt(s.dataset.value, 10);
      s.classList.toggle('active', v <= value);
      s.classList.remove('hover');
    });
  }

  // Check if this card is fully rated
  const r = ratings[productId];
  if (r.contextual_fit && r.general_taste) {
    const card = document.querySelector(`.product-card[data-product-id="${CSS.escape(productId)}"]`);
    if (card) card.classList.add('rated');
  }

  updateProgress();
}

// ── Progress ──────────────────────────────────────────────────────────────────

function updateProgress() {
  const total  = recommendations.length;
  const rated  = Object.values(ratings).filter(r => r.contextual_fit && r.general_taste).length;

  document.getElementById('progressLabel').textContent = `${rated} / ${total} rated`;
  document.getElementById('progressFill').style.width  = `${total ? (rated / total * 100) : 0}%`;

  const allDone = rated === total && total > 0;
  document.getElementById('submitBtn').disabled = !allDone;
  document.getElementById('bottomLabel').textContent = allDone
    ? `${total}/${total} rated ✓`
    : 'Rate all items to continue';
}

// ── Submit ────────────────────────────────────────────────────────────────────

document.getElementById('submitBtn').addEventListener('click', submitRatings);

async function submitRatings() {
  const sessionId = sessionStorage.getItem('session_id');
  const personId  = parseInt(sessionStorage.getItem('person_id'), 10);
  const btn       = document.getElementById('submitBtn');
  const label     = document.getElementById('bottomLabel');

  btn.disabled = true;
  btn.textContent = 'Saving...';

  const payload = recommendations.map(p => ({
    session_id:      sessionId,
    person_id:       personId,
    product_id:      p.product_id,
    contextual_fit:  ratings[p.product_id].contextual_fit,
    general_taste:   ratings[p.product_id].general_taste,
  }));

  try {
    const res = await fetch(`${API_BASE}/api/ratings/batch`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    sessionStorage.setItem('ratings', JSON.stringify(ratings));
    window.location.href = '/static/browse.html';

  } catch (err) {
    label.textContent = 'Failed to save — please try again.';
    label.style.color = '#C0392B';
    btn.disabled = false;
    btn.textContent = 'Continue →';
  }
}
