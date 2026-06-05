// ── ROSTER TAB ────────────────────────────────────────────────────────────────
let RCACHE = {};
let cRosterStatTab = 'overview';
let cRosterDisplayMode = 'percentile'; // raw | percentile | rank

const ROSTER_TIPS = {
  // Overview
  ppg:            'Points per game.',
  rebpg:          'Rebounds per game — offensive and defensive combined.',
  astpg:          'Assists per game.',
  stlpg:          'Steals per game.',
  blkpg:          'Blocks per game.',
  ts:             'True Shooting % — overall scoring efficiency accounting for 2PT, 3PT, and free throws. Formula: PTS / (2 × (FGA + 0.44 × FTA)).',
  usage_pct:      'Usage % — share of team possessions used by this player while on the floor (shots, free throws, turnovers).',
  prpg:           "Torvik's PRPG! — total player rating per game, combining offensive and defensive value added above average.",
  bpm:            'Box Plus/Minus — overall on-court impact estimated from box score stats, measured in points per 100 possessions above average.',
  obpm:           'Offensive Box Plus/Minus — offensive component of BPM.',
  dbpm:           'Defensive Box Plus/Minus — defensive component of BPM.',
  // Role / Advanced
  ortg:           'Offensive Rating — points produced per 100 possessions used. Measures individual scoring and creation efficiency.',
  ortg_delta_team:'Player ORtg minus team adjusted offensive efficiency. Positive = player is more offensively efficient than his team overall.',
  drtg:           'Defensive Rating — points allowed per 100 possessions while the player is on the floor. Lower is better.',
  drtg_delta_team:'How many points per 100 possessions better this player defends relative to team average. Positive = better defender than team average. (Sign is flipped from raw DRtg — lower DRtg is better, so a negative delta becomes a positive display value.)',
  ppp_used:       'Points per possession used — total points scored divided by usage-weighted possessions. Measures scoring output on possessions this player ends.',
  or_pct:         'Offensive Rebound % — share of available offensive rebounds secured while on the floor.',
  dr_pct:         'Defensive Rebound % — share of available defensive rebounds secured while on the floor.',
  ast_pct:        'Assist % — percentage of teammate made field goals assisted by this player while on the floor.',
  tov_pct:        'Turnover % — turnovers per possession used. Lower is better.',
  blk_pct:        '% of opponent 2-point attempts blocked while this player is on the floor.',
  stl_pct:        '% of opponent possessions that end in a steal by this player.',
  ast_tov_ratio:  'Assist-to-turnover ratio. Measures playmaking efficiency — higher is better for ball-handlers.',
  foul_sensitivity:'Fouls committed per minute played (fc_40 / MPG). Indicates foul risk — players with high values are more likely to foul out or lose minutes.',
  // Shooting
  rim_rate:       'Rim attempt rate — rim attempts (dunks + close 2s) as a share of total FGA. Higher = more paint presence.',
  rim_fg_pct:     'FG% at the rim — finishing efficiency on dunks and close 2-point attempts combined.',
  midrange_rate:  'Midrange attempt rate — long 2-point attempts as a share of total FGA.',
  midrange_fg_pct:'FG% on midrange shots (long 2-point attempts).',
  three_rate:     '3-point attempt rate — 3PA as a share of total FGA.',
  three_fg_pct:   '3-point FG%.',
  three_att_pg:   '3-point attempts per game — measures perimeter volume.',
  ft_rate:        'Free throw rate — FTA per FGA. Measures how often the player draws fouls.',
  ft_pct:         'Free throw percentage.',
};


const ROSTER_FROZEN = [
  {key:'name',        label:'Player'},
  {key:'position',    label:'Pos'},
  {key:'class',       label:'Yr'},
  {key:'height_in',   label:'Ht',  fmt: v => { const i=parseInt(v); return isNaN(i)?'—':Math.floor(i/12)+"'"+(i%12)+'"'; }},
  {key:'games',       label:'G'},
  {key:'minutes_per_game', label:'MPG', fmt: v => parseFloat(v).toFixed(1)},
];

const ROSTER_STAT_TABS = {
  overview: [
    {key:'ppg',         label:'PTS/G',  fmt:v=>parseFloat(v).toFixed(1)},
    {key:'rebpg',       label:'REB/G',  fmt:v=>parseFloat(v).toFixed(1)},
    {key:'astpg',       label:'AST/G',  fmt:v=>parseFloat(v).toFixed(1)},
    {key:'stlpg',       label:'STL/G',  fmt:v=>parseFloat(v).toFixed(1)},
    {key:'blkpg',       label:'BLK/G',  fmt:v=>parseFloat(v).toFixed(1)},
    {key:'ts',          label:'TS%',    fmt:v=>fmtPct(v)},
    {key:'usage_pct',   label:'USG%',   fmt:v=>fmtPct(v)},
    {key:'prpg',        label:'PRPG',   fmt:v=>parseFloat(v).toFixed(2)},
    {key:'bpm',         label:'BPM',    fmt:v=>(parseFloat(v)>0?'+':'')+parseFloat(v).toFixed(1)},
    {key:'obpm',        label:'OBPM',   fmt:v=>(parseFloat(v)>0?'+':'')+parseFloat(v).toFixed(1)},
    {key:'dbpm',        label:'DBPM',   fmt:v=>(parseFloat(v)>0?'+':'')+parseFloat(v).toFixed(1)},
  ],
  advanced: [
    {key:'ortg',        label:'ORtg',   fmt:v=>parseFloat(v).toFixed(1)},
    {key:'ortg_delta_team', label:'ORtg vs Team', fmt:v=>(parseFloat(v)>0?'+':'')+parseFloat(v).toFixed(1)},
    {key:'drtg',        label:'DRtg',   fmt:v=>parseFloat(v).toFixed(1)},
    {key:'drtg_delta_team', label:'DRtg vs Team', fmt:v=>(parseFloat(v)>0?'+':'')+(-parseFloat(v)).toFixed(1)},
    {key:'ppp_used',    label:'PPP',    fmt:v=>parseFloat(v).toFixed(3)},
    {key:'or_pct',      label:'OR%',    fmt:v=>fmtPct(v)},
    {key:'dr_pct',      label:'DR%',    fmt:v=>fmtPct(v)},
    {key:'ast_pct',     label:'AST%',   fmt:v=>fmtPct(v)},
    {key:'tov_pct',     label:'TOV%',   fmt:v=>fmtPct(v)},
    {key:'blk_pct',     label:'BLK%',   fmt:v=>fmtPct(v)},
    {key:'stl_pct',     label:'STL%',   fmt:v=>fmtPct(v)},
    {key:'ast_tov_ratio',label:'A/T',   fmt:v=>parseFloat(v).toFixed(2)},
    {key:'foul_sensitivity', label:'Foul Sens', fmt:v=>parseFloat(v).toFixed(2)},
  ],
  shooting: [
    {key:'ts',          label:'TS%',    fmt:v=>fmtPct(v)},
    {key:'rim_rate',    label:'Rim Rate', fmt:v=>fmtPct(v), pctKey:'rim_rate_pct'},
    {key:'rim_fg_pct',  label:'Rim FG%', fmt:v=>fmtPct(v)},
    {key:'midrange_rate', label:'Mid Rate', fmt:v=>fmtPct(v)},
    {key:'midrange_fg_pct', label:'Mid FG%', fmt:v=>fmtPct(v)},
    {key:'three_rate',  label:'3PT Rate', fmt:v=>fmtPct(v)},
    {key:'three_fg_pct',label:'3PT%',   fmt:v=>fmtPct(v)},
    {key:'three_att_pg',label:'3PA/G',  fmt:v=>parseFloat(v).toFixed(1)},
    {key:'ft_rate',     label:'FT Rate', fmt:v=>fmtPct(v)},
    {key:'ft_pct',      label:'FT%',    fmt:v=>fmtPct(v)},
  ],
};

// Smart percentage formatter — handles both decimal (0.45) and whole-number (45.0) storage
function fmtPct(v, decimals=1) {
  const n = parseFloat(v);
  if (isNaN(n)) return '—';
  // If value > 1, already stored as percentage (e.g. 39.9 = 39.9%)
  // If value <= 1, stored as decimal (e.g. 0.399 = 39.9%)
  const pct = n > 1 ? n : n * 100;
  return pct.toFixed(decimals) + '%';
}

// Keys that have no percentile (display strings, deltas, etc)
const NO_PCT_KEYS = new Set([
  'rim_made_att_str','midrange_made_att_str',
  'three_made_att_str','ft_made_att_str','three_att_pg'
]);

// Lower is better for these keys (percentile color already handled by percentile direction in data)
const LOWER_BETTER = new Set(['drtg','tov_pct','foul_sensitivity']);

// drtg delta keys: flip sign on display so positive = better defense (easier for coaches)
const DRTG_DELTA_KEYS = new Set([
  'drtg_delta_team','drtg_delta_conf','drtg_delta_sub'
]);

const MPG_TIER_LABELS = {
  'Core Player (26+ MPG)':        {label:'Core Rotation (26+ MPG)',       color:'var(--accent)',  note:''},
  'Primary Rotation (18–26 MPG)':  {label:'Primary Rotation (18–26 MPG)', color:'var(--text2)',   note:''},
  'Bench Rotation (10–18 MPG)':    {label:'Bench Rotation (10–18 MPG)',   color:'var(--text3)',   note:''},
  'Fringe Rotation (5–10 MPG)':    {label:'Fringe Rotation (5–10 MPG)',   color:'var(--text4)',   note:'Limited sample — percentiles shown for reference, not direct comparison to full-rotation players'},
  'End of Bench (0–5 MPG)':        {label:'End of Bench (0–5 MPG)',       color:'var(--text4)',   note:'Too few minutes for reliable percentiles — raw stats only'},
};

async function loadRoster(team, year) {
  const key = `${team}__${year}`;
  if (RCACHE[key]) return RCACHE[key];
  const r = await fetch(`player_data/layer1_rosters/rosters_${year}.json`);
  const data = await r.json();
  RCACHE[key] = data[team] || [];
  return RCACHE[key];
}

function setRosterStatTab(tab, btn) {
  cRosterStatTab = tab;
  document.querySelectorAll('#roster-stat-tabs .hist-cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (cTeam && cYear) renderRosterTable();
}

function setRosterDisplayMode(mode, btn) {
  cRosterDisplayMode = mode;
  document.querySelectorAll('#roster-display-toggle .view-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (cTeam && cYear) renderRosterTable();
}

async function renderRoster() {
  const wrap = document.getElementById('roster-content');
  const empty = document.getElementById('roster-empty');
  const loading = document.getElementById('roster-loading');
  if (!cTeam || !cYear) { wrap.style.display='none'; empty.style.display='flex'; return; }

  empty.style.display = 'none';
  loading.style.display = 'flex';
  wrap.style.display = 'none';

  try {
    const players = await loadRoster(cTeam, cYear);
    loading.style.display = 'none';
    if (!players || players.length === 0) {
      empty.style.display = 'flex';
      empty.textContent = `No roster data for ${cTeam} in ${cYear}.`;
      return;
    }
    const controlsWrap = document.getElementById('roster-controls-wrap');
    if (controlsWrap) controlsWrap.style.display = 'block';
    wrap.style.display = 'block';
    renderRosterTable(players);
  } catch(e) {
    loading.style.display = 'none';
    empty.style.display = 'flex';
    empty.textContent = 'Error loading roster: ' + e.message;
  }
}


function rosterTip(key) {
  const t = ROSTER_TIPS[key];
  if (!t) return '';
  return `<span class="info-icon" onclick="toggleTip(event,this)" style="margin-left:3px">i<span class="tooltip">${t}</span></span>`;
}

function renderRosterTable(playersArg) {
  const wrap = document.getElementById('roster-content');
  const key = `${cTeam}__${cYear}`;
  const players = playersArg || RCACHE[key];
  if (!players) return;

  const stats = ROSTER_STAT_TABS[cRosterStatTab];
  const mode = cRosterDisplayMode;

  // Group by MPG tier
  const tierOrder = ['Core Player (26+ MPG)','Primary Rotation (18–26 MPG)','Bench Rotation (10–18 MPG)','Fringe Rotation (5–10 MPG)','End of Bench (0–5 MPG)'];
  const grouped = {};
  tierOrder.forEach(t => grouped[t] = []);
  players.forEach(p => {
    const t = p.mpg_tier || 'End of Bench';
    if (!grouped[t]) grouped[t] = [];
    grouped[t].push(p);
  });

  // Build table
  let html = `<div class="roster-table-wrap">
    <table class="roster-table">
      <thead><tr>`;

  // Frozen headers
  ROSTER_FROZEN.forEach(col => {
    html += `<th class="roster-frozen-th">${col.label}</th>`;
  });
  // Stat headers
  stats.forEach(s => {
    html += `<th class="roster-stat-th">${s.label}${rosterTip(s.key)}</th>`;
  });
  html += `</tr></thead><tbody>`;

  // Rows by tier
  tierOrder.forEach(tier => {
    const group = grouped[tier];
    if (!group || group.length === 0) return;
    const tierCfg = MPG_TIER_LABELS[tier] || {label: tier, color: 'var(--text4)'};

    // Tier separator row
    const tierNote = tierCfg.note
      ? `<span class="roster-tier-note">${tierCfg.note}</span>`
      : '';
    html += `<tr class="roster-tier-row">
      <td colspan="${ROSTER_FROZEN.length + stats.length}" style="color:${tierCfg.color}">
        ${tierCfg.label}${tierNote}
      </td>
    </tr>`;

    group.forEach(p => {
      const isTier2 = p.percentile_tier === 'Tier 2';
      const noPercentile = !p.percentile_eligible;
      const rowCls = isTier2 ? 'roster-row roster-tier2' : 'roster-row';

      html += `<tr class="${rowCls}">`;

      // Frozen cells
      ROSTER_FROZEN.forEach(col => {
        let val = p[col.key];
        let display = col.fmt ? col.fmt(val) : (val ?? '—');
        if (col.key === 'name') {
          const tier2mark = isTier2 ? '<span class="roster-tier2-mark" title="Limited minutes — percentiles on Tier 1 scale">*</span>' : '';
          html += `<td class="roster-frozen-td roster-name-cell">${display}${tier2mark}</td>`;
        } else {
          html += `<td class="roster-frozen-td">${display ?? '—'}</td>`;
        }
      });

      // Stat cells
      stats.forEach(s => {
        html += `<td class="roster-stat-td">${rosterStatCell(p, s, mode, noPercentile, isTier2)}</td>`;
      });

      html += `</tr>`;
    });
  });

  html += `</tbody></table></div>`;

  // Tier 2 footnote removed — info is in tier header row

  wrap.innerHTML = html;
}

function rosterStatCell(p, stat, mode, noPercentile, isTier2) {
  const rawVal = p[stat.key];
  const pctKey = stat.pctKey || (stat.key + '_pct');
  const rankKey = stat.key + '_rank'; // not in layer1 but graceful fallback
  const hasPct = !NO_PCT_KEYS.has(stat.key) && p[pctKey] !== undefined && p[pctKey] !== null;

  const isDrtgDelta = DRTG_DELTA_KEYS.has(stat.key);
  const fmtRaw = () => {
    const v = parseFloat(rawVal);
    if (isNaN(v) || rawVal === null || rawVal === undefined) return '—';
    // drtg delta: flip sign so positive = better defense
    if (isDrtgDelta) {
      const flipped = -v;
      return (flipped > 0 ? '+' : '') + flipped.toFixed(1);
    }
    return stat.fmt(rawVal);
  };

  if (mode === 'raw' || noPercentile || !hasPct) {
    return `<span class="roster-raw">${fmtRaw()}</span>`;
  }

  const pct = parseFloat(p[pctKey]);
  if (isNaN(pct)) return `<span class="roster-raw">${fmtRaw()}</span>`;

  if (mode === 'percentile') {
    const cls = rosterPctCls(pct, isTier2);
    const pctDisplay = Math.round(pct * 100);
    const barWidth = Math.round(pct * 100);
    return `<div class="roster-pct-cell ${isTier2 ? 'tier2-pct' : ''}">
      <span class="roster-pct-val ${cls}">${pctDisplay}</span>
      <div class="roster-pct-bar-wrap"><div class="roster-pct-bar ${cls}-bar" style="width:${barWidth}%"></div></div>
    </div>`;
  }

  if (mode === 'rank') {
    // Layer1 doesn't have rank, derive from percentile tier label
    const cls = rosterPctCls(pct, isTier2);
    const pctDisplay = Math.round(pct * 100);
    return `<span class="roster-raw ${cls}">${pctDisplay}%</span>`;
  }

  return `<span class="roster-raw">${fmtRaw()}</span>`;
}

function rosterPctCls(pct, isTier2) {
  const suffix = isTier2 ? '-muted' : '';
  if (pct >= 0.85) return 'pct-elite' + suffix;
  if (pct >= 0.65) return 'pct-good' + suffix;
  if (pct >= 0.40) return 'pct-avg' + suffix;
  if (pct >= 0.20) return 'pct-below' + suffix;
  return 'pct-poor' + suffix;
}
