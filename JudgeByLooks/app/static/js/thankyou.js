const KEYWORD_DIMENSIONS = {
  minimalist: 'aesthetic', maximalist: 'aesthetic', classic: 'aesthetic',
  avant_garde: 'aesthetic', streetwear: 'aesthetic', bohemian: 'aesthetic',
  preppy: 'aesthetic', romantic: 'aesthetic', edgy: 'aesthetic',
  quiet_luxury: 'aesthetic', coastal: 'aesthetic', dark_academia: 'aesthetic',
  sporty: 'aesthetic', clean_girl: 'aesthetic', ballet_aesthetic: 'aesthetic',
  coquette_style: 'aesthetic', tomboy_chic: 'aesthetic', androgynous_look: 'aesthetic',
  soft_glamour: 'aesthetic', indie_style: 'aesthetic', coastal_grandmother: 'aesthetic',
  dopamine_dressing: 'aesthetic', quiet_opulence: 'aesthetic', power_dressing: 'aesthetic',
  artsy_downtown: 'aesthetic', retro_seventies: 'aesthetic', retro_nineties: 'aesthetic',
  y2k_inspired: 'aesthetic', futuristic_style: 'aesthetic', boho_luxe: 'aesthetic',
  mob_wife_glam: 'aesthetic', stealth_wealth: 'aesthetic', avant_minimalist: 'aesthetic',

  playful: 'mood', serious: 'mood', rebellious: 'mood', elegant: 'mood',
  laid_back: 'mood', bold: 'mood', understated: 'mood', whimsical: 'mood',
  polished: 'mood', raw: 'mood', dramatic: 'mood', ethereal: 'mood',
  sensual: 'mood', nostalgic: 'mood', futuristic_mood: 'mood',

  neutral: 'color', monochrome: 'color', earth_tones: 'color', pastel: 'color',
  bold_colors: 'color', black_forward: 'color', white_forward: 'color',
  jewel_tones: 'color', multicolor: 'color', neon_accent: 'color',
  pastel_rainbow: 'color', gradient_dye: 'color', burnout_print: 'color',
  ikat_pattern: 'color',
  burgundy_wine: 'color', camel_tan: 'color', cobalt_blue: 'color',
  forest_green: 'color', blush_pink: 'color', cream_ivory: 'color',
  olive_khaki: 'color', rust_orange: 'color', stone_grey: 'color',
  dusty_mauve: 'color', warm_taupe: 'color', slate_blue: 'color',
  powder_blue: 'color', mint_green: 'color', lilac_purple: 'color',
  sage_green: 'color', mustard_yellow: 'color', coral_pink: 'color',
  teal_green: 'color', charcoal_grey: 'color', navy_blue: 'color',
  silver_tone: 'color', golden_yellow: 'color', deep_purple: 'color',
  hot_pink: 'color', champagne_gold: 'color', midnight_blue: 'color',
  chocolate_brown: 'color', nude_pink: 'color', jade_green: 'color',
  indigo_blue: 'color', fuchsia_pink: 'color', lavender_haze: 'color',
  amber_gold: 'color', smoky_grey: 'color', copper_bronze: 'color',
  pearl_white: 'color', burnt_sienna: 'color',

  loungewear: 'formality', casual: 'formality', smart_casual: 'formality',
  business_casual: 'formality', formal: 'formality', black_tie: 'formality',

  parisian: 'cultural', scandinavian: 'cultural', italian_luxury: 'cultural',
  japanese_minimalist: 'cultural', american_prep: 'cultural',
  british_heritage: 'cultural', nyc_streetwear: 'cultural', californian: 'cultural',
  korean_minimal: 'cultural', french_riviera: 'cultural', milan_chic: 'cultural',
  mediterranean_style: 'cultural', australian_surf: 'cultural', east_london: 'cultural',
  tokyo_street: 'cultural', brooklyn_cool: 'cultural', porto_casual: 'cultural',
  rio_beach: 'cultural',

  fitted: 'silhouette', oversized: 'silhouette', structured: 'silhouette',
  flowy: 'silhouette', layered: 'silhouette', cropped: 'silhouette',
  voluminous: 'silhouette', wide_leg: 'silhouette', slim_cut: 'silhouette',
  high_waist: 'silhouette', low_rise: 'silhouette', relaxed_fit: 'silhouette',
  tailored_cut: 'silhouette', a_line: 'silhouette', shift_silhouette: 'silhouette',
  bodycon: 'silhouette', empire_waist: 'silhouette', pencil_cut: 'silhouette',
  column_silhouette: 'silhouette', cape_silhouette: 'silhouette',
  mermaid_cut: 'silhouette', trapeze_cut: 'silhouette', boxy_cut: 'silhouette',
  mini_length: 'silhouette', midi_length: 'silhouette', maxi_length: 'silhouette',
  wrap_style: 'silhouette', asymmetric_hem: 'silhouette', pleated: 'silhouette',
  ruched: 'silhouette', puff_sleeve: 'silhouette', balloon_sleeve: 'silhouette',
  off_shoulder: 'silhouette',
  crew_neck: 'silhouette', v_neck: 'silhouette', turtleneck: 'silhouette',
  crewneck: 'silhouette', boat_neck: 'silhouette', square_neck: 'silhouette',
  halter_neck: 'silhouette', cowl_neck: 'silhouette', strapless: 'silhouette',
  scoop_neck: 'silhouette', collar_detail: 'silhouette', deep_v: 'silhouette',
  mock_neck: 'silhouette', one_shoulder: 'silhouette', sweetheart_neckline: 'silhouette',
  long_sleeve: 'silhouette', short_sleeve: 'silhouette', sleeveless: 'silhouette',
  three_quarter: 'silhouette', cap_sleeve: 'silhouette', bell_sleeve: 'silhouette',
  raglan: 'silhouette', rolled_sleeve: 'silhouette', flutter_sleeve: 'silhouette',
  cold_shoulder: 'silhouette', three_quarter_sleeve: 'silhouette',
  raglan_sleeve: 'silhouette', dolman_sleeve: 'silhouette', dropped_shoulder: 'silhouette',

  everyday: 'occasion', workwear: 'occasion', going_out: 'occasion',
  travel: 'occasion', outdoor: 'occasion', sport: 'occasion',
  beach: 'occasion', occasion: 'occasion', date_night: 'occasion',
  brunch_casual: 'occasion', festival_wear: 'occasion', resort_wear: 'occasion',
  activewear: 'occasion', athleisure: 'occasion', evening_event: 'occasion',
  party_look: 'occasion', street_style: 'occasion', market_day: 'occasion',
  gallery_opening: 'occasion', weekend_errand: 'occasion', cocktail: 'occasion',
  brunch: 'occasion', office_ready: 'occasion', transitional: 'occasion',
  gym_wear: 'occasion', yoga_wear: 'occasion', running_wear: 'occasion',
  swim_wear: 'occasion', evening_wear: 'occasion', wedding_guest: 'occasion',
  party_wear: 'occasion', work_from_home: 'occasion', ski_wear: 'occasion',
  activewear_set: 'occasion', night_out: 'occasion', formal_occasion: 'occasion',
  capsule_piece: 'occasion', wardrobe_staple: 'occasion', statement_piece: 'occasion',

  sustainable: 'values', investment_piece: 'values', trend_driven: 'values',
  heritage_craft: 'values', luxury_status: 'values', budget_conscious: 'values',
  logo_forward: 'values', logo_free: 'values', size_inclusive: 'values',
  gender_neutral: 'values', performance_tech: 'values', artisan_made: 'values',
  limited_edition: 'values', capsule_wardrobe: 'values', slow_fashion: 'values',

  solid: 'pattern', stripes: 'pattern', check: 'pattern', floral: 'pattern',
  graphic: 'pattern', abstract: 'pattern', animal_print: 'pattern',
  paisley: 'pattern', polka_dot: 'pattern', tie_dye: 'pattern',
  camouflage: 'pattern', plaid: 'pattern', houndstooth: 'pattern',
  geometric_print: 'pattern', tropical_print: 'pattern', ditsy_floral: 'pattern',
  border_print: 'pattern', color_block: 'pattern', metallic_finish: 'pattern',
  sequin_embellish: 'pattern', lace_detail: 'pattern', embroidery_detail: 'pattern',
  fringe_trim: 'pattern', ruffle_detail: 'pattern',
  floral_print: 'pattern', striped_pattern: 'pattern', checked_pattern: 'pattern',
  solid_color: 'pattern', abstract_print: 'pattern', paisley_print: 'pattern',
  baroque_print: 'pattern', ombre_effect: 'pattern', fairisle_knit: 'pattern',
  argyle_pattern: 'pattern', colour_block: 'pattern', acid_wash: 'pattern',
  graphic_print: 'pattern', logo_repeat: 'pattern', leopard_spot: 'pattern',
  zebra_stripe: 'pattern', toile_print: 'pattern', damask_print: 'pattern',
  windowpane_check: 'pattern',

  denim: 'fabric', leather: 'fabric', knit: 'fabric', linen: 'fabric',
  velvet: 'fabric', satin: 'fabric', technical_fabric: 'fabric', cotton: 'fabric',
  silk: 'fabric', wool: 'fabric', cashmere: 'fabric', faux_leather: 'fabric',
  suede: 'fabric', nylon: 'fabric', polyester: 'fabric', chiffon: 'fabric',
  organza: 'fabric', jersey: 'fabric', fleece: 'fabric', corduroy: 'fabric',
  tweed: 'fabric', canvas: 'fabric', mesh_fabric: 'fabric', sequin_fabric: 'fabric',
  bamboo: 'fabric', hemp_fabric: 'fabric',
  smooth: 'fabric', textured: 'fabric', sheer: 'fabric', matte_finish: 'fabric',
  glossy: 'fabric', distressed: 'fabric', washed: 'fabric', crinkled: 'fabric',
  quilted: 'fabric', woven_detail: 'fabric', broderie_anglaise: 'fabric',
  crochet_knit: 'fabric', ribbed_knit: 'fabric', cable_knit: 'fabric',
  waffle_knit: 'fabric', open_weave: 'fabric', jacquard: 'fabric', brocade: 'fabric',
  denim_fabric: 'fabric', linen_fabric: 'fabric', velvet_fabric: 'fabric',
  satin_fabric: 'fabric', leather_fabric: 'fabric', knitwear_fabric: 'fabric',
  silk_fabric: 'fabric', cotton_fabric: 'fabric', modal_fabric: 'fabric',
  lyocell_fabric: 'fabric', viscose_fabric: 'fabric', wool_fabric: 'fabric',
  cashmere_fabric: 'fabric', suede_fabric: 'fabric', nylon_fabric: 'fabric',
  jersey_fabric: 'fabric', crepe_fabric: 'fabric', brocade_fabric: 'fabric',
  corduroy_fabric: 'fabric', organza_fabric: 'fabric', chiffon_fabric: 'fabric',
  poplin_fabric: 'fabric', flannel_fabric: 'fabric', fleece_fabric: 'fabric',
  recycled_fabric: 'fabric', stretch_fabric: 'fabric', sheer_fabric: 'fabric',
  mesh_detail: 'fabric', ribbed_texture: 'fabric', quilted_detail: 'fabric',
  faux_fur_trim: 'fabric', distressed_finish: 'fabric', woven_texture: 'fabric',
  jacquard_weave: 'fabric', burnout_effect: 'fabric', metallic_sheen: 'fabric',
  glitter_detail: 'fabric', sequin_embellishment: 'fabric', beaded_detail: 'fabric',
  laser_cut: 'fabric', perforated_detail: 'fabric', frayed_edge: 'fabric',
  brushed_finish: 'fabric', ruffled: 'fabric', belted: 'fabric',
  crochet_detail: 'fabric', embroidered_detail: 'fabric', pleated_detail: 'fabric',
  cutout_detail: 'fabric', tie_waist: 'fabric', button_front: 'fabric',
  double_breasted: 'fabric', single_breasted: 'fabric', zip_front: 'fabric',
  cargo_pockets: 'fabric', patch_pocket: 'fabric', chest_pocket: 'fabric',
  notch_lapel: 'fabric', mandarin_collar: 'fabric', shawl_collar: 'fabric',
  gathered_bodice: 'fabric', smocked_detail: 'fabric', pintuck_detail: 'fabric',
  shirred_detail: 'fabric', drawstring_waist: 'fabric', elastic_waist: 'fabric',
  corset_detail: 'fabric', gathered_waist: 'fabric', raw_edge_hem: 'fabric',
  lace_trim: 'fabric', contrast_stitch: 'fabric', open_back: 'fabric',
  gold_hardware: 'fabric', silver_hardware: 'fabric', chain_trim: 'fabric',
  buckle_detail: 'fabric', stud_embellishment: 'fabric', handmade_detail: 'fabric',
};

const DIMENSION_ORDER = [
  'aesthetic', 'color', 'mood', 'silhouette',
  'formality', 'cultural', 'occasion', 'values', 'pattern', 'fabric',
];

const DIMENSION_LABELS = {
  aesthetic: 'Aesthetic', mood: 'Mood', color: 'Color',
  silhouette: 'Silhouette', formality: 'Formality',
  cultural: 'Cultural', occasion: 'Occasion', values: 'Values',
  pattern: 'Pattern', fabric: 'Fabric & Texture',
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
