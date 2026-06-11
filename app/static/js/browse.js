const MAX_FAVORITES = 5;
const API_BASE = '';

let allProducts = [];
let filteredProducts = [];
let selectedIds = new Set();
let activeCategory = 'All';

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

  try {
    const res = await fetch(`${API_BASE}/api/browse/${sessionId}/${personId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    allProducts = data.products || [];
  } catch (err) {
    document.getElementById('browseGrid').innerHTML =
      `<p style="color:#C0392B;font-size:14px;grid-column:1/-1">
         Failed to load products. <a href="/static/index.html">Try again</a>
       </p>`;
    return;
  }

  filteredProducts = allProducts;
  buildFilterPills(allProducts);
  renderGrid(filteredProducts);
}

// ── Filter pills ──────────────────────────────────────────────────────────────

function buildFilterPills(products) {
  const seen = new Set();
  const categories = [];
  products.forEach(p => {
    const cat = p.category || 'Other';
    if (!seen.has(cat)) { seen.add(cat); categories.push(cat); }
  });

  const wrap = document.getElementById('filterPills');
  wrap.innerHTML = '';

  ['All', ...categories].forEach(cat => {
    const pill = document.createElement('button');
    pill.className = 'filter-pill' + (cat === 'All' ? ' active' : '');
    pill.textContent = cat;
    pill.addEventListener('click', () => filterByCategory(cat));
    wrap.appendChild(pill);
  });
}

function filterByCategory(category) {
  activeCategory = category;

  document.querySelectorAll('.filter-pill').forEach(p => {
    p.classList.toggle('active', p.textContent === category);
  });

  filteredProducts = category === 'All'
    ? allProducts
    : allProducts.filter(p => (p.category || 'Other') === category);

  renderGrid(filteredProducts);
}

// ── Grid rendering ────────────────────────────────────────────────────────────

function renderGrid(products) {
  const grid = document.getElementById('browseGrid');
  grid.innerHTML = '';

  if (!products.length) {
    grid.innerHTML = '<p style="font-size:14px;color:#6B6B6B;grid-column:1/-1">No products in this category.</p>';
    return;
  }

  products.forEach(p => {
    const card = createCard(p);
    grid.appendChild(card);
  });
}

function createCard(p) {
  const isSelected = selectedIds.has(p.product_id);
  const matchPct   = Math.round((p.similarity_score || 0) * 100);
  const price      = p.price ? `${p.currency || ''} ${p.price}`.trim() : '';

  const card = document.createElement('div');
  card.className = 'browse-card' + (isSelected ? ' selected' : '');
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
      <button class="heart-btn" aria-label="Favourite" data-id="${escHtml(p.product_id)}">
        ${isSelected ? '♥' : '♡'}
      </button>
    </div>
    <div class="browse-card-info">
      <div class="browse-card-brand">${escHtml(p.brand)}</div>
      <div class="browse-card-name">${escHtml(p.name)}</div>
      ${price ? `<div class="browse-card-price">${escHtml(price)}</div>` : ''}
    </div>
  `;

  // Heart button — toggle only
  card.querySelector('.heart-btn').addEventListener('click', e => {
    e.stopPropagation();
    toggleSelection(p.product_id);
  });

  // Card click — toggle too
  card.addEventListener('click', () => toggleSelection(p.product_id));

  return card;
}

// ── Selection ─────────────────────────────────────────────────────────────────

function toggleSelection(productId) {
  if (selectedIds.has(productId)) {
    selectedIds.delete(productId);
    applyCardState(productId, false);
  } else {
    if (selectedIds.size >= MAX_FAVORITES) {
      flashCounter();
      showToast('Maximum 5 favorites reached');
      return;
    }
    selectedIds.add(productId);
    applyCardState(productId, true);
  }

  updateCounter();
  updateBottomBar();
}

function applyCardState(productId, selected) {
  // Update every rendered copy (filter may show same card twice — won't happen,
  // but query all just in case grid was re-rendered)
  document.querySelectorAll(`.browse-card[data-product-id="${CSS.escape(productId)}"]`).forEach(card => {
    card.classList.toggle('selected', selected);
    const btn = card.querySelector('.heart-btn');
    if (btn) btn.textContent = selected ? '♥' : '♡';
  });
}

// ── Counter & bottom bar ──────────────────────────────────────────────────────

function updateCounter() {
  const n       = selectedIds.size;
  const el      = document.getElementById('favCounter');
  el.textContent = `${n} / 5 selected`;
  el.classList.toggle('maxed', n === MAX_FAVORITES);
}

function updateBottomBar() {
  const n     = selectedIds.size;
  const label = document.getElementById('bottomLabel');
  const btn   = document.getElementById('submitBtn');

  if (n === 0)               label.textContent = 'Select up to 5 favorites';
  else if (n === MAX_FAVORITES) label.textContent = '5 / 5 selected';
  else                       label.textContent = `${n} / 5 selected`;

  btn.disabled = n < 1;
}

function flashCounter() {
  const el = document.getElementById('favCounter');
  const orig = el.style.color;
  el.style.color = '#FF5252';
  el.style.fontWeight = '500';
  setTimeout(() => {
    el.style.color = '';
    el.style.fontWeight = '';
    updateCounter(); // restore proper state
  }, 600);
}

// ── Submit ────────────────────────────────────────────────────────────────────

document.getElementById('submitBtn').addEventListener('click', submitFavorites);

async function submitFavorites() {
  const sessionId = sessionStorage.getItem('session_id');
  const personId  = parseInt(sessionStorage.getItem('person_id'), 10);
  const btn       = document.getElementById('submitBtn');
  const label     = document.getElementById('bottomLabel');

  btn.disabled    = true;
  btn.textContent = 'Saving...';

  const productIds = Array.from(selectedIds);

  try {
    const res = await fetch(`${API_BASE}/api/favorites`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ session_id: sessionId, person_id: personId, product_ids: productIds }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    // Store selected product objects for thank-you page
    const favProducts = allProducts.filter(p => selectedIds.has(p.product_id));
    sessionStorage.setItem('favorites', JSON.stringify(favProducts));

    window.location.href = '/static/thankyou.html';

  } catch (err) {
    label.textContent = 'Failed to save — please try again.';
    label.style.color = '#C0392B';
    btn.disabled    = false;
    btn.textContent = 'Save my picks →';
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(message, duration = 2000) {
  // Remove any existing toast
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  document.body.appendChild(toast);

  // Trigger reflow before adding visible class so transition fires
  toast.getBoundingClientRect();
  toast.classList.add('visible');

  setTimeout(() => {
    toast.classList.remove('visible');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
  }, duration);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function initials(brand, name) {
  const src = brand || name || '?';
  return src.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();
}
