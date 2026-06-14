// ── ROSTER TAB ────────────────────────────────────────────────────────────────
let RCACHE = {};
let cRosterStatTab = 'overview';

const ROSTER_TIPS = {
  ppg:            'Points per game.',
  rebpg:          'Rebounds per game — offensive and defensive combined.',
  astpg:          'Assists per game.',
  stlpg:          'Steals per game.',
  blkpg:          'Blocks per game.',
  ts:             'True Shooting % — overall scoring efficiency accounting for 2PT, 3PT, and free throws. Formula: PTS / (2 × (FGA + 0.44 × FTA)).',
  efg:            'Effective FG% — weights 3-pointers appropriately. Formula: (FGM + 0.5 × 3PM) / FGA.',
  usage_pct:      'Usage % — share of team possessions used by this player while on the floor (shots, free throws, turnovers).',
  prpg:           "Torvik's PRPG! (PORPAGATU!) — offensive value added above replacement per game, adjusted for usage and opponent strength.",
  dprpg:          "Torvik's DPRPG! — defensive value added above replacement per game, adjusted for opponent strength.",
  bpm:            'Box Plus/Minus — overall on-court impact estimated from box score stats, measured in points per 100 possessions above average.',
  obpm:           'Off BPM — offensive component of Box Plus/Minus.',
  dbpm:           'Def BPM — defensive component of Box Plus/Minus.',
  ortg:           'Offensive Rating — points produced per 100 possessions used.',
  ortg_delta_team:'Offensive rating with this player on the floor vs. team avg. Positive = better than team avg.',
  drtg:           'Defensive Rating — points allowed per 100 possessions while on the floor. Lower is better.',
  drtg_delta_team:'Defensive rating with this player on the floor vs. team avg. Positive = better than team avg.',
  ppp_used:       'Points per possession used — accounts for FGA, free throw trips, and turnovers.',
  or_pct:         'Offensive Rebound % — share of available offensive rebounds secured while on the floor.',
  dr_pct:         'Defensive Rebound % — share of available defensive rebounds secured while on the floor.',
  ast_pct:        'Assist % — percentage of teammate made field goals assisted by this player while on the floor.',
  tov_pct:        'Turnover % — turnovers per possession used. Lower is better.',
  tov_sensitivity:'TOV Sensitivity — percentage of team possessions this player turns over. Formula: TOV% × Usage%.',
  blk_pct:        '% of opponent 2-point attempts blocked while this player is on the floor.',
  stl_pct:        '% of opponent possessions that end in a steal by this player.',
  ast_tov_ratio:  'Assist-to-turnover ratio. Higher is better for ball-handlers.',
  foul_sensitivity:'Fouls committed per minute played. Indicates foul risk — higher = more likely to foul out.',
  rim_rate:       'Rim attempt rate — dunks + close 2s as a share of total FGA. Higher = more paint presence.',
  rim_fg_pct:     'FG% at the rim — finishing efficiency on dunks and close 2-point attempts combined.',
  midrange_rate:  'Midrange attempt rate — long 2-point attempts as a share of total FGA.',
  midrange_fg_pct:'FG% on midrange shots.',
  three_rate:     '3-point attempt rate — 3PA as a share of total FGA.',
  three_fg_pct:   '3-point FG%.',
  ft_rate:        'Free throw rate — FTA per FGA. Measures how often the player draws fouls.',
  ft_pct:         'Free throw percentage.',
};

function fmtPct(v, decimals=1) {
  const n = parseFloat(v);
  if (isNaN(n) || v === null || v === undefined) return '—';
  return n.toFixed(decimals) + '%';
}
function fmtPctDec(v, decimals=1) {
  const n = parseFloat(v);
  if (isNaN(n) || v === null || v === undefined) return '—';
  return (n * 100).toFixed(decimals) + '%';
}
function fmtSign(v, decimals=1) {
  const n = parseFloat(v);
  if (isNaN(n) || v === null || v === undefined) return '—';
  return (n > 0 ? '+' : '') + n.toFixed(decimals);
}

function fmtMA(p, madeKey, attKey) {
  const m = parseFloat(p[madeKey]);
  const a = parseFloat(p[attKey]);
  if (isNaN(m) || isNaN(a)) return '—';
  return m.toFixed(1) + '/' + a.toFixed(1);
}

// Keys that are display strings — no percentile bar, white text
const STRING_KEYS = new Set([
  '_fg_ma','_rim_ma','_mid_ma','_three_ma','_ft_ma',
]);

const DRTG_DELTA_KEYS = new Set(['drtg_delta_team','drtg_delta_conf','drtg_delta_sub']);

const ROSTER_FROZEN = [
  {key:'name',             label:'Player',  stacked:false, frozen:true},
  {key:'position',         label:'Pos',     stacked:false, frozen:false},
  {key:'class',            label:'Yr',      stacked:false, frozen:false},
  {key:'height_in',        label:'Ht',      stacked:false, frozen:false, fmt: v => { const i=parseInt(v); return isNaN(i)?'—':Math.floor(i/12)+"'"+(i%12)+'"'; }},
  {key:'games',            label:'G',       stacked:false, frozen:false},
  {key:'minutes_per_game', label:'MPG',     stacked:false, frozen:false, fmt: v => parseFloat(v).toFixed(1)},
  {key:'usage_pct',        label:'USG%',    stacked:true,  frozen:false, fmt: v => fmtPct(v), pctKey:'usage_pct_pct'},
];

const ROSTER_STAT_TABS = {
  overview: [
    {key:'bpm',          label:'BPM',         fmt:v=>fmtSign(v)},
    {key:'obpm',         label:'Off\nBPM',    fmt:v=>fmtSign(v)},
    {key:'dbpm',         label:'Def\nBPM',    fmt:v=>fmtSign(v)},
    {key:'ppg',          label:'PTS/G',       fmt:v=>parseFloat(v).toFixed(1)},
    {key:'rebpg',        label:'REB/G',       fmt:v=>parseFloat(v).toFixed(1)},
    {key:'astpg',        label:'AST/G',       fmt:v=>parseFloat(v).toFixed(1)},
    {key:'stlpg',        label:'STL/G',       fmt:v=>parseFloat(v).toFixed(1)},
    {key:'blkpg',        label:'BLK/G',       fmt:v=>parseFloat(v).toFixed(1)},
  ],
  advanced: [
    {key:'prpg',             label:'PRPG',             fmt:v=>parseFloat(v).toFixed(2)},
    {key:'dprpg',            label:'DPRPG',            fmt:v=>parseFloat(v).toFixed(2)},
    {key:'ortg',             label:'Off Rtg',          fmt:v=>parseFloat(v).toFixed(1)},
    {key:'ortg_delta_team',  label:'Off Rtg\nvs Team', fmt:v=>fmtSign(v)},
    {key:'drtg',             label:'Def Rtg',          fmt:v=>parseFloat(v).toFixed(1)},
    {key:'drtg_delta_team',  label:'Def Rtg\nvs Team', fmt:v=>((-parseFloat(v))>0?'+':'')+(-parseFloat(v)).toFixed(1)},
    {key:'or_pct',           label:'OR%',              fmt:v=>fmtPct(v)},
    {key:'dr_pct',           label:'DR%',              fmt:v=>fmtPct(v)},
    {key:'ast_pct',          label:'AST%',             fmt:v=>fmtPct(v)},
    {key:'tov_pct',          label:'TOV%',             fmt:v=>fmtPct(v)},
    {key:'blk_pct',          label:'BLK%',             fmt:v=>fmtPct(v)},
    {key:'stl_pct',          label:'STL%',             fmt:v=>fmtPct(v)},
    {key:'ast_tov_ratio',    label:'AST/TOV',          fmt:v=>parseFloat(v).toFixed(2)},
    {key:'foul_sensitivity', label:'Foul\nSensitivity',fmt:v=>parseFloat(v).toFixed(2)},
  ],
  shooting: [
    {key:'ppp_used',        label:'PPP\nUsed',        fmt:v=>parseFloat(v).toFixed(3)},
    {key:'ts',              label:'TS%',              fmt:v=>fmtPct(v)},
    {key:'efg',             label:'eFG%',             fmt:v=>fmtPct(v)},
    {key:'total_fg_pct',    label:'FG%',              fmt:v=>fmtPctDec(v)},
    {key:'_fg_ma',          label:'FGM/\nFGA',        fmt:(v,p)=>fmtMA(p,'fgm_pg','fga_pg'), noBar:true, computed:true},
    {key:'rim_rate',        label:'Rim\nRate',        fmt:v=>fmtPctDec(v)},
    {key:'rim_fg_pct',      label:'Rim\nFG%',        fmt:v=>fmtPctDec(v)},
    {key:'_rim_ma',         label:'Rim\nFGM/FGA',    fmt:(v,p)=>fmtMA(p,'rim_made_pg','rim_att_pg'), noBar:true, computed:true},
    {key:'midrange_rate',   label:'Mid\nRate',        fmt:v=>fmtPctDec(v)},
    {key:'midrange_fg_pct', label:'Mid\nFG%',        fmt:v=>fmtPctDec(v)},
    {key:'_mid_ma',         label:'Mid\nFGM/FGA',    fmt:(v,p)=>fmtMA(p,'midrange_made_pg','midrange_att_pg'), noBar:true, computed:true},
    {key:'three_rate',      label:'3PT\nRate',        fmt:v=>fmtPctDec(v)},
    {key:'three_fg_pct',    label:'3PT%',             fmt:v=>fmtPctDec(v)},
    {key:'_three_ma',       label:'3PT\nFGM/FGA',    fmt:(v,p)=>fmtMA(p,'three_made_pg','three_att_pg'), noBar:true, computed:true},
    {key:'ft_rate',         label:'FT\nRate',         fmt:v=>fmtPctDec(v)},
    {key:'ft_pct',          label:'FT%',              fmt:v=>fmtPctDec(v)},
    {key:'_ft_ma',          label:'FTM/\nFTA',        fmt:(v,p)=>fmtMA(p,'ft_made_pg','ft_att_pg'), noBar:true, computed:true},
  ],
};

const MPG_TIER_LABELS = {
  'Core Player (26+ MPG)':       {label:'Core Rotation',       mpg:'26+ MPG',    color:'var(--accent)',  note:''},
  'Primary Rotation (18\u201326 MPG)':{label:'Primary Rotation',   mpg:'18\u201326 MPG', color:'var(--text2)',   note:''},
  'Bench Rotation (10\u201318 MPG)':  {label:'Bench Rotation',      mpg:'10\u201318 MPG', color:'var(--text2)',   note:''},
  'Fringe Rotation (5\u201310 MPG)':  {label:'Fringe Rotation',     mpg:'5\u201310 MPG',  color:'var(--text3)',   note:'Limited minutes \u2014 ranked on full-rotation scale (10+ MPG, 10+ games) \u00b7 5+ games required'},
  'End of Bench (0\u20135 MPG)':      {label:'End of Bench',        mpg:'0\u20135 MPG',   color:'var(--text4)',   note:'Too few minutes for reliable percentiles \u2014 raw stats only'},
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

async function renderRoster() {
  const wrap = document.getElementById('roster-content');
  const empty = document.getElementById('roster-empty');
  const loading = document.getElementById('roster-loading');
  if (!cTeam || !cYear) { wrap.style.display='none'; empty.style.display='flex'; return; }

  empty.style.display = 'none';
  loading.style.display = 'flex';
  wrap.style.display = 'none';
  const cw = document.getElementById('roster-controls-wrap');
  if (cw) cw.style.display = 'none';

  try {
    const players = await loadRoster(cTeam, cYear);
    loading.style.display = 'none';
    if (!players || players.length === 0) {
      empty.style.display = 'flex';
      empty.textContent = `No roster data for ${cTeam} in ${cYear}.`;
      return;
    }
    if (cw) cw.style.display = 'block';
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

function rosterPctCls(pct, isTier2) {
  const suffix = isTier2 ? '-muted' : '';
  if (pct >= 0.85) return 'pct-elite' + suffix;
  if (pct >= 0.65) return 'pct-good' + suffix;
  if (pct >= 0.40) return 'pct-avg' + suffix;
  if (pct >= 0.20) return 'pct-below' + suffix;
  return 'pct-poor' + suffix;
}

function rosterStackedCell(rawDisplay, pctVal, isTier2) {
  const pct = parseFloat(pctVal);
  if (isNaN(pct)) return `<span class="roster-raw-white">${rawDisplay}</span>`;
  const cls = rosterPctCls(pct, isTier2);
  const pctDisplay = Math.round(pct * 100);
  const barWidth = Math.round(pct * 100);
  return `<div class="roster-pct-cell${isTier2?' tier2-pct':''}">
    <span class="roster-raw-val ${cls}">${rawDisplay}</span>
    <div class="roster-pct-row">
      <span class="roster-pct-num ${cls}">${pctDisplay}</span>
      <div class="roster-pct-bar-wrap"><div class="roster-pct-bar ${cls}-bar" style="width:${barWidth}%"></div></div>
    </div>
  </div>`;
}

function renderRosterTable(playersArg) {
  const wrap = document.getElementById('roster-content');
  const key = `${cTeam}__${cYear}`;
  const players = playersArg || RCACHE[key];
  if (!players) return;

  const stats = ROSTER_STAT_TABS[cRosterStatTab];

  const tierOrder = [
    'Core Player (26+ MPG)',
    'Primary Rotation (18\u201326 MPG)',
    'Bench Rotation (10\u201318 MPG)',
    'Fringe Rotation (5\u201310 MPG)',
    'End of Bench (0\u20135 MPG)',
  ];
  const grouped = {};
  tierOrder.forEach(t => grouped[t] = []);
  players.forEach(p => {
    const t = p.mpg_tier || 'End of Bench (0\u20135 MPG)';
    if (!grouped[t]) grouped[t] = [];
    grouped[t].push(p);
  });

  const totalCols = ROSTER_FROZEN.length + stats.length;

  let html = `<div class="roster-scroll-wrap"><div class="roster-table-wrap"><table class="roster-table"><thead><tr>`;

  ROSTER_FROZEN.forEach(col => {
    const frozenStyle = col.frozen ? 'position:sticky;left:0;z-index:3;' : '';
    const thClass = col.frozen ? 'roster-frozen-th roster-name-th' : 'roster-frozen-th roster-scroll-th';
    html += `<th class="${thClass}" style="${frozenStyle}">${col.label}${col.stacked ? rosterTip(col.key) : ''}</th>`;
  });
  const totalStats = stats.length;
  stats.forEach((s, i) => {
    const lbl = s.label.replace('\n','<br>');
    const tipDir = i >= totalStats - 4 ? 'tip-left' : '';
    html += `<th class="roster-stat-th ${tipDir}">${lbl}${rosterTip(s.key)}</th>`;
  });
  html += `</tr></thead><tbody>`;

  tierOrder.forEach(tier => {
    const group = grouped[tier];
    if (!group || group.length === 0) return;
    const tierCfg = MPG_TIER_LABELS[tier] || {label:tier, mpg:'', color:'var(--text4)', note:''};

    const noteHtml = tierCfg.note
      ? `<span class="roster-tier-note">${tierCfg.note}</span>`
      : '';
    html += `<tr class="roster-tier-row">
      <td colspan="${totalCols}">
        <span class="roster-tier-label" style="color:${tierCfg.color}">${tierCfg.label}</span>
        <span class="roster-tier-mpg"> ${tierCfg.mpg}</span>
        ${noteHtml}
      </td>
    </tr>`;

    group.forEach(p => {
      const isTier2 = p.percentile_tier === 'Tier 2';
      const noPercentile = !p.percentile_eligible || p.percentile_eligible === 'False' || p.percentile_eligible === false;
      const rowCls = isTier2 ? 'roster-row roster-tier2' : 'roster-row';

      html += `<tr class="${rowCls}">`;

      ROSTER_FROZEN.forEach(col => {
        const val = p[col.key];
        const display = col.fmt ? col.fmt(val) : (val ?? '—');

        if (col.key === 'name') {
          html += `<td class="roster-frozen-td roster-name-cell" style="position:sticky;left:0;z-index:1;">${display}</td>`;
        } else if (col.stacked) {
          const pctKey = col.pctKey || (col.key + '_pct');
          const pctVal = p[pctKey];
          const cellContent = (noPercentile || pctVal === null || pctVal === undefined)
            ? `<span class="roster-raw-white">${display}</span>`
            : rosterStackedCell(display, pctVal, isTier2);
          html += `<td class="roster-frozen-td roster-scroll-td">${cellContent}</td>`;
        } else {
          html += `<td class="roster-frozen-td roster-scroll-td">${display ?? '—'}</td>`;
        }
      });

      stats.forEach(s => {
        const rawVal = p[s.key];
        const isString = STRING_KEYS.has(s.key) || s.noBar;

        if (isString) {
          const display = s.computed ? s.fmt(null, p) : (s.fmt ? s.fmt(rawVal) : (rawVal ?? '—'));
          html += `<td class="roster-stat-td"><span class="roster-raw-white">${display}</span></td>`;
          return;
        }

        const isDrtgDelta = DRTG_DELTA_KEYS.has(s.key);
        let display;
        if (isDrtgDelta) {
          const v = parseFloat(rawVal);
          display = isNaN(v) ? '—' : (((-v)>0?'+':'') + (-v).toFixed(1));
        } else {
          const v = parseFloat(rawVal);
          display = (isNaN(v) || rawVal === null || rawVal === undefined) ? '—' : s.fmt(rawVal);
        }

        const pctKey = s.pctKey || (s.key + '_pct');
        const pctVal = p[pctKey];
        const hasPct = pctVal !== undefined && pctVal !== null;

        if (noPercentile || !hasPct) {
          html += `<td class="roster-stat-td"><span class="roster-raw-white">${display}</span></td>`;
          return;
        }

        html += `<td class="roster-stat-td">${rosterStackedCell(display, pctVal, isTier2)}</td>`;
      });

      html += `</tr>`;
    });
  });

  html += `</tbody></table></div></div>`;
  wrap.innerHTML = html;
}
