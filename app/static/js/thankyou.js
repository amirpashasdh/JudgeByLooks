const KEYWORD_DIMENSIONS = {
  minimalist: 'aesthetic', maximalist: 'aesthetic', classic: 'aesthetic',
  avant_garde: 'aesthetic', streetwear: 'aesthetic', bohemian: 'aesthetic',
  preppy: 'aesthetic', romantic: 'aesthetic', edgy: 'aesthetic',
  quiet_luxury: 'aesthetic', coastal: 'aesthetic', dark_academia: 'aesthetic',
  sporty: 'aesthetic',
  playful: 'mood', serious: 'mood', rebellious: 'mood', elegant: 'mood',
  laid_back: 'mood', bold: 'mood', understated: 'mood', whimsical: 'mood',
  polished: 'mood', raw: 'mood',
  neutral: 'color', monochrome: 'color', earth_tones: 'color', pastel: 'color',
  bold_colors: 'color', black_forward: 'color', white_forward: 'color',
  jewel_tones: 'color', multicolor: 'color',
  loungewear: 'formality', casual: 'formality', smart_casual: 'formality',
  business_casual: 'formality', formal: 'formality', black_tie: 'formality',
  parisian: 'cultural', scandinavian: 'cultural', italian_luxury: 'cultural',
  japanese_minimalist: 'cultural', american_prep: 'cultural',
  british_heritage: 'cultural', nyc_streetwear: 'cultural', californian: 'cultural',
  fitted: 'silhouette', oversized: 'silhouette', structured: 'silhouette',
  flowy: 'silhouette', layered: 'silhouette', cropped: 'silhouette',
  voluminous: 'silhouette',
  everyday: 'occasion', workwear: 'occasion', going_out: 'occasion',
  travel: 'occasion', outdoor: 'occasion', sport: 'occasion',
  beach: 'occasion', occasion: 'occasion',
  sustainable: 'values', investment_piece: 'values', trend_driven: 'values',
  heritage_craft: 'values', luxury_status: 'values', budget_conscious: 'values',
  logo_forward: 'values', logo_free: 'values', size_inclusive: 'values',
  gender_neutral: 'values', performance_tech: 'values',
};

const DIMENSION_ORDER = [
  'aesthetic', 'color', 'mood', 'silhouette',
  'formality', 'cultural', 'occasion', 'values',
];

const DIMENSION_LABELS = {
  aesthetic: 'Aesthetic', mood: 'Mood', color: 'Color',
  silhouette: 'Silhouette', formality: 'Formality',
  cultural: 'Cultural', occasion: 'Occasion', values: 'Values',
};

// ── Boot ──────────────────────────────────────────────────────────────────────

window.addEventListener('load', init);

function init() {
  const sessionId = sessionStorage.getItem('session_id');
  if (!sessionId) {
    window.location.href = '/static/index.html';
    return;
  }

  const keywords  = parseJSON(sessionStorage.getItem('keywords'))  || {};
  const favorites = parseJSON(sessionStorage.getItem('favorites')) || [];

  const dimAverages  = computeDimensionAverages(keywords);
  const sortedDims   = DIMENSION_ORDER.slice().sort((a, b) => (dimAverages[b] || 0) - (dimAverages[a] || 0));
  const topKeywords  = getTopKeywords(keywords, 8);

  renderDimensionBars(sortedDims, dimAverages);
  renderTopKeywords(topKeywords);
  renderStyleSentence(keywords);
  renderFavorites(favorites);

  // Animate bars after a short delay so transition is visible
  setTimeout(() => {
    document.querySelectorAll('.dimension-bar-fill').forEach(el => {
      el.style.width = el.dataset.target;
    });
  }, 120);

  // Nav "Start over"
  document.getElementById('startOverNav').addEventListener('click', e => {
    e.preventDefault();
    clearAndGo('/static/index.html');
  });

  // CTA button
  document.getElementById('startOverBtn').addEventListener('click', () => {
    clearAndGo('/static/index.html');
  });
}

// ── Dimension bars ────────────────────────────────────────────────────────────

function computeDimensionAverages(keywords) {
  const sums   = {};
  const counts = {};

  Object.entries(keywords).forEach(([kw, score]) => {
    const dim = KEYWORD_DIMENSIONS[kw];
    if (!dim) return;
    sums[dim]   = (sums[dim]   || 0) + Number(score);
    counts[dim] = (counts[dim] || 0) + 1;
  });

  const avgs = {};
  DIMENSION_ORDER.forEach(dim => {
    avgs[dim] = counts[dim] ? sums[dim] / counts[dim] : 0;
  });
  return avgs;
}

function renderDimensionBars(sortedDims, dimAverages) {
  const wrap = document.getElementById('dimensionBars');
  wrap.innerHTML = '';

  sortedDims.forEach((dim, i) => {
    const score  = dimAverages[dim] || 0;
    const pct    = Math.min(score * 100, 100).toFixed(0) + '%';
    const label  = DIMENSION_LABELS[dim] || dim;

    const row = document.createElement('div');
    row.className = 'dimension-row';
    row.style.transitionDelay = `${i * 60}ms`;
    row.innerHTML = `
      <span class="dimension-label">${label}</span>
      <div class="dimension-bar-bg">
        <div class="dimension-bar-fill" data-target="${pct}" style="transition-delay:${i * 60}ms"></div>
      </div>
      <span class="dimension-score">${score.toFixed(2)}</span>
    `;
    wrap.appendChild(row);
  });
}

// ── Top keywords ──────────────────────────────────────────────────────────────

function getTopKeywords(keywords, n) {
  return Object.entries(keywords)
    .filter(([, v]) => Number(v) > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([k]) => k);
}

function renderTopKeywords(kwList) {
  const wrap = document.getElementById('topKeywordPills');
  wrap.innerHTML = kwList
    .map(k => `<span class="large-pill">${fmt(k)}</span>`)
    .join('');
}

// ── Style sentence ────────────────────────────────────────────────────────────

function renderStyleSentence(keywords) {
  const byDim = groupByDimension(keywords);

  const aesthetics = topN(byDim.aesthetic, 2);
  const colors     = topN(byDim.color,     1);
  const silhouette = topN(byDim.silhouette, 1);

  const parts = [];

  if (aesthetics.length >= 2) {
    parts.push(`Your style leans ${fmt(aesthetics[0])} and ${fmt(aesthetics[1])}`);
  } else if (aesthetics.length === 1) {
    parts.push(`Your style leans ${fmt(aesthetics[0])}`);
  }

  if (colors.length) {
    parts.push(`with a preference for ${fmt(colors[0])} tones`);
  }

  if (silhouette.length) {
    parts.push(`and ${fmt(silhouette[0])} silhouettes`);
  }

  const el = document.getElementById('styleSentence');
  if (parts.length) {
    el.textContent = parts.join(', ') + '.';
  } else {
    el.style.display = 'none';
  }
}

function groupByDimension(keywords) {
  const groups = {};
  Object.entries(keywords).forEach(([kw, score]) => {
    const dim = KEYWORD_DIMENSIONS[kw];
    if (!dim || Number(score) <= 0.1) return;
    if (!groups[dim]) groups[dim] = [];
    groups[dim].push([kw, Number(score)]);
  });
  // sort each group descending
  Object.values(groups).forEach(arr => arr.sort((a, b) => b[1] - a[1]));
  return groups;
}

function topN(arr, n) {
  if (!arr) return [];
  return arr.slice(0, n).map(([k]) => k);
}

// ── Favorites ─────────────────────────────────────────────────────────────────

function renderFavorites(favorites) {
  const row = document.getElementById('favoritesRow');

  if (!favorites || !favorites.length) {
    row.outerHTML = '<p style="font-size:14px;color:#6B6B6B;margin:12px 0 40px">No favorites saved.</p>';
    return;
  }

  row.innerHTML = favorites.map(p => {
    const price = p.price ? `${p.currency || ''} ${p.price}`.trim() : '';
    const url   = p.product_url || '#';
    return `
      <a class="favorite-card" href="${escHtml(url)}" target="_blank" rel="noopener">
        <div class="card-image-wrap">
          <img
            src="${escHtml(p.image_url || '')}"
            alt="${escHtml(p.name || '')}"
            loading="lazy"
            onerror="this.style.display='none'"
          />
        </div>
        <div class="favorite-card-info">
          <div class="favorite-card-brand">${escHtml(p.brand || '')}</div>
          <div class="favorite-card-name">${escHtml(p.name || '')}</div>
          ${price ? `<div class="favorite-card-price">${escHtml(price)}</div>` : ''}
        </div>
      </a>
    `;
  }).join('');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function clearAndGo(url) {
  sessionStorage.clear();
  window.location.href = url;
}

function parseJSON(str) {
  if (!str) return null;
  try { return JSON.parse(str); } catch { return null; }
}

function fmt(kw) {
  if (!kw) return '';
  const s = kw.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
