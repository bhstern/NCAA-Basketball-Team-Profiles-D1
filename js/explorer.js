// ── PLAYER EXPLORER ───────────────────────────────────────────────────────────
let EXPLORER_CACHE = {};
let cExplorerYear = 2026;
let cExplorerStatTab = 'overview';
let cExplorerPctContext = 'national';
let cExplorerSort = {key: 'bpm', dir: 'desc'};
let cExplorerStatFilters = [];
let cExplorerData = [];
let cExplorerFiltered = [];

// Default sort per tab
const TAB_DEFAULT_SORT = {
  overview: 'bpm',
  advanced: 'ppp_used',
  shooting: 'ts',
  per40:    'pts_per_40',
  context:  'ortg_delta_team',
};

// ── TOOLTIPS ─────────────────────────────────────────────────────────────────
const EXPLORER_TIPS = {
  ppg:'Points per game.',
  rebpg:'Rebounds per game.',
  astpg:'Assists per game.',
  stlpg:'Steals per game.',
  blkpg:'Blocks per game.',
  ts:'True Shooting % — overall scoring efficiency accounting for 2PT, 3PT, and free throws.',
  efg:'Effective FG% — weights 3-pointers appropriately. Formula: (FGM + 0.5×3PM) / FGA.',
  usage_pct:'Usage % — share of team possessions used while on the floor.',
  prpg:"Torvik's PRPG! — total player rating per game.",
  oprpg:"Torvik's Offensive PRPG — offensive value added per game.",
  dprpg:"Torvik's Defensive PRPG — defensive value added per game.",
  bpm:'Box Plus/Minus — overall on-court impact per 100 possessions above average.',
  obpm:'Offensive Box Plus/Minus.',
  dbpm:'Defensive Box Plus/Minus.',
  ortg:'Offensive Rating — points produced per 100 possessions used.',
  ortg_delta_team:'Player ORtg minus team adjusted offense. Positive = more efficient than team.',
  drtg:'Defensive Rating — points allowed per 100 possessions. Lower is better.',
  drtg_delta_team:'How many pts/100 better this player defends vs team average. Positive = better than team.',
  ppp_used:'Points per possession used — scoring efficiency on possessions this player ends.',
  or_pct:'Offensive Rebound % — share of available ORBs secured.',
  dr_pct:'Defensive Rebound % — share of available DRBs secured.',
  ast_pct:'Assist % — % of teammate FGs assisted while on floor.',
  tov_pct:'Turnover % — turnovers per possession used. Lower is better.',
  tov_sensitivity:'Turnover % × usage — how damaging turnovers are given this player\'s role.',
  blk_pct:'% of opponent 2PT attempts blocked.',
  stl_pct:'% of opponent possessions ending in a steal.',
  ast_tov_ratio:'Assist-to-turnover ratio.',
  foul_sensitivity:'Fouls per minute played. Higher = more foul risk.',
  total_fg_pct:'Overall FG% across all shot types.',
  two_fg_pct:'2-point FG%.',
  rim_rate:'Rim attempt rate — dunks + close 2s as share of total FGA.',
  rim_fg_pct:'FG% at the rim — dunks + close 2s combined.',
  close_two_rate:'Close 2-point attempt rate (non-dunk rim attempts) as share of total FGA.',
  close_two_fg_pct:'FG% on close 2-point attempts (non-dunk).',
  dunk_rate:'Dunk attempt rate as share of total FGA.',
  dunk_fg_pct:'FG% on dunk attempts.',
  midrange_rate:'Midrange attempt rate as share of total FGA.',
  midrange_fg_pct:'Midrange FG%.',
  three_rate:'3-point attempt rate as share of total FGA.',
  three_fg_pct:'3-point FG%.',
  three_p_per_100:'3-point attempts per 100 possessions.',
  ft_rate:'Free throw rate — FTA per FGA.',
  ft_pct:'Free throw percentage.',
  close_vs_mid_ratio:'Rim attempts / midrange attempts. Higher = more paint-oriented.',
  rim_vs_three_ratio:'Rim attempts / 3PT attempts. Higher = more rim pressure vs perimeter.',
  pts_per_40:'Points per 40 minutes — scoring volume normalized for playing time.',
  reb_per_40:'Rebounds per 40 minutes.',
  ast_per_40:'Assists per 40 minutes.',
  stl_per_40:'Steals per 40 minutes.',
  blk_per_40:'Blocks per 40 minutes.',
  stocks_per_40:'Steals + blocks per 40 minutes — total defensive activity.',
  fc_40:'Fouls committed per 40 minutes.',
  ortg_delta_conf:'Player ORtg minus conference average offense.',
  drtg_delta_conf:'How many pts/100 better this player defends vs conference average.',
  ortg_delta_sub:'Player ORtg minus Power/Mid-Major average offense.',
  drtg_delta_sub:'How many pts/100 better this player defends vs Power/Mid-Major average.',
  ts_delta_team:'Player TS% minus team TS%.',
  ts_delta_conf:'Player TS% minus conference average TS%.',
  ts_delta_sub:'Player TS% minus Power/Mid-Major average TS%.',
  efg_delta_team:'Player eFG% minus team eFG%.',
  efg_delta_conf:'Player eFG% minus conference average eFG%.',
  efg_delta_sub:'Player eFG% minus Power/Mid-Major average eFG%.',
  rim_rate_delta_team:'Player rim rate minus team rim rate.',
  rim_rate_delta_conf:'Player rim rate minus conference average rim rate.',
  rim_rate_delta_sub:'Player rim rate minus Power/Mid-Major average rim rate.',
  three_rate_delta_team:'Player 3PT rate minus team 3PT rate.',
  three_rate_delta_conf:'Player 3PT rate minus conference average 3PT rate.',
  three_rate_delta_sub:'Player 3PT rate minus Power/Mid-Major average 3PT rate.',
  recruit_rank_clean:'Recruit Score (0-99) — Torvik recruit rating. 99 = highest rated recruit. 0 or blank = unranked.',
  age:'Player age on Feb 1 of the season.',
  years_in_d1:'Years of D1 experience.',
};

// ── PCT CONTEXT SUFFIX MAP ────────────────────────────────────────────────────
const PCT_SUFFIX = {
  national: '_pct',
  conf:     '_conf_pct',
  sub:      '_sub_pct',
  pos:      '_pos_pct',
  pos_conf: '_pos_conf_pct',
  pos_sub:  '_pos_sub_pct',
};

// ── FORMATTERS ────────────────────────────────────────────────────────────────
function fmtPctE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v===null||v===undefined)return'—';return n.toFixed(d)+'%';}
function fmtPctDecE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v===null||v===undefined)return'—';return(n*100).toFixed(d)+'%';}
function fmtSignE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v===null||v===undefined)return'—';return(n>0?'+':'')+n.toFixed(d);}
function fmtMAE(p,mKey,aKey){const m=parseFloat(p[mKey]),a=parseFloat(p[aKey]);if(isNaN(m)||isNaN(a))return'—';return m.toFixed(1)+'/'+a.toFixed(1);}
function fmtNumE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v===null||v===undefined)return'—';return n.toFixed(d);}

const DRTG_DELTA_KEYS_E = new Set(['drtg_delta_team','drtg_delta_conf','drtg_delta_sub']);
const STRING_KEYS_E = new Set(['_fgm_fga','_two_ma','_rim_ma','_close_two_ma','_dunk_ma','_mid_ma','_three_ma','_ft_ma']);

// ── STAT TABS ─────────────────────────────────────────────────────────────────
const EXPLORER_STAT_TABS = {
  overview: [
    {key:'bpm',       label:'BPM',           fmt:v=>fmtSignE(v)},
    {key:'obpm',      label:'Off\nBPM',      fmt:v=>fmtSignE(v)},
    {key:'dbpm',      label:'Def\nBPM',      fmt:v=>fmtSignE(v)},
    {key:'prpg',      label:'PRPG',          fmt:v=>fmtNumE(v,2)},
    {key:'oprpg',     label:'Off\nPRPG',     fmt:v=>fmtNumE(v,2)},
    {key:'dprpg',     label:'Def\nPRPG',     fmt:v=>fmtNumE(v,2)},
    {key:'ppg',       label:'PTS/G',         fmt:v=>fmtNumE(v)},
    {key:'rebpg',     label:'REB/G',         fmt:v=>fmtNumE(v)},
    {key:'astpg',     label:'AST/G',         fmt:v=>fmtNumE(v)},
    {key:'stlpg',     label:'STL/G',         fmt:v=>fmtNumE(v)},
    {key:'blkpg',     label:'BLK/G',         fmt:v=>fmtNumE(v)},
    {key:'ts',        label:'TS%',           fmt:v=>fmtPctE(v)},
    {key:'usage_pct', label:'USG%',          fmt:v=>fmtPctE(v)},
  ],
  advanced: [
    {key:'ppp_used',         label:'PPP\nUsed',          fmt:v=>fmtNumE(v,3)},
    {key:'ortg',             label:'Off\nRtg',           fmt:v=>fmtNumE(v,1)},
    {key:'ortg_delta_team',  label:'Off Rtg\nvs Team',   fmt:v=>fmtSignE(v)},
    {key:'drtg',             label:'Def\nRtg',           fmt:v=>fmtNumE(v,1)},
    {key:'drtg_delta_team',  label:'Def Rtg\nvs Team',   fmt:v=>((-parseFloat(v))>0?'+':'')+(-parseFloat(v)).toFixed(1)},
    {key:'efg',              label:'eFG%',               fmt:v=>fmtPctE(v)},
    {key:'or_pct',           label:'OR%',                fmt:v=>fmtPctE(v)},
    {key:'dr_pct',           label:'DR%',                fmt:v=>fmtPctE(v)},
    {key:'ast_pct',          label:'AST%',               fmt:v=>fmtPctE(v)},
    {key:'tov_pct',          label:'TOV%',               fmt:v=>fmtPctE(v)},
    {key:'ast_tov_ratio',    label:'AST/\nTOV',          fmt:v=>fmtNumE(v,2)},
    {key:'tov_sensitivity',  label:'TOV\nSensitivity',   fmt:v=>fmtNumE(v,3)},
    {key:'blk_pct',          label:'BLK%',               fmt:v=>fmtPctE(v)},
    {key:'stl_pct',          label:'STL%',               fmt:v=>fmtPctE(v)},
    {key:'foul_sensitivity', label:'Foul\nSensitivity',  fmt:v=>fmtNumE(v,2)},
  ],
  shooting: [
    // Overall
    {key:'ts',              label:'TS%',                fmt:v=>fmtPctE(v),    section:'Overall'},
    {key:'efg',             label:'eFG%',               fmt:v=>fmtPctE(v),    section:'Overall'},
    {key:'total_fg_pct',    label:'FG%',                fmt:v=>fmtPctDecE(v), section:'Overall'},
    {key:'_fgm_fga',        label:'FGM/\nFGA',          fmt:(v,p)=>fmtMAE(p,'fgm_pg','fga_pg'), noBar:true, computed:true, section:'Overall'},
    {key:'two_fg_pct',      label:'2PT\nFG%',           fmt:v=>fmtPctDecE(v), section:'Overall'},
    {key:'_two_ma',         label:'2PT\nFGM/FGA',       fmt:(v,p)=>fmtMAE(p,'two_made_pg','two_att_pg'), noBar:true, computed:true, section:'Overall'},
    // 3PT
    {key:'three_rate',      label:'3PT\nRate',          fmt:v=>fmtPctDecE(v), section:'3PT'},
    {key:'three_fg_pct',    label:'3PT%',               fmt:v=>fmtPctDecE(v), section:'3PT'},
    {key:'_three_ma',       label:'3PT\nFGM/FGA',       fmt:(v,p)=>fmtMAE(p,'three_made_pg','three_att_pg'), noBar:true, computed:true, section:'3PT'},
    {key:'three_p_per_100', label:'3PA/\n100',          fmt:v=>fmtNumE(v,1),  section:'3PT'},
    // Rim
    {key:'rim_rate',        label:'Rim\nRate',          fmt:v=>fmtPctDecE(v), section:'Rim'},
    {key:'rim_fg_pct',      label:'Rim\nFG%',           fmt:v=>fmtPctDecE(v), section:'Rim'},
    {key:'_rim_ma',         label:'Rim\nFGM/FGA',       fmt:(v,p)=>fmtMAE(p,'rim_made_pg','rim_att_pg'), noBar:true, computed:true, section:'Rim'},
    {key:'close_two_rate',  label:'Close 2\nRate',      fmt:v=>fmtPctDecE(v), section:'Rim'},
    {key:'close_two_fg_pct',label:'Close 2\nFG%',       fmt:v=>fmtPctDecE(v), section:'Rim'},
    {key:'_close_two_ma',   label:'Close 2\nFGM/FGA',   fmt:(v,p)=>fmtMAE(p,'close_two_made_pg','close_two_att_pg'), noBar:true, computed:true, section:'Rim'},
    {key:'dunk_rate',       label:'Dunk\nRate',         fmt:v=>fmtPctDecE(v), section:'Rim'},
    {key:'dunk_fg_pct',     label:'Dunk\nFG%',          fmt:v=>fmtPctDecE(v), section:'Rim'},
    {key:'_dunk_ma',        label:'Dunk\nFGM/FGA',      fmt:(v,p)=>fmtMAE(p,'dunk_made_pg','dunk_att_pg'), noBar:true, computed:true, section:'Rim'},
    // Midrange
    {key:'midrange_rate',   label:'Midrange\nRate',     fmt:v=>fmtPctDecE(v), section:'Midrange'},
    {key:'midrange_fg_pct', label:'Midrange\nFG%',      fmt:v=>fmtPctDecE(v), section:'Midrange'},
    {key:'_mid_ma',         label:'Midrange\nFGM/FGA',  fmt:(v,p)=>fmtMAE(p,'midrange_made_pg','midrange_att_pg'), noBar:true, computed:true, section:'Midrange'},
    // FT
    {key:'ft_rate',         label:'FT\nRate',           fmt:v=>fmtPctDecE(v), section:'FT'},
    {key:'ft_pct',          label:'FT%',                fmt:v=>fmtPctDecE(v), section:'FT'},
    {key:'_ft_ma',          label:'FTM/\nFTA',          fmt:(v,p)=>fmtMAE(p,'ft_made_pg','ft_att_pg'), noBar:true, computed:true, section:'FT'},
    // Ratios
    {key:'close_vs_mid_ratio', label:'Rim/\nMid',       fmt:v=>fmtNumE(v,2),  section:'Ratios'},
    {key:'rim_vs_three_ratio', label:'Rim/\n3PT',       fmt:v=>fmtNumE(v,2),  section:'Ratios'},
  ],
  per40: [
    {key:'pts_per_40',    label:'PTS\n/40',     fmt:v=>fmtNumE(v)},
    {key:'reb_per_40',    label:'REB\n/40',     fmt:v=>fmtNumE(v)},
    {key:'ast_per_40',    label:'AST\n/40',     fmt:v=>fmtNumE(v)},
    {key:'stl_per_40',    label:'STL\n/40',     fmt:v=>fmtNumE(v)},
    {key:'blk_per_40',    label:'BLK\n/40',     fmt:v=>fmtNumE(v)},
    {key:'stocks_per_40', label:'Stocks\n/40',  fmt:v=>fmtNumE(v)},
    {key:'fc_40',         label:'FC\n/40',      fmt:v=>fmtNumE(v,2)},
  ],
  context: [
    // vs Team
    {key:'ortg_delta_team',       label:'Off Rtg\nvs Team',    fmt:v=>fmtSignE(v)},
    {key:'drtg_delta_team',       label:'Def Rtg\nvs Team',    fmt:v=>((-parseFloat(v))>0?'+':'')+(-parseFloat(v)).toFixed(1)},
    {key:'ts_delta_team',         label:'TS%\nvs Team',        fmt:v=>fmtSignE(v,2)},
    {key:'efg_delta_team',        label:'eFG%\nvs Team',       fmt:v=>fmtSignE(v,2)},
    {key:'rim_rate_delta_team',   label:'Rim\nvs Team',        fmt:v=>fmtSignE(v,2)},
    {key:'three_rate_delta_team', label:'3PT\nvs Team',        fmt:v=>fmtSignE(v,2)},
    // vs Conference
    {key:'ortg_delta_conf',       label:'Off Rtg\nvs Conf',    fmt:v=>fmtSignE(v)},
    {key:'drtg_delta_conf',       label:'Def Rtg\nvs Conf',    fmt:v=>((-parseFloat(v))>0?'+':'')+(-parseFloat(v)).toFixed(1)},
    {key:'ts_delta_conf',         label:'TS%\nvs Conf',        fmt:v=>fmtSignE(v,2)},
    {key:'efg_delta_conf',        label:'eFG%\nvs Conf',       fmt:v=>fmtSignE(v,2)},
    {key:'rim_rate_delta_conf',   label:'Rim\nvs Conf',        fmt:v=>fmtSignE(v,2)},
    {key:'three_rate_delta_conf', label:'3PT\nvs Conf',        fmt:v=>fmtSignE(v,2)},
    // vs Sub (Power/Mid)
    {key:'ortg_delta_sub',        label:'Off Rtg\nvs Sub',     fmt:v=>fmtSignE(v)},
    {key:'drtg_delta_sub',        label:'Def Rtg\nvs Sub',     fmt:v=>((-parseFloat(v))>0?'+':'')+(-parseFloat(v)).toFixed(1)},
    {key:'ts_delta_sub',          label:'TS%\nvs Sub',         fmt:v=>fmtSignE(v,2)},
    {key:'efg_delta_sub',         label:'eFG%\nvs Sub',        fmt:v=>fmtSignE(v,2)},
    {key:'rim_rate_delta_sub',    label:'Rim\nvs Sub',         fmt:v=>fmtSignE(v,2)},
    {key:'three_rate_delta_sub',  label:'3PT\nvs Sub',         fmt:v=>fmtSignE(v,2)},
  ],
};

// ── FROZEN IDENTITY COLUMNS ───────────────────────────────────────────────────
const EXPLORER_FROZEN = [
  {key:'name',              label:'Player',              frozen:true,  width:160, left:32,  fmt:v=>v??'—'},
  {key:'team',              label:'Team',                frozen:true,  width:130, left:192, fmt:v=>v??'—'},
  {key:'position',          label:'Pos',                 frozen:true,  width:55,  left:322, fmt:v=>v??'—'},
  {key:'class',             label:'Yr',                  frozen:false, fmt:v=>v??'—'},
  {key:'height_in',         label:'Ht',                  frozen:false, fmt:v=>{const i=parseInt(v);return isNaN(i)?'—':Math.floor(i/12)+"'"+(i%12)+'"';}},
  {key:'games',             label:'G',                   frozen:false, fmt:v=>v??'—'},
  {key:'minutes_per_game',  label:'MPG',                 frozen:false, fmt:v=>fmtNumE(v)},
  {key:'age',               label:'Age',                 frozen:false, fmt:v=>fmtNumE(v,1)},
  {key:'recruit_rank_clean',label:'Recruit\nScore',      frozen:false, fmt:v=>(v&&!isNaN(v))?parseInt(v):'—'},
  {key:'years_in_d1',       label:'Yrs\nD1',             frozen:false, fmt:v=>v??'—'},
];

// ── LOAD ──────────────────────────────────────────────────────────────────────
async function loadExplorerYear(year) {
  if (EXPLORER_CACHE[year]) return EXPLORER_CACHE[year];
  const r = await fetch(`player_data/layer2_explorer/players_${year}.json`);
  const data = await r.json();
  EXPLORER_CACHE[year] = data;
  return data;
}

// ── INIT ──────────────────────────────────────────────────────────────────────
async function initExplorer() {
  const yearSel = document.getElementById('explorer-year-select');
  if (!yearSel) return;

  if (yearSel.options.length === 0) {
    const years = [2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016];
    yearSel.innerHTML = years.map(y => `<option value="${y}" ${y===2026?'selected':''}>${yLabel(y)}</option>`).join('');
  }

  const year = parseInt(yearSel.value) || 2026;
  if (cExplorerData.length > 0 && cExplorerYear === year) {
    renderExplorerTable();
    return;
  }

  await loadAndRenderExplorer();
}

async function loadAndRenderExplorer() {
  const wrap = document.getElementById('explorer-table-wrap');
  const empty = document.getElementById('explorer-empty');
  const loading = document.getElementById('explorer-loading');

  empty.style.display = 'none';
  loading.style.display = 'flex';
  wrap.style.display = 'none';

  try {
    const year = parseInt(document.getElementById('explorer-year-select').value);
    cExplorerYear = year;
    cExplorerData = await loadExplorerYear(year);
    initMultiFilters(cExplorerData);
    applyExplorerFilters();
    loading.style.display = 'none';
    wrap.style.display = 'block';
    renderExplorerTable();
  } catch(e) {
    loading.style.display = 'none';
    empty.style.display = 'flex';
    empty.textContent = 'Error loading player data: ' + e.message;
  }
}

// ── FILTERS ───────────────────────────────────────────────────────────────────
function applyExplorerFilters() {
  let data = [...cExplorerData];

  const pos  = document.getElementById('ef-position')?.value;
  const conf = document.getElementById('ef-conference')?.value;
  const sub  = document.getElementById('ef-sub')?.value;
  const cls  = document.getElementById('ef-class')?.value;
  const tier = document.getElementById('ef-tier')?.value;
  const role = document.getElementById('ef-role')?.value;
  const yrsD1 = document.getElementById('ef-years-d1')?.value;

  if (pos)  data = data.filter(p => p.position === pos);
  if (conf) data = data.filter(p => p.conference === conf);
  if (sub)  data = data.filter(p => p.power_mid === sub);
  if (cls)  data = data.filter(p => p.class === cls);
  if (role) data = data.filter(p => p.role === role);
  if (yrsD1) data = data.filter(p => parseInt(p.years_in_d1) >= parseInt(yrsD1));

  // Tier filter — default excludes End of Bench
  const defaultTiers = new Set([
    'Core Player (26+ MPG)',
    'Primary Rotation (18\u201326 MPG)',
    'Bench Rotation (10\u201318 MPG)',
    'Fringe Rotation (5\u201310 MPG)',
  ]);
  if (tier) {
    data = data.filter(p => p.mpg_tier === tier);
  } else {
    data = data.filter(p => defaultTiers.has(p.mpg_tier));
  }

  // Stat threshold filters
  cExplorerStatFilters.forEach(f => {
    data = data.filter(p => {
      const v = parseFloat(p[f.stat]);
      if (isNaN(v)) return false;
      if (f.min !== '' && !isNaN(f.min) && v < parseFloat(f.min)) return false;
      if (f.max !== '' && !isNaN(f.max) && v > parseFloat(f.max)) return false;
      return true;
    });
  });

  // Sort
  data.sort((a, b) => {
    const aVal = parseFloat(a[cExplorerSort.key]);
    const bVal = parseFloat(b[cExplorerSort.key]);
    if (isNaN(aVal) && isNaN(bVal)) return 0;
    if (isNaN(aVal)) return 1;
    if (isNaN(bVal)) return -1;
    return cExplorerSort.dir === 'desc' ? bVal - aVal : aVal - bVal;
  });

  cExplorerFiltered = data;
}

function setExplorerSort(key) {
  if (cExplorerSort.key === key) {
    cExplorerSort.dir = cExplorerSort.dir === 'desc' ? 'asc' : 'desc';
  } else {
    cExplorerSort.key = key;
    cExplorerSort.dir = 'desc';
  }
  applyExplorerFilters();
  renderExplorerTable();
}

function setExplorerStatTab(tab, btn) {
  cExplorerStatTab = tab;
  document.querySelectorAll('#explorer-stat-tabs .hist-cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  // Set default sort for this tab
  if (TAB_DEFAULT_SORT[tab]) {
    cExplorerSort = {key: TAB_DEFAULT_SORT[tab], dir: 'desc'};
  }
  applyExplorerFilters();
  renderExplorerTable();
}

function setExplorerPctContext(ctx, btn) {
  cExplorerPctContext = ctx;
  document.querySelectorAll('#explorer-pct-toggle .view-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderExplorerTable();
}

function onExplorerFilterChange() {
  applyExplorerFilters();
  renderExplorerTable();
}

function addStatFilter() {
  const stat = document.getElementById('sf-stat-select').value;
  const min = document.getElementById('sf-min').value;
  const max = document.getElementById('sf-max').value;
  if (!stat) return;
  cExplorerStatFilters.push({stat, min, max});
  renderStatFilterTags();
  applyExplorerFilters();
  renderExplorerTable();
}

function removeStatFilter(i) {
  cExplorerStatFilters.splice(i, 1);
  renderStatFilterTags();
  applyExplorerFilters();
  renderExplorerTable();
}

function renderStatFilterTags() {
  const wrap = document.getElementById('stat-filter-tags');
  if (!wrap) return;
  wrap.innerHTML = cExplorerStatFilters.map((f, i) => {
    const minStr = f.min !== '' ? ` \u2265 ${f.min}` : '';
    const maxStr = f.max !== '' ? ` \u2264 ${f.max}` : '';
    return `<span class="stat-filter-tag">${f.stat}${minStr}${maxStr} <span class="stat-filter-remove" onclick="removeStatFilter(${i})">\u00d7</span></span>`;
  }).join('');
}

// ── POPULATE FILTER DROPDOWNS ─────────────────────────────────────────────────
function populateExplorerDropdowns(data) {
  const confs = [...new Set(data.map(p => p.conference).filter(Boolean))].sort();
  const roles = [...new Set(data.map(p => p.role).filter(Boolean))].sort();
  const tiers = [
    'Core Player (26+ MPG)',
    'Primary Rotation (18\u201326 MPG)',
    'Bench Rotation (10\u201318 MPG)',
    'Fringe Rotation (5\u201310 MPG)',
    'End of Bench (0\u20135 MPG)',
  ];

  const confSel = document.getElementById('ef-conference');
  if (confSel && confSel.options.length <= 1) {
    confs.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; confSel.appendChild(o); });
  }
  const roleSel = document.getElementById('ef-role');
  if (roleSel && roleSel.options.length <= 1) {
    roles.forEach(r => { const o = document.createElement('option'); o.value = r; o.textContent = r; roleSel.appendChild(o); });
  }
  const tierSel = document.getElementById('ef-tier');
  if (tierSel && tierSel.options.length <= 1) {
    tiers.forEach(t => { const o = document.createElement('option'); o.value = t; o.textContent = t; tierSel.appendChild(o); });
  }

  // Years in D1
  const yrsSel = document.getElementById('ef-years-d1');
  if (yrsSel && yrsSel.options.length <= 1) {
    [1,2,3,4,5].forEach(y => {
      const o = document.createElement('option');
      o.value = y; o.textContent = y + (y===5?'+':' yr');
      yrsSel.appendChild(o);
    });
  }

  // Stat filter dropdown
  const sfSel = document.getElementById('sf-stat-select');
  if (sfSel && sfSel.options.length <= 1) {
    const allStats = Object.values(EXPLORER_STAT_TABS).flat().filter(s => !s.computed && !STRING_KEYS_E.has(s.key));
    const seen = new Set();
    allStats.forEach(s => {
      if (seen.has(s.key)) return;
      seen.add(s.key);
      const o = document.createElement('option');
      o.value = s.key;
      o.textContent = s.label.replace('\n',' ');
      sfSel.appendChild(o);
    });
  }
}

// ── RENDER TABLE ──────────────────────────────────────────────────────────────
function explorerTip(key) {
  const t = EXPLORER_TIPS[key];
  if (!t) return '';
  return `<span class="info-icon" onclick="toggleTip(event,this)" style="margin-left:3px">i<span class="tooltip">${t}</span></span>`;
}

function explorerPctCls(pct) {
  if (pct >= 0.85) return 'pct-elite';
  if (pct >= 0.65) return 'pct-good';
  if (pct >= 0.40) return 'pct-avg';
  if (pct >= 0.20) return 'pct-below';
  return 'pct-poor';
}

function explorerStackedCell(rawDisplay, pctVal, isSortedCol) {
  const pct = parseFloat(pctVal);
  if (isNaN(pct)) return `<span class="roster-raw-white">${rawDisplay}</span>`;
  const cls = explorerPctCls(pct);
  const pctDisplay = Math.round(pct * 100);
  const barWidth = Math.round(pct * 100);
  return `<div class="roster-pct-cell">
    <span class="roster-raw-val ${cls}">${rawDisplay}</span>
    <div class="roster-pct-row">
      <span class="roster-pct-num ${cls}">${pctDisplay}</span>
      <div class="roster-pct-bar-wrap"><div class="roster-pct-bar ${cls}-bar" style="width:${barWidth}%"></div></div>
    </div>
  </div>`;
}

function renderExplorerTable() {
  const wrap = document.getElementById('explorer-table-wrap');
  if (!wrap || !cExplorerFiltered.length) {
    if (wrap) wrap.innerHTML = '<div class="empty-state">No players match the current filters.</div>';
    return;
  }

  populateExplorerDropdowns(cExplorerData);

  const stats = EXPLORER_STAT_TABS[cExplorerStatTab];
  const pctSuffix = PCT_SUFFIX[cExplorerPctContext] || '_pct';
  const display = cExplorerFiltered.slice(0, 200);
  const sortedStatIdx = stats.findIndex(s => s.key === cExplorerSort.key);

  let html = `<div class="explorer-table-scroll-wrap"><div class="explorer-table-inner"><div class="roster-table-wrap"><table class="roster-table explorer-table"><thead><tr>`;

  // Rank column
  html += `<th class="roster-frozen-th explorer-rank-th" style="position:sticky;left:0;z-index:4;min-width:32px;width:32px;">#</th>`;

  // Frozen identity columns
  EXPLORER_FROZEN.forEach(col => {
    const lbl = col.label.replace('\n','<br>');
    if (col.frozen) {
      const isLastFrozen = col.key === 'position';
      const lastFrozenCls = isLastFrozen ? ' explorer-last-frozen' : '';
      html += `<th class="roster-frozen-th explorer-id-th${lastFrozenCls}" style="position:sticky;left:${col.left}px;z-index:4;min-width:${col.width}px;max-width:${col.width}px;background:var(--surface2);">${lbl}</th>`;
    } else {
      html += `<th class="roster-frozen-th roster-scroll-th">${lbl}</th>`;
    }
  });

  // Stat headers
  stats.forEach((s, i) => {
    const lbl = s.label.replace('\n','<br>');
    const tipDir = i >= stats.length - 4 ? 'tip-left' : '';
    const isSorted = cExplorerSort.key === s.key;
    const sortIcon = isSorted ? (cExplorerSort.dir === 'desc' ? ' \u25be' : ' \u25b4') : '';
    const sortedCls = isSorted ? ' explorer-col-sorted' : '';
    const clickable = !s.computed && !s.noBar ? 'onclick="setExplorerSort(\'' + s.key + '\')" style="cursor:pointer;"' : '';
    html += '<th class="roster-stat-th ' + tipDir + sortedCls + '" ' + clickable + '>' + lbl + sortIcon + explorerTip(s.key) + '</th>';
  });

  html += `</tr></thead><tbody>`;

  display.forEach((p, idx) => {
    const isTier2 = p.percentile_tier === 'Tier 2';
    const noPercentile = !p.percentile_eligible || p.percentile_eligible === false || p.percentile_eligible === 'False';
    const rowCls = isTier2 ? 'roster-row roster-tier2' : 'roster-row';

    html += `<tr class="${rowCls}">`;

    // Rank cell
    html += `<td class="roster-frozen-td explorer-rank-cell" style="position:sticky;left:0;z-index:2;background:var(--surface);">${idx+1}</td>`;

    // Frozen identity cells
    EXPLORER_FROZEN.forEach(col => {
      const val = p[col.key];
      const disp = col.fmt ? col.fmt(val) : (val ?? '—');
      if (col.frozen) {
        const isLastFrozenCell = col.key === 'position';
        const lastFrozenCellCls = isLastFrozenCell ? ' explorer-last-frozen' : '';
        html += `<td class="roster-frozen-td explorer-id-cell${lastFrozenCellCls}" style="position:sticky;left:${col.left}px;z-index:2;min-width:${col.width}px;max-width:${col.width}px;overflow:hidden;text-overflow:ellipsis;background:var(--surface);">${disp}</td>`;
      } else {
        html += `<td class="roster-frozen-td roster-scroll-td">${disp}</td>`;
      }
    });

    // Stat cells
    stats.forEach((s, si) => {
      const isSortedCol = si === sortedStatIdx;
      const sortedTdCls = isSortedCol ? ' explorer-col-sorted' : '';
      const rawVal = s.computed ? null : p[s.key];
      const isString = STRING_KEYS_E.has(s.key) || s.noBar;

      if (isString) {
        const disp = s.computed ? s.fmt(null, p) : s.fmt(rawVal);
        html += `<td class="roster-stat-td${sortedTdCls}"><span class="roster-raw-white">${disp ?? '—'}</span></td>`;
        return;
      }

      const isDrtgDelta = DRTG_DELTA_KEYS_E.has(s.key);
      let rawDisplay;
      if (isDrtgDelta) {
        const v = parseFloat(rawVal);
        rawDisplay = isNaN(v) ? '—' : (((-v)>0?'+':'') + (-v).toFixed(1));
      } else {
        rawDisplay = (rawVal === null || rawVal === undefined || isNaN(parseFloat(rawVal))) ? '—' : s.fmt(rawVal);
      }

      const pctKey = s.key + pctSuffix;
      const pctVal = p[pctKey];
      const hasPct = pctVal !== undefined && pctVal !== null;

      if (noPercentile || !hasPct) {
        html += `<td class="roster-stat-td${sortedTdCls}"><span class="roster-raw-white">${rawDisplay}</span></td>`;
        return;
      }

      html += `<td class="roster-stat-td${sortedTdCls}">${explorerStackedCell(rawDisplay, pctVal, isSortedCol)}</td>`;
    });

    html += `</tr>`;
  });

  if (cExplorerFiltered.length > 200) {
    html += `<tr><td colspan="999" class="explorer-more-row">Showing top 200 of ${cExplorerFiltered.length.toLocaleString()} players — add filters to narrow results</td></tr>`;
  }

  html += `</tbody></table></div></div></div>`;
  const hint = '<div class="explorer-sort-hint">Click any column header to sort</div>';
  wrap.innerHTML = hint + html;

  const countEl = document.getElementById('explorer-count');
  if (countEl) countEl.textContent = `${cExplorerFiltered.length.toLocaleString()} players`;

  // Sync top scrollbar
  setTimeout(syncExplorerScrollbar, 60);
}

// ── MULTI-SELECT FILTER SYSTEM ────────────────────────────────────────────────
// State: maps filterKey -> Set of selected values (empty Set = all selected)
const EXPLORER_MULTI_STATE = {
  position:  new Set(), // empty = all
  conference: new Set(),
  class:     new Set(),
  mpg_tier:  new Set(['Core Player (26+ MPG)','Primary Rotation (18\u201326 MPG)','Bench Rotation (10\u201318 MPG)','Fringe Rotation (5\u201310 MPG)']), // EOB excluded by default
  level:     new Set(), // Power/Mid
};

let cExplorerMinGames = 5;
let cExplorerHeightMin = 60; // 5'0"
let cExplorerHeightMax = 90; // 7'6"
let cExplorerNameSearch = '';

function initMultiFilters(data) {
  // Conferences
  const confs = [...new Set(data.map(p => p.conference).filter(Boolean))].sort();
  buildCheckboxDropdown('mf-conference', 'Conference', confs, EXPLORER_MULTI_STATE.conference, true);

  // Classes
  buildButtonFilter('mf-class', ['FR','SO','JR','SR','GR'], EXPLORER_MULTI_STATE.class);

  // MPG Tiers
  const tiers = ['Core Player (26+ MPG)','Primary Rotation (18\u201326 MPG)','Bench Rotation (10\u201318 MPG)','Fringe Rotation (5\u201310 MPG)','End of Bench (0\u20135 MPG)'];
  const tierLabels = ['Core (26+)','Primary (18-26)','Bench (10-18)','Fringe (5-10)','End of Bench'];
  buildButtonFilter('mf-mpg-tier', tiers, EXPLORER_MULTI_STATE.mpg_tier, tierLabels);

  // Height slider
  const heights = data.map(p => parseInt(p.height_in)).filter(h => !isNaN(h));
  cExplorerHeightMin = Math.min(...heights);
  cExplorerHeightMax = Math.max(...heights);
  initHeightSlider(cExplorerHeightMin, cExplorerHeightMax);
}

// Button-style multi-toggle (Position, Level, Class, MPG Tier)
function buildButtonFilter(containerId, values, stateSet, labels) {
  const container = document.getElementById(containerId);
  if (!container || container.dataset.built) return;
  container.dataset.built = '1';
  const lbls = labels || values;
  values.forEach((v, i) => {
    const btn = document.createElement('button');
    btn.className = 'mf-btn' + (stateSet.size === 0 || stateSet.has(v) ? ' active' : '');
    btn.textContent = lbls[i];
    btn.dataset.value = v;
    btn.onclick = () => {
      if (stateSet.has(v)) {
        stateSet.delete(v);
      } else {
        stateSet.add(v);
      }
      // If all selected or none selected, treat as all
      if (stateSet.size === values.length) stateSet.clear();
      btn.className = 'mf-btn' + (stateSet.size === 0 || stateSet.has(v) ? ' active' : '');
      // Update all buttons in container
      container.querySelectorAll('.mf-btn').forEach(b => {
        b.className = 'mf-btn' + (stateSet.size === 0 || stateSet.has(b.dataset.value) ? ' active' : '');
      });
      onExplorerFilterChange();
    };
    container.appendChild(btn);
  });
}

// Checkbox dropdown (Conference)
function buildCheckboxDropdown(containerId, label, values, stateSet, searchable) {
  const container = document.getElementById(containerId);
  if (!container || container.dataset.built) return;
  container.dataset.built = '1';

  const btn = document.createElement('button');
  btn.className = 'mf-dropdown-btn';
  btn.innerHTML = label + ' <span class="mf-dropdown-arrow">\u25be</span>';

  const menu = document.createElement('div');
  menu.className = 'mf-dropdown-menu';
  menu.style.display = 'none';

  if (searchable) {
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Search...';
    searchInput.className = 'mf-search';
    searchInput.oninput = () => {
      const q = searchInput.value.toLowerCase();
      menu.querySelectorAll('.mf-check-item').forEach(item => {
        item.style.display = item.dataset.value.toLowerCase().includes(q) ? '' : 'none';
      });
    };
    menu.appendChild(searchInput);
  }

  // All option
  const allItem = document.createElement('label');
  allItem.className = 'mf-check-item';
  allItem.innerHTML = '<input type="checkbox" checked> All';
  const allCb = allItem.querySelector('input');
  allCb.onchange = () => {
    if (allCb.checked) {
      stateSet.clear();
      menu.querySelectorAll('.mf-check-item input:not(.all-cb)').forEach(cb => cb.checked = true);
    }
    updateDropdownLabel();
    onExplorerFilterChange();
  };
  allCb.classList.add('all-cb');
  menu.appendChild(allItem);

  values.forEach(v => {
    const item = document.createElement('label');
    item.className = 'mf-check-item';
    item.dataset.value = v;
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = stateSet.size === 0 || stateSet.has(v);
    cb.onchange = () => {
      if (cb.checked) {
        stateSet.add(v);
      } else {
        stateSet.delete(v);
        // If nothing checked, check all
        if (stateSet.size === 0) {
          menu.querySelectorAll('.mf-check-item input:not(.all-cb)').forEach(c => c.checked = true);
          allCb.checked = true;
        }
      }
      // Check if all selected
      const total = values.length;
      if (stateSet.size === total) { stateSet.clear(); }
      allCb.checked = stateSet.size === 0;
      updateDropdownLabel();
      onExplorerFilterChange();
    };
    item.appendChild(cb);
    item.appendChild(document.createTextNode(' ' + v));
    menu.appendChild(item);
  });

  function updateDropdownLabel() {
    const count = stateSet.size;
    btn.innerHTML = (count === 0 ? label : label + ` (${count})`) + ' <span class="mf-dropdown-arrow">\u25be</span>';
  }

  btn.onclick = (e) => {
    e.stopPropagation();
    const isOpen = menu.style.display !== 'none';
    document.querySelectorAll('.mf-dropdown-menu').forEach(m => m.style.display = 'none');
    menu.style.display = isOpen ? 'none' : 'block';
  };

  document.addEventListener('click', () => { menu.style.display = 'none'; }, {once: false});

  container.appendChild(btn);
  container.appendChild(menu);
}

function initHeightSlider(minH, maxH) {
  const container = document.getElementById('mf-height');
  if (!container || container.dataset.built) return;
  container.dataset.built = '1';

  const fmtHt = h => { const f=Math.floor(h/12), i=h%12; return `${f}'${i}"`; };

  const label = document.createElement('span');
  label.className = 'mf-height-label';
  label.textContent = `${fmtHt(minH)} – ${fmtHt(maxH)}`;

  const sliderWrap = document.createElement('div');
  sliderWrap.className = 'mf-slider-wrap';

  const minSlider = document.createElement('input');
  minSlider.type = 'range'; minSlider.min = minH; minSlider.max = maxH;
  minSlider.value = minH; minSlider.className = 'mf-slider mf-slider-min';

  const maxSlider = document.createElement('input');
  maxSlider.type = 'range'; maxSlider.min = minH; maxSlider.max = maxH;
  maxSlider.value = maxH; maxSlider.className = 'mf-slider mf-slider-max';

  const updateLabel = () => {
    const lo = parseInt(minSlider.value);
    const hi = parseInt(maxSlider.value);
    if (lo > hi) { minSlider.value = hi; }
    if (hi < lo) { maxSlider.value = lo; }
    cExplorerHeightMin = parseInt(minSlider.value);
    cExplorerHeightMax = parseInt(maxSlider.value);
    label.textContent = `${fmtHt(cExplorerHeightMin)} – ${fmtHt(cExplorerHeightMax)}`;
    onExplorerFilterChange();
  };

  minSlider.oninput = updateLabel;
  maxSlider.oninput = updateLabel;

  sliderWrap.appendChild(minSlider);
  sliderWrap.appendChild(maxSlider);
  container.appendChild(label);
  container.appendChild(sliderWrap);
}

// ── POSITION / LEVEL BUTTON TOGGLES ──────────────────────────────────────────
function togglePositionFilter(val, btn) {
  const state = EXPLORER_MULTI_STATE.position;
  if (state.has(val)) {
    state.delete(val);
    btn.classList.remove('active');
  } else {
    state.add(val);
    btn.classList.add('active');
  }
  // If all 3 selected, clear (= all)
  if (state.size === 3) { state.clear(); document.querySelectorAll('#mf-position .mf-btn').forEach(b => b.classList.add('active')); }
  onExplorerFilterChange();
}

function toggleLevelFilter(val, btn) {
  const state = EXPLORER_MULTI_STATE.level;
  if (state.has(val)) {
    state.delete(val);
    btn.classList.remove('active');
  } else {
    state.add(val);
    btn.classList.add('active');
  }
  if (state.size === 2) { state.clear(); document.querySelectorAll('#mf-level .mf-btn').forEach(b => b.classList.add('active')); }
  onExplorerFilterChange();
}

// ── SCROLLBAR AT TOP ──────────────────────────────────────────────────────────
function syncExplorerScrollbar() {
  const topBar = document.getElementById('explorer-scroll-top');
  const tableWrap = document.querySelector('#explorer-table-wrap .explorer-table-scroll-wrap');
  if (!topBar || !tableWrap) return;

  // Sync widths
  const inner = tableWrap.querySelector('table');
  if (inner) topBar.querySelector('div').style.width = inner.offsetWidth + 'px';

  // Sync scroll position
  topBar.onscroll = () => { tableWrap.scrollLeft = topBar.scrollLeft; };
  tableWrap.onscroll = () => { topBar.scrollLeft = tableWrap.scrollLeft; };
}

// Call after render
const _origRenderExplorer = renderExplorerTable;
// Patch renderExplorerTable to sync scrollbar after render
const _patchedRender = function() {
  _origRenderExplorer();
  setTimeout(syncExplorerScrollbar, 50);
};
