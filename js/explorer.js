// ── PLAYER EXPLORER ───────────────────────────────────────────────────────────
let EXPLORER_CACHE = {};
let cExplorerYear = 2026;
let cExplorerStatTab = 'overview';
let cExplorerPctContext = 'national';
let cExplorerSort = {key: 'bpm', dir: 'desc'};
let cExplorerStatFilters = [];
let cExplorerPctFilters = [];
let cExplorerData = [];
let cExplorerFiltered = [];
let cExplorerPage = 1;
const EXPLORER_PAGE_SIZE = 200;

// Default sort per tab
const TAB_DEFAULT_SORT = {
  overview: 'bpm',
  advanced: 'prpg',
  shooting: 'ppp_used',
  per40:    'pts_per_40',
  context:  'ortg_delta_team',
};

// ── TOOLTIPS ─────────────────────────────────────────────────────────────────
const EXPLORER_TIPS = {
  ppg:'Points per game.',rebpg:'Rebounds per game.',astpg:'Assists per game.',
  stlpg:'Steals per game.',blkpg:'Blocks per game.',
  ts:'True Shooting % — overall scoring efficiency.',
  efg:'Effective FG% — weights 3-pointers. Formula: (FGM + 0.5×3PM) / FGA.',
  usage_pct:'Usage % — share of team possessions used while on floor.',
  prpg:"Torvik's PRPG! (PORPAGATU!) — offensive value added above replacement per game, adjusted for usage and opponent strength.",
  
  dprpg:"Torvik's DPRPG! — defensive value added above replacement per game, adjusted for opponent strength.",
  bpm:'Box Plus/Minus — overall on-court impact per 100 possessions above average.',
  obpm:'Offensive Box Plus/Minus.',dbpm:'Defensive Box Plus/Minus.',
  ortg:'Offensive Rating — points produced per 100 possessions used.',
  ortg_delta_team:'Offensive rating with this player on the floor vs. team avg. Positive = better than team avg.',
  drtg:'Defensive Rating — points allowed per 100 possessions. Lower is better.',
  drtg_delta_team:'Defensive rating with this player on the floor vs. team avg. Positive = better than team avg.',
  ppp_used:'Points per possession used — accounts for FGA, free throw trips, and turnovers.',
  or_pct:'Offensive Rebound %.',dr_pct:'Defensive Rebound %.',
  ast_pct:'Assist % — % of teammate FGs assisted while on floor.',
  tov_pct:'Turnover % — turnovers per possession used. Lower is better.',
  tov_sensitivity:'TOV Sensitivity — percentage of team possessions this player turns over. Formula: TOV% × Usage%.',
  blk_pct:'% of opponent 2PT attempts blocked.',stl_pct:'% of opponent possessions ending in steal.',
  ast_tov_ratio:'Assist-to-turnover ratio.',
  foul_sensitivity:'Fouls committed per minute played. Indicates foul risk — higher = more likely to foul out.',
  total_fg_pct:'Overall FG%.',two_fg_pct:'2-point FG%.',
  rim_rate:'Rim attempt rate — dunks + close 2s as share of FGA.',
  rim_fg_pct:'FG% at the rim — dunks + close 2s combined.',
  close_two_rate:'Close 2PT attempt rate as share of FGA.',
  close_two_fg_pct:'FG% on close 2PT attempts.',
  dunk_rate:'Dunk attempt rate as share of FGA.',dunk_fg_pct:'FG% on dunks.',
  midrange_rate:'Midrange attempt rate as share of FGA.',midrange_fg_pct:'FG% on midrange shots.',
  three_rate:'3PT attempt rate as share of FGA.',three_fg_pct:'3PT FG%.',
  three_p_per_100:'3PT attempts per 100 possessions.',
  ft_rate:'Free throw rate — FTA per FGA.',ft_pct:'Free throw %.',
  close_vs_mid_ratio:'Rim / midrange attempts. Higher = more paint-oriented.',
  rim_vs_three_ratio:'Rim / 3PT attempts. Higher = more rim pressure.',
  pts_per_40:'Points per 40 minutes.',reb_per_40:'Rebounds per 40.',
  ast_per_40:'Assists per 40.',stl_per_40:'Steals per 40.',blk_per_40:'Blocks per 40.',
  stocks_per_40:'Steals + blocks per 40.',fc_40:'Fouls committed per 40.',
  ortg_delta_conf:'Player ORtg minus conference average.',
  drtg_delta_conf:'Pts/100 better vs conference average defense.',
  ortg_delta_sub:'Player ORtg minus Power/Mid-Major average.',
  drtg_delta_sub:'Pts/100 better vs Power/Mid-Major average defense.',
  ts_delta_team:'Player TS% minus team TS%.',ts_delta_conf:'Player TS% minus conf TS%.',
  ts_delta_sub:'Player TS% minus Power/Mid-Major TS%.',
  efg_delta_team:'Player eFG% minus team eFG%.',efg_delta_conf:'Player eFG% minus conf eFG%.',
  efg_delta_sub:'Player eFG% minus Power/Mid-Major eFG%.',
  rim_rate_delta_team:'Player rim rate minus team rim rate.',
  rim_rate_delta_conf:'Player rim rate minus conf rim rate.',
  rim_rate_delta_sub:'Player rim rate minus Power/Mid-Major rim rate.',
  three_rate_delta_team:'Player 3PT rate minus team 3PT rate.',
  three_rate_delta_conf:'Player 3PT rate minus conf 3PT rate.',
  three_rate_delta_sub:'Player 3PT rate minus Power/Mid-Major 3PT rate.',
  recruit_rank_clean:'Recruit Score (0-100) — Torvik recruit rating. 100 = highest rated. Blank = unranked.',
  age:'Player age on Feb 1 of season.',years_in_d1:'Years of D1 experience.',
};

const PCT_SUFFIX = {
  national:'_pct', conf:'_conf_pct', sub:'_sub_pct',
  pos:'_pos_pct', pos_conf:'_pos_conf_pct', pos_sub:'_pos_sub_pct',
};

function fmtPctE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v==null)return'—';return n.toFixed(d)+'%';}
function fmtPctDecE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v==null)return'—';return(n*100).toFixed(d)+'%';}
function fmtSignE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v==null)return'—';return(n>0?'+':'')+n.toFixed(d);}
function fmtMAE(p,mk,ak){const m=parseFloat(p[mk]),a=parseFloat(p[ak]);if(isNaN(m)||isNaN(a))return'—';return m.toFixed(1)+'/'+a.toFixed(1);}
function fmtNumE(v,d=1){const n=parseFloat(v);if(isNaN(n)||v==null)return'—';return n.toFixed(d);}
function fmtDrtgDelta(v){const n=parseFloat(v);if(isNaN(n))return'—';const f=-n;return(f>0?'+':'')+f.toFixed(1);}

const DRTG_DELTA_KEYS_E = new Set(['drtg_delta_team','drtg_delta_conf','drtg_delta_sub']);
const STRING_KEYS_E = new Set(['_fgm_fga','_two_ma','_rim_ma','_close_two_ma','_dunk_ma','_mid_ma','_three_ma','_ft_ma']);

const EXPLORER_STAT_TABS = {
  overview:[
    {key:'usage_pct',fmt:v=>fmtPctE(v),label:'USG%'},
    {key:'bpm',fmt:v=>fmtSignE(v),label:'BPM'},
    {key:'obpm',fmt:v=>fmtSignE(v),label:'Off\nBPM'},
    {key:'dbpm',fmt:v=>fmtSignE(v),label:'Def\nBPM'},
    {key:'ts',fmt:v=>fmtPctE(v),label:'TS%'},
    {key:'ppg',fmt:v=>fmtNumE(v),label:'PTS/G'},
    {key:'rebpg',fmt:v=>fmtNumE(v),label:'REB/G'},
    {key:'astpg',fmt:v=>fmtNumE(v),label:'AST/G'},
    {key:'stlpg',fmt:v=>fmtNumE(v),label:'STL/G'},
    {key:'blkpg',fmt:v=>fmtNumE(v),label:'BLK/G'},
  ],
  advanced:[
    {key:'prpg',fmt:v=>fmtNumE(v,2),label:'PRPG'},
    {key:'dprpg',fmt:v=>fmtNumE(v,2),label:'Def\nPRPG'},
    {key:'ortg',fmt:v=>fmtNumE(v,1),label:'Off\nRtg'},
    {key:'ortg_delta_team',fmt:v=>fmtSignE(v),label:'Off Rtg\nvs Team'},
    {key:'drtg',fmt:v=>fmtNumE(v,1),label:'Def\nRtg'},
    {key:'drtg_delta_team',fmt:v=>fmtDrtgDelta(v),label:'Def Rtg\nvs Team'},
    {key:'or_pct',fmt:v=>fmtPctE(v),label:'OR%'},
    {key:'dr_pct',fmt:v=>fmtPctE(v),label:'DR%'},
    {key:'ast_pct',fmt:v=>fmtPctE(v),label:'AST%'},
    {key:'tov_pct',fmt:v=>fmtPctE(v),label:'TOV%'},
    {key:'ast_tov_ratio',fmt:v=>fmtNumE(v,2),label:'AST/\nTOV'},
    {key:'tov_sensitivity',fmt:v=>fmtPctE(v,1),label:'TOV\nSensitivity'},
    {key:'blk_pct',fmt:v=>fmtPctE(v),label:'BLK%'},
    {key:'stl_pct',fmt:v=>fmtPctE(v),label:'STL%'},
    {key:'foul_sensitivity',fmt:v=>fmtNumE(v,2),label:'Foul\nSensitivity'},
  ],
  shooting:[
    {key:'ppp_used',fmt:v=>fmtNumE(v,3),label:'PPP\nUsed'},
    {key:'ts',fmt:v=>fmtPctE(v),label:'TS%'},
    {key:'efg',fmt:v=>fmtPctE(v),label:'eFG%'},
    {key:'total_fg_pct',fmt:v=>fmtPctDecE(v),label:'FG%'},
    {key:'_fgm_fga',fmt:(v,p)=>fmtMAE(p,'fgm_pg','fga_pg'),noBar:true,computed:true,label:'FGM/\nFGA'},
    {key:'two_fg_pct',fmt:v=>fmtPctDecE(v),label:'2PT\nFG%'},
    {key:'_two_ma',fmt:(v,p)=>fmtMAE(p,'two_made_pg','two_att_pg'),noBar:true,computed:true,label:'2PT\nFGM/FGA'},
    {key:'three_rate',fmt:v=>fmtPctDecE(v),label:'3PT\nRate'},
    {key:'three_fg_pct',fmt:v=>fmtPctDecE(v),label:'3PT%'},
    {key:'_three_ma',fmt:(v,p)=>fmtMAE(p,'three_made_pg','three_att_pg'),noBar:true,computed:true,label:'3PT\nFGM/FGA'},
    {key:'three_p_per_100',fmt:v=>fmtNumE(v,1),label:'3PA/\n100'},
    {key:'rim_rate',fmt:v=>fmtPctDecE(v),label:'Rim\nRate'},
    {key:'rim_fg_pct',fmt:v=>fmtPctDecE(v),label:'Rim\nFG%'},
    {key:'_rim_ma',fmt:(v,p)=>fmtMAE(p,'rim_made_pg','rim_att_pg'),noBar:true,computed:true,label:'Rim\nFGM/FGA'},
    {key:'close_two_rate',fmt:v=>fmtPctDecE(v),label:'Close 2\nRate'},
    {key:'close_two_fg_pct',fmt:v=>fmtPctDecE(v),label:'Close 2\nFG%'},
    {key:'_close_two_ma',fmt:(v,p)=>fmtMAE(p,'close_two_made_pg','close_two_att_pg'),noBar:true,computed:true,label:'Close 2\nFGM/FGA'},
    {key:'dunk_rate',fmt:v=>fmtPctDecE(v),label:'Dunk\nRate'},
    {key:'dunk_fg_pct',fmt:v=>fmtPctDecE(v),label:'Dunk\nFG%'},
    {key:'_dunk_ma',fmt:(v,p)=>fmtMAE(p,'dunk_made_pg','dunk_att_pg'),noBar:true,computed:true,label:'Dunk\nFGM/FGA'},
    {key:'midrange_rate',fmt:v=>fmtPctDecE(v),label:'Midrange\nRate'},
    {key:'midrange_fg_pct',fmt:v=>fmtPctDecE(v),label:'Midrange\nFG%'},
    {key:'_mid_ma',fmt:(v,p)=>fmtMAE(p,'midrange_made_pg','midrange_att_pg'),noBar:true,computed:true,label:'Midrange\nFGM/FGA'},
    {key:'ft_rate',fmt:v=>fmtPctDecE(v),label:'FT\nRate'},
    {key:'ft_pct',fmt:v=>fmtPctDecE(v),label:'FT%'},
    {key:'_ft_ma',fmt:(v,p)=>fmtMAE(p,'ft_made_pg','ft_att_pg'),noBar:true,computed:true,label:'FTM/\nFTA'},
    {key:'close_vs_mid_ratio',fmt:v=>fmtNumE(v,2),label:'Rim/\nMid'},
    {key:'rim_vs_three_ratio',fmt:v=>fmtNumE(v,2),label:'Rim/\n3PT'},
  ],
  per40:[
    {key:'pts_per_40',fmt:v=>fmtNumE(v),label:'PTS\n/40'},
    {key:'reb_per_40',fmt:v=>fmtNumE(v),label:'REB\n/40'},
    {key:'ast_per_40',fmt:v=>fmtNumE(v),label:'AST\n/40'},
    {key:'stl_per_40',fmt:v=>fmtNumE(v),label:'STL\n/40'},
    {key:'blk_per_40',fmt:v=>fmtNumE(v),label:'BLK\n/40'},
    {key:'stocks_per_40',fmt:v=>fmtNumE(v),label:'Stocks\n/40'},
    {key:'fc_40',fmt:v=>fmtNumE(v,2),label:'FC\n/40'},
  ],
  context:[
    {key:'ortg_delta_team',fmt:v=>fmtSignE(v),label:'Off Rtg\nvs Team'},
    {key:'drtg_delta_team',fmt:v=>fmtDrtgDelta(v),label:'Def Rtg\nvs Team'},
    {key:'ts_delta_team',fmt:v=>fmtSignE(v,2),label:'TS%\nvs Team'},
    {key:'efg_delta_team',fmt:v=>fmtSignE(v,2),label:'eFG%\nvs Team'},
    {key:'rim_rate_delta_team',fmt:v=>fmtSignE(parseFloat(v)*100,1)+'%',label:'Rim\nvs Team'},
    {key:'three_rate_delta_team',fmt:v=>fmtSignE(parseFloat(v)*100,1)+'%',label:'3PT\nvs Team'},
    {key:'ortg_delta_conf',fmt:v=>fmtSignE(v),label:'Off Rtg\nvs Conf'},
    {key:'drtg_delta_conf',fmt:v=>fmtDrtgDelta(v),label:'Def Rtg\nvs Conf'},
    {key:'ts_delta_conf',fmt:v=>fmtSignE(v,2),label:'TS%\nvs Conf'},
    {key:'efg_delta_conf',fmt:v=>fmtSignE(v,2),label:'eFG%\nvs Conf'},
    {key:'rim_rate_delta_conf',fmt:v=>fmtSignE(parseFloat(v)*100,1)+'%',label:'Rim\nvs Conf'},
    {key:'three_rate_delta_conf',fmt:v=>fmtSignE(parseFloat(v)*100,1)+'%',label:'3PT\nvs Conf'},
    {key:'ortg_delta_sub',fmt:v=>fmtSignE(v),label:'Off Rtg\nvs Power/Mid'},
    {key:'drtg_delta_sub',fmt:v=>fmtDrtgDelta(v),label:'Def Rtg\nvs Power/Mid'},
    {key:'ts_delta_sub',fmt:v=>fmtSignE(v,2),label:'TS%\nvs Power/Mid'},
    {key:'efg_delta_sub',fmt:v=>fmtSignE(v,2),label:'eFG%\nvs Power/Mid'},
    {key:'rim_rate_delta_sub',fmt:v=>fmtSignE(parseFloat(v)*100,1)+'%',label:'Rim\nvs Power/Mid'},
    {key:'three_rate_delta_sub',fmt:v=>fmtSignE(parseFloat(v)*100,1)+'%',label:'3PT\nvs Power/Mid'},
  ],
};

const EXPLORER_FROZEN = [
  {key:'name',label:'Player',frozen:true,width:155,left:28,fmt:v=>v??'—'},
  {key:'team',label:'Team',frozen:true,width:125,left:183,fmt:v=>v??'—'},
  {key:'position',label:'Pos',frozen:true,width:65,left:308,fmt:v=>v??'—'},
  {key:'class',label:'Yr',frozen:false,fmt:v=>v??'—'},
  {key:'height_in',label:'Ht',frozen:false,fmt:v=>{const i=parseInt(v);return isNaN(i)?'—':Math.floor(i/12)+"'"+(i%12)+'"';}},
  {key:'games',label:'G',frozen:false,fmt:v=>v??'—'},
  {key:'minutes_per_game',label:'MPG',frozen:false,fmt:v=>fmtNumE(v)},
  {key:'age',label:'Age',frozen:false,fmt:v=>fmtNumE(v,1)},
  {key:'recruit_rank_clean',label:'Recruit\nScore',frozen:false,tip:true,fmt:v=>(v&&!isNaN(v))?parseInt(v):'—'},
  {key:'years_in_d1',label:'Yrs\nD1',frozen:false,tip:true,fmt:v=>v??'—'},
];

// ── FILTER STATE — simple object, read from DOM ───────────────────────────────
// Active multi-select sets — empty = all selected
let EF = {
  positions:   new Set(),
  levels:      new Set(),
  classes:     new Set(),
  tiers:       new Set(['Core Player (26+ MPG)','Primary Rotation (18\u201326 MPG)','Bench Rotation (10\u201318 MPG)','Fringe Rotation (5\u201310 MPG)']),
  conferences: new Set(),
  teams:       new Set(),
  roles:       new Set(),
  yrsD1:       new Set(),
  minGames:    5,
  minHeight:   0,
  maxHeight:   999,
  name:        '',
};

// ── LOAD ──────────────────────────────────────────────────────────────────────
async function loadExplorerYear(year) {
  if (EXPLORER_CACHE[year]) return EXPLORER_CACHE[year];
  const r = await fetch(`player_data/layer2_explorer/players_${year}.json`);
  const data = await r.json();
  EXPLORER_CACHE[year] = data;
  return data;
}

async function initExplorer() {
  const yearSel = document.getElementById('explorer-year-select');
  if (!yearSel) return;
  if (yearSel.options.length === 0) {
    const years = [2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016];
    yearSel.innerHTML = years.map(y=>`<option value="${y}" ${y===2026?'selected':''}>${yLabel(y)}</option>`).join('');
  }
  const year = parseInt(yearSel.value)||2026;
  if (cExplorerData.length>0 && cExplorerYear===year) { renderExplorerTable(); return; }
  await loadAndRenderExplorer();
}

async function loadAndRenderExplorer() {
  const wrap = document.getElementById('explorer-table-wrap');
  const empty = document.getElementById('explorer-empty');
  const loading = document.getElementById('explorer-loading');
  empty.style.display='none'; loading.style.display='flex'; wrap.style.display='none';
  try {
    const year = parseInt(document.getElementById('explorer-year-select').value);
    cExplorerYear = year;
    cExplorerData = await loadExplorerYear(year);
    // Clear built flags so conference and team dropdowns rebuild for the new year
    const _cw = document.getElementById('mf-conference');
    const _tw = document.getElementById('mf-team');
    if (_cw) { _cw.dataset.built=''; _cw.innerHTML=''; }
    if (_tw) { _tw.dataset.built=''; _tw.innerHTML=''; }
    buildExplorerFilters();
    applyExplorerFilters();
    loading.style.display='none'; wrap.style.display='block';
    renderExplorerTable();
  } catch(e) {
    loading.style.display='none'; empty.style.display='flex';
    empty.textContent='Error loading player data: '+e.message;
  }
}

// ── BUILD FILTER UI ───────────────────────────────────────────────────────────
function buildExplorerFilters() {
  // Conference dropdown (built once per data load)
  const confWrap = document.getElementById('mf-conference');
  if (confWrap && !confWrap.dataset.built) {
    confWrap.dataset.built = '1';
    const confs = [...new Set(cExplorerData.map(p=>p.conference).filter(Boolean))].sort();
    buildCheckboxDropdown(confWrap, 'Conference', confs, EF.conferences);
  }

  // Team dropdown
  const teamWrap = document.getElementById('mf-team');
  if (teamWrap && !teamWrap.dataset.built) {
    teamWrap.dataset.built = '1';
    const teams = [...new Set(cExplorerData.map(p=>p.team).filter(Boolean))].sort();
    buildCheckboxDropdown(teamWrap, 'Team', teams, EF.teams);
  }

  // Role buttons — sorted by position group
  const roleWrap = document.getElementById('mf-role');
  if (roleWrap && !roleWrap.dataset.built) {
    roleWrap.dataset.built = '1';
    const roles = [...new Set(cExplorerData.map(p=>p.role).filter(Boolean))];
    const rolePos = {};
    cExplorerData.forEach(p=>{ if(p.role&&p.position) rolePos[p.role]=p.position; });
    const posOrder = {'Guard':0,'Wing':1,'Big':2};
    roles.sort((a,b)=>{
      const pa=posOrder[rolePos[a]]??3, pb=posOrder[rolePos[b]]??3;
      if(pa!==pb) return pa-pb;
      if(a==='C'&&b==='PF/C') return 1;
      if(a==='PF/C'&&b==='C') return -1;
      return a.localeCompare(b);
    });
    roles.forEach(r=>{
      const btn=document.createElement('button');
      btn.className='mf-btn active'; btn.dataset.value=r; btn.textContent=r;
      btn.onclick=()=>toggleEF(EF.roles,r,roles,'#mf-role');
      roleWrap.appendChild(btn);
    });
  }

  // Yrs D1 buttons
  const yrsWrap = document.getElementById('mf-years-d1');
  if (yrsWrap && !yrsWrap.dataset.built) {
    yrsWrap.dataset.built = '1';
    ['1','2','3','4','5+'].forEach(y=>{
      const btn=document.createElement('button');
      btn.className='mf-btn active'; btn.dataset.value=y; btn.textContent=y+(y==='5+'?'':' yr');
      btn.onclick=()=>toggleEF(EF.yrsD1,y,['1','2','3','4','5+'],'#mf-years-d1');
      yrsWrap.appendChild(btn);
    });
  }

  // Stat filter dropdown
  const sfSel = document.getElementById('sf-stat-select');
  const pfSel = document.getElementById('pf-stat-select');
  if (sfSel && sfSel.options.length <= 1) {
    const seen = new Set();
    Object.values(EXPLORER_STAT_TABS).flat().filter(s=>!s.computed&&!STRING_KEYS_E.has(s.key)).forEach(s=>{
      if (seen.has(s.key)) return; seen.add(s.key);
      const o=document.createElement('option'); o.value=s.key; o.textContent=s.label.replace('\n',' '); sfSel.appendChild(o);
      if(pfSel){const o2=document.createElement('option');o2.value=s.key;o2.textContent=s.label.replace('\n',' ');pfSel.appendChild(o2);}
    });
    // Add per-game shooting volume stats grouped with their related stats
    const pgStats = [
      // Overall
      {key:'fga_pg',label:'FGA/G'},{key:'fgm_pg',label:'FGM/G'},
      {key:'two_att_pg',label:'2PT Att/G'},{key:'two_made_pg',label:'2PT Made/G'},
      // 3PT
      {key:'three_att_pg',label:'3PT Att/G'},{key:'three_made_pg',label:'3PT Made/G'},
      // Rim
      {key:'rim_att_pg',label:'Rim Att/G'},{key:'rim_made_pg',label:'Rim Made/G'},
      {key:'close_two_att_pg',label:'Close 2 Att/G'},{key:'close_two_made_pg',label:'Close 2 Made/G'},
      {key:'dunk_att_pg',label:'Dunk Att/G'},{key:'dunk_made_pg',label:'Dunk Made/G'},
      // Midrange
      {key:'midrange_att_pg',label:'Midrange Att/G'},{key:'midrange_made_pg',label:'Midrange Made/G'},
      // FT
      {key:'ft_att_pg',label:'FT Att/G'},{key:'ft_made_pg',label:'FT Made/G'},
    ];
    pgStats.forEach(s=>{ if(seen.has(s.key)) return; seen.add(s.key); const o=document.createElement('option'); o.value=s.key; o.textContent=s.label; sfSel.appendChild(o); });
  }

  // Height slider bounds
  const heights = cExplorerData.map(p=>parseInt(p.height_in)).filter(h=>!isNaN(h));
  const minH = Math.min(...heights), maxH = Math.max(...heights);
  EF.minHeight = minH; EF.maxHeight = maxH;
  const minSlider = document.getElementById('slider-min-height');
  const maxSlider = document.getElementById('slider-max-height');
  if (minSlider && !minSlider.dataset.built) {
    minSlider.dataset.built='1';
    minSlider.min=minH; minSlider.max=maxH; minSlider.value=minH;
    maxSlider.min=minH; maxSlider.max=maxH; maxSlider.value=maxH;
    updateHeightLabel();
  }
}

function buildCheckboxDropdown(container, label, values, stateSet) {
  const btn = document.createElement('button');
  btn.className = 'mf-dropdown-btn';
  btn.innerHTML = label + ' <span>▾</span>';
  const menu = document.createElement('div');
  menu.className = 'mf-dropdown-menu';
  menu.style.display = 'none';
  menu.addEventListener('click', e => e.stopPropagation());
  const search = document.createElement('input');
  search.type='text'; search.placeholder='Search...'; search.className='mf-search';
  search.oninput = () => {
    const q = search.value.toLowerCase();
    menu.querySelectorAll('.mf-check-item[data-val]').forEach(item=>{
      item.style.display = item.dataset.val.toLowerCase().includes(q)?'':'none';
    });
  };
  menu.appendChild(search);
  const totalCount = values.length;
  const updateBtn = () => {
    let display;
    if (stateSet.size === 0) {
      display = label + ': All';
    } else if (stateSet.size === totalCount) {
      display = label + ': None';
    } else {
      // Show how many are selected (total minus filtered-out)
      const selectedCount = totalCount - stateSet.size;
      display = label + ' (' + selectedCount + ')';
    }
    btn.innerHTML = display + ' <span>▾</span>';
  };
  const actionRow = document.createElement('div');
  actionRow.className = 'mf-action-row';
  const selAllBtn = document.createElement('button');
  selAllBtn.className='mf-action-btn'; selAllBtn.textContent='Select All';
  selAllBtn.onclick = () => {
    stateSet.clear(); // empty = all selected
    menu.querySelectorAll('.mf-check-item[data-val] input').forEach(c=>c.checked=true);
    updateBtn(); onExplorerFilterChange();
  };
  const deselAllBtn = document.createElement('button');
  deselAllBtn.className='mf-action-btn'; deselAllBtn.textContent='Deselect All';
  deselAllBtn.onclick = () => {
    stateSet.clear();
    values.forEach(v=>stateSet.add(v)); // all in set = none visible
    menu.querySelectorAll('.mf-check-item[data-val] input').forEach(c=>c.checked=false);
    updateBtn(); onExplorerFilterChange();
  };
  actionRow.appendChild(selAllBtn); actionRow.appendChild(deselAllBtn);
  menu.appendChild(actionRow);
  values.forEach(v => {
    const item = document.createElement('label');
    item.className='mf-check-item'; item.dataset.val=v;
    const cb = document.createElement('input'); cb.type='checkbox';
    cb.checked = stateSet.size===0 || stateSet.has(v);
    cb.onchange = () => {
      if (cb.checked) {
        // User checked this item - remove from excluded set
        stateSet.delete(v);
      } else {
        // User unchecked - if was "all", initialize excluded set with just this item
        if (stateSet.size === 0) {
          // Was showing all, now exclude just this one
          stateSet.add(v);
        } else {
          stateSet.add(v);
        }
      }
      // If all excluded, treat as deselect all
      // If none excluded, treat as select all (clear)
      updateBtn(); onExplorerFilterChange();
    };
    item.appendChild(cb); item.appendChild(document.createTextNode(' '+v));
    menu.appendChild(item);
  });
  btn.onclick = e => {
    e.stopPropagation();
    const open = menu.style.display!=='none';
    document.querySelectorAll('.mf-dropdown-menu').forEach(m=>m.style.display='none');
    menu.style.display = open?'none':'block';
    if(menu.style.display!=='none') setTimeout(()=>search.focus(),50);
  };
  document.addEventListener('click', ()=>{ menu.style.display='none'; });
  container.appendChild(btn);
  container.appendChild(menu);
}

// ── FILTER TOGGLE FUNCTIONS (called from HTML) ────────────────────────────────
function toggleEF(stateSet, val, allVals, containerSelector) {
  if (stateSet.has(val)) { stateSet.delete(val); }
  else { stateSet.add(val); }
  if (stateSet.size === allVals.length) stateSet.clear();
  // Update button styles
  document.querySelectorAll(containerSelector+' .mf-btn').forEach(b=>{
    b.classList.toggle('active', stateSet.size===0 || stateSet.has(b.dataset.value));
  });
  onExplorerFilterChange();
}

function togglePosition(val,btn){ toggleEF(EF.positions,val,['Guard','Wing','Big'],'#mf-position'); }
function toggleLevel(val,btn){ toggleEF(EF.levels,val,['Power','Mid-Major'],'#mf-level'); }
function toggleClass(val,btn){ toggleEF(EF.classes,val,['FR','SO','JR','SR'],'#mf-class'); }
function toggleTier(val,btn){
  const allTiers=['Core Player (26+ MPG)','Primary Rotation (18\u201326 MPG)','Bench Rotation (10\u201318 MPG)','Fringe Rotation (5\u201310 MPG)','End of Bench (0\u20135 MPG)'];
  toggleEF(EF.tiers,val,allTiers,'#mf-mpg-tier');
}

function updateHeightLabel() {
  const minS = document.getElementById('slider-min-height');
  const maxS = document.getElementById('slider-max-height');
  if (!minS||!maxS) return;
  let lo=parseInt(minS.value), hi=parseInt(maxS.value);
  if(lo>hi){ minS.value=hi; lo=hi; }
  if(hi<lo){ maxS.value=lo; hi=lo; }
  const fmt=h=>`${Math.floor(h/12)}'${h%12}"`;
  const lblMin=document.getElementById('height-label-min');
  const lblMax=document.getElementById('height-label-max');
  if(lblMin) lblMin.textContent=fmt(lo);
  if(lblMax) lblMax.textContent=fmt(hi);
  EF.minHeight=lo; EF.maxHeight=hi;
  onExplorerFilterChange();
}

// ── APPLY FILTERS ─────────────────────────────────────────────────────────────
function applyExplorerFilters() {
  let data = [...cExplorerData];

  if (EF.positions.size>0) data=data.filter(p=>EF.positions.has(p.position));
  if (EF.levels.size>0)    data=data.filter(p=>EF.levels.has(p.power_mid));
  if (EF.classes.size>0)   data=data.filter(p=>EF.classes.has(p.class));
  if (EF.tiers.size>0)     data=data.filter(p=>EF.tiers.has(p.mpg_tier));
  if (EF.conferences.size>0) data=data.filter(p=>!EF.conferences.has(p.conference));

  if (EF.teams.size>0)  data=data.filter(p=>!EF.teams.has(p.team));
  if (EF.roles.size>0)  data=data.filter(p=>EF.roles.has(p.role));
  if (EF.yrsD1.size>0) {
    data=data.filter(p=>{
      const y=parseInt(p.years_in_d1);
      return EF.yrsD1.has(y>=5?'5+':String(y));
    });
  }

  // Min games
  data=data.filter(p=>parseInt(p.games)>=(EF.minGames||0));

  // Height
  data=data.filter(p=>{
    const h=parseInt(p.height_in);
    return isNaN(h)||(h>=EF.minHeight&&h<=EF.maxHeight);
  });

  // Name search
  if (EF.name) {
    const q=EF.name.toLowerCase();
    data=data.filter(p=>p.name&&p.name.toLowerCase().includes(q));
  }

  // Stat threshold filters
  cExplorerStatFilters.forEach(f=>{
    data=data.filter(p=>{
      const v=parseFloat(p[f.stat]);
      if(isNaN(v)) return false;
      if(f.min!==''&&!isNaN(f.min)&&v<parseFloat(f.min)) return false;
      if(f.max!==''&&!isNaN(f.max)&&v>parseFloat(f.max)) return false;
      return true;
    });
  });

  // Percentile filters
  cExplorerPctFilters.forEach(f=>{
    const pctKey = f.stat + PCT_SUFFIX[f.ctx];
    data=data.filter(p=>{
      const v=parseFloat(p[pctKey]);
      if(isNaN(v)) return false;
      // Convert to 0-100 scale for user-friendly input
      const pct100 = v * 100;
      if(f.min!==''&&!isNaN(f.min)&&pct100<parseFloat(f.min)) return false;
      if(f.max!==''&&!isNaN(f.max)&&pct100>parseFloat(f.max)) return false;
      return true;
    });
  });

  // Sort
  data.sort((a,b)=>{
    const av=parseFloat(a[cExplorerSort.key]), bv=parseFloat(b[cExplorerSort.key]);
    if(isNaN(av)&&isNaN(bv)) return 0;
    if(isNaN(av)) return 1; if(isNaN(bv)) return -1;
    return cExplorerSort.dir==='desc'?bv-av:av-bv;
  });

  cExplorerFiltered=data;
  cExplorerPage=1;
}

function onExplorerFilterChange() { applyExplorerFilters(); renderExplorerTable(); }

function setExplorerSort(key) {
  if(cExplorerSort.key===key) { cExplorerSort.dir=cExplorerSort.dir==='desc'?'asc':'desc'; }
  else { cExplorerSort.key=key; cExplorerSort.dir='desc'; }
  applyExplorerFilters(); renderExplorerTable();
}

function setExplorerStatTab(tab,btn) {
  cExplorerStatTab=tab;
  document.querySelectorAll('#explorer-stat-tabs .hist-cat-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  if(TAB_DEFAULT_SORT[tab]) { cExplorerSort={key:TAB_DEFAULT_SORT[tab],dir:'desc'}; }
  applyExplorerFilters(); renderExplorerTable();
}

function setExplorerPctContext(ctx,btn) {
  cExplorerPctContext=ctx;
  document.querySelectorAll('#explorer-pct-toggle .view-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  renderExplorerTable();
}

function addStatFilter() {
  const stat=document.getElementById('sf-stat-select').value;
  const min=document.getElementById('sf-min').value;
  const max=document.getElementById('sf-max').value;
  if(!stat) return;
  cExplorerStatFilters.push({stat,min,max});
  renderStatFilterTags(); applyExplorerFilters(); renderExplorerTable();
}

function removeStatFilter(i) {
  cExplorerStatFilters.splice(i,1);
  renderStatFilterTags(); applyExplorerFilters(); renderExplorerTable();
}

function addPctFilter() {
  const stat=document.getElementById('pf-stat-select').value;
  const ctx=document.getElementById('pf-context-select').value;
  const min=document.getElementById('pf-min').value;
  const max=document.getElementById('pf-max').value;
  if(!stat||!ctx) return;
  cExplorerPctFilters.push({stat,ctx,min,max});
  renderStatFilterTags(); applyExplorerFilters(); renderExplorerTable();
}

function removePctFilter(i) {
  cExplorerPctFilters.splice(i,1);
  renderStatFilterTags(); applyExplorerFilters(); renderExplorerTable();
}

function renderStatFilterTags() {
  const wrap=document.getElementById('stat-filter-tags');
  if(!wrap) return;
  const ctxLabels={national:'Natl',conf:'Conf',sub:'Power/Mid',pos:'Pos',pos_conf:'Pos+Conf',pos_sub:'Pos+P/Mid'};
  const statTags=cExplorerStatFilters.map((f,i)=>{
    const mn=f.min!==''?` ≥${f.min}`:'', mx=f.max!==''?` ≤${f.max}`:'';
    return `<span class="stat-filter-tag">${f.stat}${mn}${mx} <span class="stat-filter-remove" onclick="removeStatFilter(${i})">×</span></span>`;
  });
  const pctTags=cExplorerPctFilters.map((f,i)=>{
    const mn=f.min!==''?` ≥${f.min}th`:'', mx=f.max!==''?` ≤${f.max}th`:'';
    return `<span class="stat-filter-tag stat-filter-tag-pct">${f.stat} (${ctxLabels[f.ctx]||f.ctx})${mn}${mx} <span class="stat-filter-remove" onclick="removePctFilter(${i})">×</span></span>`;
  });
  wrap.innerHTML=[...statTags,...pctTags].join('');
}

function showMoreExplorer() {
  cExplorerPage++;
  renderExplorerTable(true);
}

// ── RENDER TABLE ──────────────────────────────────────────────────────────────
function explorerTip(key) {
  const t=EXPLORER_TIPS[key];
  if(!t) return '';
  return `<span class="info-icon" onclick="toggleTip(event,this)" style="margin-left:3px">i<span class="tooltip">${t}</span></span>`;
}

function explorerPctCls(pct) {
  if(pct>=0.85) return 'pct-elite';
  if(pct>=0.65) return 'pct-good';
  if(pct>=0.40) return 'pct-avg';
  if(pct>=0.20) return 'pct-below';
  return 'pct-poor';
}

function explorerStackedCell(raw, pctVal) {
  const pct=parseFloat(pctVal);
  if(isNaN(pct)) return `<span class="roster-raw-white">${raw}</span>`;
  const cls=explorerPctCls(pct);
  const pd=Math.round(pct*100);
  return `<div class="roster-pct-cell"><span class="roster-raw-val ${cls}">${raw}</span><div class="roster-pct-row"><span class="roster-pct-num ${cls}">${pd}</span><div class="roster-pct-bar-wrap"><div class="roster-pct-bar ${cls}-bar" style="width:${pd}%"></div></div></div></div>`;
}

function renderExplorerTable(append=false) {
  const wrap=document.getElementById('explorer-table-wrap');
  if(!wrap) return;

  if(!cExplorerFiltered.length) {
    wrap.innerHTML='<div class="empty-state">No players match the current filters.</div>';
    updateExplorerCount();
    return;
  }

  const stats=EXPLORER_STAT_TABS[cExplorerStatTab];
  const pctSuffix=PCT_SUFFIX[cExplorerPctContext]||'_pct';
  const pageEnd=cExplorerPage*EXPLORER_PAGE_SIZE;
  const display=cExplorerFiltered.slice(0,pageEnd);
  const sortedStatIdx=stats.findIndex(s=>s.key===cExplorerSort.key);
  const totalSeason=cExplorerData.length;

  let html=`<div class="explorer-table-scroll-wrap"><table class="roster-table explorer-table"><thead><tr>`;

  // Rank
  html+=`<th class="explorer-rank-th" style="min-width:28px;width:28px;max-width:28px;text-align:center;padding:0 4px;background:var(--surface2);color:var(--text4);font-size:10px;">#</th>`;

  // Frozen cols
  EXPLORER_FROZEN.forEach(col=>{
    const lbl=col.label.replace('\n','<br>');
    const isLast=col.key==='position';
    const isSorted=cExplorerSort.key===col.key;
    const sortIcon=isSorted?(cExplorerSort.dir==='desc'?' ▾':' ▴'):'';
    const sortedCls=isSorted?' explorer-col-sorted':'';
    // Sortable identity cols (not name/team/position)
    const sortable=['height_in','games','minutes_per_game','age','recruit_rank_clean','years_in_d1'].includes(col.key);
    const clickable=sortable?`onclick="setExplorerSort('${col.key}')" style="cursor:pointer;"`:'';
    if(col.frozen) {
      html+=`<th class="roster-frozen-th explorer-id-th${isLast?' explorer-last-frozen':''}${sortedCls}" ${clickable} style="position:sticky;left:${col.left}px;z-index:4;min-width:${col.width}px;max-width:${col.width}px;background:var(--surface2);">${lbl}${sortIcon}</th>`;
    } else {
      const tipHtml=col.tip?explorerTip(col.key):'';
      html+=`<th class="roster-frozen-th roster-scroll-th${sortedCls}" ${clickable}>${lbl}${sortIcon}${tipHtml}</th>`;
    }
  });

  // Stat headers
  stats.forEach((s,i)=>{
    const lbl=s.label.replace('\n','<br>');
    const tipDir=i>=stats.length-4?'tip-left':'';
    const isSorted=cExplorerSort.key===s.key;
    const sortIcon=isSorted?(cExplorerSort.dir==='desc'?' \u25be':' \u25b4'):'';
    const sortedCls=isSorted?' explorer-col-sorted':'';
    const clickable=!s.computed&&!s.noBar?'onclick="setExplorerSort(\''+s.key+'\')" style="cursor:pointer;"':'';
    html+=`<th class="roster-stat-th ${tipDir}${sortedCls}" ${clickable}>${lbl}${sortIcon}${explorerTip(s.key)}</th>`;
  });

  html+=`</tr></thead><tbody>`;

  display.forEach((p,idx)=>{
    const isTier2=p.percentile_tier==='Tier 2';
    const noPercentile=!p.percentile_eligible||p.percentile_eligible===false||p.percentile_eligible==='False';
    const rowCls=isTier2?'roster-row roster-tier2':'roster-row';
    html+=`<tr class="${rowCls}">`;
    html+=`<td class="explorer-rank-cell" style="min-width:28px;width:28px;max-width:28px;text-align:center;padding:0 4px;font-size:11px;color:var(--text4);border-bottom:1px solid var(--border);">${idx+1}</td>`;

    EXPLORER_FROZEN.forEach(col=>{
      const val=p[col.key];
      const disp=col.fmt?col.fmt(val):(val??'—');
      const isLast=col.key==='position';
      if(col.frozen) {
        html+=`<td class="roster-frozen-td explorer-id-cell${isLast?' explorer-last-frozen':''}" style="position:sticky;left:${col.left}px;z-index:2;min-width:${col.width}px;max-width:${col.width}px;overflow:hidden;text-overflow:ellipsis;background:var(--surface);">${disp}</td>`;
      } else {
        html+=`<td class="roster-frozen-td roster-scroll-td">${disp}</td>`;
      }
    });

    stats.forEach((s,si)=>{
      const isSortedCol=si===sortedStatIdx;
      const sortedTd=isSortedCol?' explorer-col-sorted':'';
      const rawVal=s.computed?null:p[s.key];
      const isString=STRING_KEYS_E.has(s.key)||s.noBar;

      if(isString) {
        const disp=s.computed?s.fmt(null,p):s.fmt(rawVal);
        html+=`<td class="roster-stat-td${sortedTd}"><span class="roster-raw-white">${disp??'—'}</span></td>`;
        return;
      }

      let rawDisplay;
      if(DRTG_DELTA_KEYS_E.has(s.key)) {
        const v=parseFloat(rawVal); rawDisplay=isNaN(v)?'—':fmtDrtgDelta(rawVal);
      } else {
        rawDisplay=(rawVal==null||isNaN(parseFloat(rawVal)))?'—':s.fmt(rawVal);
      }

      const pctKey=s.key+pctSuffix;
      const pctVal=p[pctKey];
      const hasPct=pctVal!=null;

      if(noPercentile||!hasPct) {
        html+=`<td class="roster-stat-td${sortedTd}"><span class="roster-raw-white">${rawDisplay}</span></td>`;
        return;
      }
      html+=`<td class="roster-stat-td${sortedTd}">${explorerStackedCell(rawDisplay,pctVal)}</td>`;
    });
    html+=`</tr>`;
  });

  if(cExplorerFiltered.length>pageEnd) {
    html+=`<tr><td class="explorer-more-row" style="text-align:left;padding-left:8px;"><button class="view-btn" onclick="showMoreExplorer()">Show More (${cExplorerFiltered.length-pageEnd} remaining)</button></td><td colspan="999"></td></tr>`;
  }

  html+=`</tbody></table></div>`;
  const hint='<div class="explorer-sort-hint">Click any column header to sort</div>';
  wrap.innerHTML=hint+html;

  updateExplorerCount();
  setTimeout(syncExplorerScrollbar,60);
  setTimeout(initStickyExplorerHeader,80);
}

// ── STICKY HEADER CLONE ───────────────────────────────────────────────────────
function initStickyExplorerHeader() {
  const scrollWrap = document.querySelector('#explorer-table-wrap .explorer-table-scroll-wrap');
  const table = scrollWrap ? scrollWrap.querySelector('table') : null;
  const realThead = table ? table.querySelector('thead tr') : null;
  if (!scrollWrap || !realThead) return;

  // Remove any existing clone
  const existing = document.getElementById('explorer-sticky-header');
  if (existing) existing.remove();

  // Create sticky header container
  const stickyWrap = document.createElement('div');
  stickyWrap.id = 'explorer-sticky-header';
  stickyWrap.style.cssText = 'position:sticky;top:0;z-index:10;overflow:hidden;background:var(--surface2);display:none;border-bottom:2px solid var(--border2);';

  // Clone the header into a matching table
  const cloneTable = document.createElement('table');
  cloneTable.className = 'roster-table explorer-table';
  cloneTable.style.cssText = 'margin:0;border-collapse:collapse;white-space:nowrap;';
  const cloneThead = document.createElement('thead');
  const cloneRow = realThead.cloneNode(true);
  cloneThead.appendChild(cloneRow);
  cloneTable.appendChild(cloneThead);
  stickyWrap.appendChild(cloneTable);

  // Insert sticky header before the scroll wrap inside explorer-table-wrap
  const tableWrap = document.getElementById('explorer-table-wrap');
  tableWrap.insertBefore(stickyWrap, scrollWrap);

  // Sync column widths from real header to clone
  function syncWidths() {
    const realCells = realThead.querySelectorAll('th');
    const cloneCells = cloneRow.querySelectorAll('th');
    realCells.forEach((cell, i) => {
      if (cloneCells[i]) {
        const w = cell.getBoundingClientRect().width;
        cloneCells[i].style.minWidth = w + 'px';
        cloneCells[i].style.maxWidth = w + 'px';
        cloneCells[i].style.width = w + 'px';
      }
    });
    // Match total table width
    cloneTable.style.width = table.getBoundingClientRect().width + 'px';
  }

  // Sync horizontal scroll between sticky header and table
  scrollWrap.addEventListener('scroll', () => {
    stickyWrap.scrollLeft = scrollWrap.scrollLeft;
  });

  // Show/hide sticky header based on whether real thead is visible
  const tableWrapEl = document.getElementById('explorer-table-wrap');
  function onScroll() {
    const theadRect = realThead.getBoundingClientRect();
    const wrapRect = tableWrapEl.getBoundingClientRect();
    if (theadRect.bottom < wrapRect.top + 10) {
      if (stickyWrap.style.display === 'none') {
        syncWidths();
        stickyWrap.style.display = 'block';
      }
      stickyWrap.scrollLeft = scrollWrap.scrollLeft;
    } else {
      stickyWrap.style.display = 'none';
    }
  }

  window.addEventListener('scroll', onScroll, {passive: true});
  // Store cleanup ref
  if (window._explorerScrollListener) {
    window.removeEventListener('scroll', window._explorerScrollListener);
  }
  window._explorerScrollListener = onScroll;

  syncWidths();
}

function resetExplorerFilters() {
  // Reset EF state
  EF.positions.clear();
  EF.levels.clear();
  EF.classes.clear();
  EF.conferences.clear();
  EF.teams.clear();
  EF.roles.clear();
  EF.yrsD1.clear();
  EF.tiers.clear();
  ['Core Player (26+ MPG)','Primary Rotation (18–26 MPG)','Bench Rotation (10–18 MPG)','Fringe Rotation (5–10 MPG)'].forEach(t=>EF.tiers.add(t));
  EF.minGames = 5;
  EF.name = '';
  EF.minHeight = 0;
  EF.maxHeight = 999;

  // Reset name search
  const nameEl = document.getElementById('ef-name-search');
  if (nameEl) nameEl.value = '';

  // Reset min games
  const gamesEl = document.getElementById('ef-min-games');
  if (gamesEl) gamesEl.value = 5;

  // Reset stat filter dropdowns
  const sfStat = document.getElementById('sf-stat-select');
  const sfMin = document.getElementById('sf-min');
  const sfMax = document.getElementById('sf-max');
  if (sfStat) sfStat.value = '';
  if (sfMin) sfMin.value = '';
  if (sfMax) sfMax.value = '';

  // Reset percentile filter dropdowns
  const pfStat = document.getElementById('pf-stat-select');
  const pfCtx = document.getElementById('pf-context-select');
  const pfMin = document.getElementById('pf-min');
  const pfMax = document.getElementById('pf-max');
  if (pfStat) pfStat.value = '';
  if (pfCtx) pfCtx.value = 'national';
  if (pfMin) pfMin.value = '';
  if (pfMax) pfMax.value = '';

  // Reset height sliders
  const minS = document.getElementById('slider-min-height');
  const maxS = document.getElementById('slider-max-height');
  if (minS && maxS) {
    minS.value = minS.min;
    maxS.value = maxS.max;
    updateHeightLabel();
  }

  // Reset all button groups — all active
  ['#mf-position','#mf-level','#mf-class'].forEach(sel => {
    document.querySelectorAll(sel + ' .mf-btn').forEach(b => b.classList.add('active'));
  });

  // Reset role and yrs D1 button groups
  ['#mf-role','#mf-years-d1'].forEach(sel => {
    document.querySelectorAll(sel + ' .mf-btn').forEach(b => b.classList.add('active'));
  });

  // Reset MPG tier — all except EOB
  document.querySelectorAll('#mf-mpg-tier .mf-btn').forEach(b => {
    const isEOB = b.dataset.value && b.dataset.value.includes('End of Bench');
    b.classList.toggle('active', !isEOB);
  });

  // Reset conference and team dropdowns
  ['#mf-conference','#mf-team'].forEach(sel => {
    // Check all checkboxes
    document.querySelectorAll(sel + ' .mf-check-item[data-val] input').forEach(cb => cb.checked = true);
    // Reset button label
    const btn = document.querySelector(sel + ' .mf-dropdown-btn');
    if (btn) {
      const lbl = sel === '#mf-conference' ? 'Conference' : 'Team';
      btn.innerHTML = lbl + ': All <span>▾</span>';
    }
  });

  // Reset stat threshold and percentile filters
  cExplorerStatFilters = [];
  cExplorerPctFilters = [];
  renderStatFilterTags();

  // Reset sort to default
  cExplorerSort = {key: 'bpm', dir: 'desc'};

  // Reset percentile context to national
  cExplorerPctContext = 'national';
  document.querySelectorAll('#explorer-pct-toggle .view-btn').forEach((b,i) => {
    b.classList.toggle('active', i === 0);
  });

  applyExplorerFilters();
  renderExplorerTable();
}

function updateExplorerCount() {
  const el=document.getElementById('explorer-count');
  if(!el) return;
  const total=cExplorerData.length;
  const filtered=cExplorerFiltered.length;
  el.textContent=filtered===total?`${total.toLocaleString()} players`:`${filtered.toLocaleString()} of ${total.toLocaleString()} players`;
}

// ── TOP SCROLLBAR SYNC ────────────────────────────────────────────────────────
function syncExplorerScrollbar() {
  const topBar=document.getElementById('explorer-scroll-top');
  const tableWrap=document.querySelector('#explorer-table-wrap .explorer-table-scroll-wrap');
  if(!topBar||!tableWrap) return;
  const table=tableWrap.querySelector('table');
  if(table) topBar.querySelector('div').style.width=table.offsetWidth+'px';
  topBar.onscroll=()=>{ tableWrap.scrollLeft=topBar.scrollLeft; };
  tableWrap.onscroll=()=>{ topBar.scrollLeft=tableWrap.scrollLeft; };
}
