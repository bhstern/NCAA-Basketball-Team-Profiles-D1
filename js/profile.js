// ── PLAYER PROFILE ────────────────────────────────────────────────────────────
// Slice 1: identity card + career table (seasons as rows, most recent first).
// Reuses the explorer's formatters + cell renderer (explorerStackedCell) and its
// tooltip map (EXPLORER_TIPS/explorerTip) so cells + headers match the Player Explorer.
// Career table uses NATIONAL percentile (stat + '_pct') — fixed reference pool across
// seasons, so year-over-year moves aren't distorted by position changes.

let cPlayer = null;              // loaded career file {player_id, name, seasons:[...]}
let cPlayerStatTab = 'overview'; // active career-table stat group
let cPlayerPctContext = 'national'; // percentile context for the cells (profile files carry 4)
let cPlayerView = 'career';         // top-level sub-view: 'career' | 'shots' | 'trends'
let cPlayerInitView = 'career';     // view to land on after load (for ?view= deep links)
let cPlayerShotSeason = null;       // selected season (year) for shot charts; null → most recent
let cPlayerShotBasis = 'national';  // shot-chart percentile basis: 'national' | 'pos'
let cPlayerShotCompare = false;     // stack the previous season below
const PF_CONTEXTS = [
  {key:'national', label:'National'},
  {key:'conf',     label:'Conference'},
  {key:'sub',      label:'Power/Mid'},
  {key:'pos',      label:'Position'},
  {key:'pos_conf', label:'Pos + Conf'},
  {key:'pos_sub',  label:'Pos + Power/Mid'},
];

function pfHeightStr(inches){
  const i = parseInt(inches);
  if (isNaN(i)) return null;
  return Math.floor(i/12) + "'" + (i%12) + '"';
}

function pfLatest(seasons){
  return seasons.slice().sort((a,b)=>(b.year||0)-(a.year||0))[0];
}

// ── entry point: roster/explorer row click, or a ?pid= deep link ──
async function openPlayerProfile(playerId, initView){
  if(!playerId) return;
  cPlayerInitView = (initView==='trends'||initView==='shots') ? initView : 'career';
  cTab='player';
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el=>el.classList.remove('active'));
  const cont=document.getElementById('tab-player');
  if(cont) cont.classList.add('active');
  const banner=document.getElementById('banner'), desc=document.getElementById('page-desc');
  if(banner) banner.style.display='none';
  if(desc) desc.style.display='none';
  history.replaceState(null,'','?tab=player&pid='+encodeURIComponent(playerId));

  const empty=document.getElementById('player-empty');
  const loading=document.getElementById('player-loading');
  const content=document.getElementById('player-content');
  if(empty) empty.style.display='none';
  if(content) content.style.display='none';
  if(loading) loading.style.display='block';

  try{
    const res=await fetch('player_data/layer2_profiles/player_'+playerId+'.json');
    if(!res.ok) throw new Error('not found');
    cPlayer=await res.json();
    cPlayerStatTab='overview';
    cPlayerView='career'; cPlayerShotSeason=null; cPlayerShotCompare=false;
    renderPlayerProfile();
    if(loading) loading.style.display='none';
    if(content) content.style.display='block';
  }catch(e){
    if(loading) loading.style.display='none';
    if(empty){ empty.style.display='block'; empty.textContent='Could not load this player profile.'; }
  }
  window.scrollTo(0,0);
}

function renderPlayerProfile(){
  if(!cPlayer) return;
  document.getElementById('player-identity').innerHTML = pfIdentityCard();
  const seasonsDesc=cPlayer.seasons.slice().sort((a,b)=>(b.year||0)-(a.year||0));
  const trend=pfComputeTrending(seasonsDesc);
  const th=document.getElementById('player-trending-header'); if(th) th.innerHTML=pfTrendingHeaderHTML(trend);
  const tv=document.getElementById('player-trends'); if(tv) tv.innerHTML=pfTrendsTabHTML(trend);
  const tb=document.getElementById('player-trends-btn'); if(tb) tb.style.display = trend.singleSeason ? 'none' : '';  // tab only for 2+ seasons
  // reset to Career Stats view on load
  document.querySelectorAll('#player-view-nav .pf-view-btn').forEach(b=>b.classList.remove('active'));
  const c0=document.querySelector('#player-view-nav .pf-view-btn'); if(c0) c0.classList.add('active');
  document.getElementById('player-career-view').style.display='';
  document.getElementById('player-shots-view').style.display='none';
  const trv=document.getElementById('player-trends-view'); if(trv) trv.style.display='none';
  renderPlayerCareer();
  // land on a deep-linked view if requested (and available)
  if(cPlayerInitView==='shots') switchPlayerView('shots');
  else if(cPlayerInitView==='trends' && tb && tb.style.display!=='none') switchPlayerView('trends');
}

// top-level sub-view switch (Career Stats / Trends / Shot Charts)
function switchPlayerView(view, btn){
  cPlayerView=view;
  document.querySelectorAll('#player-view-nav .pf-view-btn').forEach(b=>b.classList.remove('active'));
  const activeBtn = btn || document.querySelector(`#player-view-nav .pf-view-btn[data-view="${view}"]`);
  if(activeBtn) activeBtn.classList.add('active');
  document.getElementById('player-career-view').style.display = view==='career'?'':'none';
  document.getElementById('player-shots-view').style.display  = view==='shots'?'':'none';
  const trv=document.getElementById('player-trends-view'); if(trv) trv.style.display = view==='trends'?'':'none';
  if(view==='shots') renderPlayerShots();
  // keep the URL in sync so the address bar is shareable (?pid=...&view=...)
  if(cPlayer && cPlayer.player_id){
    history.replaceState(null,'','?tab=player&pid='+encodeURIComponent(cPlayer.player_id)+'&view='+view);
  }
}

// ── identity card (from the most recent season) ──
function pfIdentityCard(){
  const s = pfLatest(cPlayer.seasons);
  const bits1 = [s.position, s.role, pfHeightStr(s.height_in), s.class,
                 (s.age!=null && !isNaN(s.age) ? parseFloat(s.age).toFixed(1)+' yrs' : null)].filter(Boolean);
  const teamLink = s.team?`<span class="pf-link" onclick="goToTeamProfile('${jsq(s.team)}', ${s.year})">${s.team}</span>`:null;
  const teamLine = [teamLink, s.conference?`(${s.conference})`:null].filter(Boolean).join(' ');
  // recruit_rank_clean is a 0–100 grade (100 = best), not a rank.
  const rr = (s.recruit_rank_clean!=null && !isNaN(s.recruit_rank_clean))
             ? 'Recruit grade '+Math.round(s.recruit_rank_clean)+'/100' : 'Unrated recruit';
  const home = [s.hometown_city, s.hometown_state].filter(Boolean).join(', ');
  const d1 = (s.years_in_d1!=null && !isNaN(s.years_in_d1))
             ? parseInt(s.years_in_d1)+ ' yr' + (parseInt(s.years_in_d1)===1?'':'s') + ' D1' : null;
  const bits3 = [home, rr, d1].filter(Boolean);
  return `
    <div class="pf-card">
      <div class="pf-name">${cPlayer.name||'—'}</div>
      <div class="pf-line pf-what">${bits1.join(' · ')}</div>
      ${teamLine?`<div class="pf-line pf-team">${teamLine}</div>`:''}
      ${bits3.length?`<div class="pf-line pf-bg">${bits3.join(' · ')}</div>`:''}
    </div>`;
}

function switchPlayerStatTab(tab, btn){
  cPlayerStatTab=tab;
  document.querySelectorAll('#player-cat-nav .hist-cat-btn').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  renderPlayerCareer();
}

function switchPlayerPctContext(ctx){
  cPlayerPctContext=ctx;
  renderPlayerCareer();   // re-render rebuilds the toggle with the new active state
}

// season-total made/att string, e.g. "146/222" (raw counts, no percentile → value-only cell)
function fmtTotMA(p, mk, ak){
  const m=p[mk], a=p[ak];
  if(m==null||a==null||isNaN(parseFloat(m))||isNaN(parseFloat(a))) return '—';
  return Math.round(m)+'/'+Math.round(a);
}

// Shooting group, defined explicitly (the profile intentionally diverges from the
// explorer here): efficiency headline, then each shot type as one contiguous block
// led by its season-total volume, with rate/%/per-game following. Made/att columns
// are labeled Total vs Per Game on a third line. Ratios dropped (redundant + unstable).
function pfShootingStats(){
  const dec=v=>fmtPctDecE(v);     // 0–1 → %
  const pct=v=>fmtPctE(v);        // already-% value
  const ma=(mp,ap)=>((v,p)=>fmtMAE(p,mp,ap));
  const tot=(mk,ak)=>((v,p)=>fmtTotMA(p,mk,ak));
  const MA={noBar:true,computed:true};
  return [
    {key:'ppp_used', label:'PPP\nUsed', fmt:v=>fmtNumE(v,3)},
    {key:'ts',  label:'TS%',  fmt:pct},
    {key:'efg', label:'eFG%', fmt:pct},
    // Field goals overall
    {key:'_tot_fg_ma', label:'FG\nFGM/FGA\nTotal',    ...MA, fmt:tot('total_fgm','total_fga')},
    {key:'total_fg_pct', label:'FG%', fmt:dec},
    {key:'_fgm_fga',   label:'FG\nFGM/FGA\nPer Game', ...MA, fmt:ma('fgm_pg','fga_pg')},
    // Three-point
    {key:'_tot_three_ma', label:'3PT\nFGM/FGA\nTotal',    ...MA, fmt:tot('three_pm','three_pa')},
    {key:'three_rate',   label:'3PT\nRate', fmt:dec},
    {key:'three_fg_pct', label:'3PT%', fmt:dec},
    {key:'_three_ma',    label:'3PT\nFGM/FGA\nPer Game', ...MA, fmt:ma('three_made_pg','three_att_pg')},
    {key:'three_p_per_100', label:'3PA\n/100', fmt:v=>fmtNumE(v,1)},
    // Two-point (overall pulled down here so all 2PT is contiguous, led by total)
    {key:'_tot_two_ma', label:'2PT\nFGM/FGA\nTotal',    ...MA, fmt:tot('two_pm','two_pa')},
    {key:'two_fg_pct',  label:'2PT\nFG%', fmt:dec},
    {key:'_two_ma',     label:'2PT\nFGM/FGA\nPer Game', ...MA, fmt:ma('two_made_pg','two_att_pg')},
    // Two-point zones, ordered farthest → closest: Midrange, then Rim (= Close 2 + Dunk)
    {key:'midrange_rate',   label:'Mid\nRate', fmt:dec},
    {key:'midrange_fg_pct', label:'Mid\nFG%', fmt:dec},
    {key:'_mid_ma',         label:'Mid\nFGM/FGA\nPer Game', ...MA, fmt:ma('midrange_made_pg','midrange_att_pg')},
    {key:'rim_rate',   label:'Rim\nRate', fmt:dec},
    {key:'rim_fg_pct', label:'Rim\nFG%', fmt:dec},
    {key:'_rim_ma',    label:'Rim\nFGM/FGA\nPer Game', ...MA, fmt:ma('rim_made_pg','rim_att_pg')},
    {key:'close_two_rate',   label:'Close 2\nRate', fmt:dec},
    {key:'close_two_fg_pct', label:'Close 2\nFG%', fmt:dec},
    {key:'_close_two_ma',    label:'Close 2\nFGM/FGA\nPer Game', ...MA, fmt:ma('close_two_made_pg','close_two_att_pg')},
    {key:'dunk_rate',   label:'Dunk\nRate', fmt:dec},
    {key:'dunk_fg_pct', label:'Dunk\nFG%', fmt:dec},
    {key:'_dunk_ma',    label:'Dunk\nFGM/FGA\nPer Game', ...MA, fmt:ma('dunk_made_pg','dunk_att_pg')},
    // Free throws
    {key:'_tot_ft_ma', label:'FT\nFTM/FTA\nTotal',    ...MA, fmt:tot('ftm','fta')},
    {key:'ft_rate', label:'FT\nRate', fmt:dec},
    {key:'ft_pct',  label:'FT%', fmt:dec},
    {key:'_ft_ma',  label:'FT\nFTM/FTA\nPer Game', ...MA, fmt:ma('ft_made_pg','ft_att_pg')},
  ];
}

// active stat group for the current tab
function pfActiveStats(){
  let stats;
  if(cPlayerStatTab==='shooting') stats=pfShootingStats();
  else stats=EXPLORER_STAT_TABS[cPlayerStatTab] || [];
  // Hide any non-computed column with no raw value in ANY season. Self-healing: context
  // deltas currently absent from the profile data (a pipeline drop, not missing data) are
  // hidden now, and reappear automatically once convert includes them — no frontend change.
  const seasons = cPlayer.seasons || [];
  return stats.filter(s => (s.computed || s.noBar) ||
    seasons.some(se => { const v=se[s.key]; return v!=null && !(typeof v==='number' && isNaN(v)); }));
}

// ── career table: seasons as rows, active stat group as columns ──
function renderPlayerCareer(){
  const wrap=document.getElementById('player-career');
  if(!wrap) return;
  const stats = pfActiveStats();
  const seasons = cPlayer.seasons.slice().sort((a,b)=>(b.year||0)-(a.year||0)); // most recent first

  // frozen left columns — kept visible while stat columns scroll. Fixed widths so we can
  // compute cumulative sticky left-offsets (Team + Role change across seasons and matter).
  const frozen = [
    {label:'Season', w:82,  get:s=> (typeof yLabel==='function'? yLabel(s.year) : s.year)},
    {label:'Team',   w:120, get:s=> s.team?`<span class="pf-link" onclick="goToTeamProfile('${jsq(s.team)}', ${s.year})">${s.team}</span>`:'—'},
    {label:'Yr',     w:40,  get:s=> s.class ?? '—'},
    {label:'Pos',    w:52,  get:s=> s.position ?? '—'},
    {label:'Role',   w:80,  get:s=> s.role ?? '—'},
    {label:'G',      w:38,  get:s=> s.games ?? '—'},
    {label:'MPG',    w:50,  get:s=> (s.minutes_per_game!=null? fmtNumE(s.minutes_per_game) : '—')},
  ];

  const stickyStyle=(left,w,z,bg)=>`position:sticky;left:${left}px;z-index:${z};width:${w}px;min-width:${w}px;max-width:${w}px;background:${bg};`;

  // percentile context applies to every tab except Context (those cells are already deltas-vs-X)
  const ctxActive = cPlayerStatTab!=='context';
  const pctSuffix = ctxActive ? (PCT_SUFFIX[cPlayerPctContext]||'_pct') : '_pct';

  let html='';
  if(ctxActive){
    html+='<div class="pf-ctx-toggle"><span class="pf-ctx-label">Percentiles vs</span>';
    PF_CONTEXTS.forEach(c=>{
      html+=`<button class="pf-ctx-btn${cPlayerPctContext===c.key?' active':''}" onclick="switchPlayerPctContext('${c.key}')">${c.label}</button>`;
    });
    html+='</div>';
  }

  html+='<div class="pf-table-scroll"><table class="roster-table pf-table"><thead><tr>';
  let left=0;
  frozen.forEach((f,i)=>{
    const last=i===frozen.length-1?' pf-frozen-last':'';
    html+=`<th class="pf-frozen-th${last}" style="${stickyStyle(left,f.w,4,'var(--surface2)')}">${f.label}</th>`;
    left+=f.w;
  });
  stats.forEach((s,i)=>{
    const tipDir=i>=stats.length-4?'tip-left':'';
    html+=`<th class="roster-stat-th ${tipDir}">${(s.label||s.key).replace(/\n/g,'<br>')}${(typeof explorerTip==='function'?explorerTip(s.key):'')}</th>`;
  });
  html+='<th class="pf-spacer"></th>';   // absorbs slack so frozen + stat columns keep their widths
  html+='</tr></thead><tbody>';

  seasons.forEach(season=>{
    html+='<tr>';
    let l=0;
    frozen.forEach((f,i)=>{
      const first=i===0?' pf-frozen-first':'';
      const last=i===frozen.length-1?' pf-frozen-last':'';
      html+=`<td class="pf-frozen-td${first}${last}" style="${stickyStyle(l,f.w,3,'var(--surface)')}">${f.get(season)}</td>`;
      l+=f.w;
    });
    stats.forEach(s=>{
      const rawDisplay = s.fmt ? s.fmt(season[s.key], season) : (season[s.key] ?? '—');
      const pctVal = (s.computed || (typeof STRING_KEYS_E!=='undefined' && STRING_KEYS_E.has(s.key)) || s.noBar)
                     ? null : season[s.key+pctSuffix];
      html+=`<td class="roster-stat-td">${explorerStackedCell(rawDisplay, pctVal)}</td>`;
    });
    html+='<td class="pf-spacer"></td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';
  wrap.innerHTML=html;
}

// ── SHOT CHARTS SUB-VIEW ──────────────────────────────────────────────────────
// Reuses shotcourt.js's buildCourtSVG + scPctColor. Per season: a Shot Rate court
// (colored by rate percentile) beside an FG% court (colored by FG% percentile),
// with per-zone season totals as a caption. Optional stacked previous-season pair.

const PF_SHOT_ZONES = {
  rim:  {rate:'rim_rate',      fg:'rim_fg_pct',      made:'rim_made',      att:'rim_att'},
  mid:  {rate:'midrange_rate', fg:'midrange_fg_pct', made:'midrange_made', att:'midrange_att'},
  three:{rate:'three_rate',    fg:'three_fg_pct',    made:'three_pm',      att:'three_pa'},
};

function pfInt(v){ return (v==null||isNaN(parseFloat(v))) ? '—' : Math.round(v); }

// build the zones object buildCourtSVG expects; metric decides which percentile colors the zones
function pfShotZones(season, sfx, metric){
  const out={};
  for(const z in PF_SHOT_ZONES){
    const d=PF_SHOT_ZONES[z];
    const rp=season[d.rate+sfx], fgp=season[d.fg+sfx];
    out[z]={ r:season[d.rate], rp:rp, fg:season[d.fg], fgp:fgp,
             color:scPctColor(metric==='rate'?rp:fgp) };
    if(metric==='fg') out[z].vol = pfInt(season[d.made])+'/'+pfInt(season[d.att]);  // volume shown on FG% chart only
  }
  return out;
}

function pfShotHeader(s){
  const bits=[ (typeof yLabel==='function'?yLabel(s.year):s.year), s.team, s.class,
    (s.years_in_d1!=null&&!isNaN(s.years_in_d1)?parseInt(s.years_in_d1)+' yr'+(parseInt(s.years_in_d1)===1?'':'s')+' D1':null),
    s.position, s.role ].filter(Boolean);
  return `<div class="pf-shot-header">${bits.join(' · ')}</div>`;
}

function pfSeasonCharts(s, sfx, compact){
  const zf = 18;   // stacking the percentile onto its own line buys room; same size in compare + single
  const base={showPct:true, showLabels:true, stackPct:true, zoneFont:zf};
  const rate=buildCourtSVG({...base, zones:pfShotZones(s,sfx,'rate'), metricsShown:'rate'});
  const fg  =buildCourtSVG({...base, zones:pfShotZones(s,sfx,'fg'),   metricsShown:'fg'});
  return `<div class="pf-shot-season">
    ${pfShotHeader(s)}
    <div class="pf-shot-courts${compact?' pf-shot-compact':''}">
      <div class="pf-shot-court"><div class="pf-shot-court-lbl">Shot Rate</div>${rate}</div>
      <div class="pf-shot-court"><div class="pf-shot-court-lbl">FG% &amp; Volume</div>${fg}</div>
    </div>
  </div>`;
}

function setPlayerShotSeason(y){ cPlayerShotSeason=parseInt(y); renderPlayerShots(); }
function setPlayerShotBasis(b){ cPlayerShotBasis=b; renderPlayerShots(); }
function setPlayerShotCompare(c){ cPlayerShotCompare=c; renderPlayerShots(); }

function renderPlayerShots(){
  const wrap=document.getElementById('player-shots');
  if(!wrap||!cPlayer) return;
  const seasons=cPlayer.seasons.slice().sort((a,b)=>(b.year||0)-(a.year||0)); // most recent first
  if(!seasons.length){ wrap.innerHTML='<div class="empty-state">No shot data for this player.</div>'; return; }

  if(cPlayerShotSeason==null) cPlayerShotSeason=seasons[0].year;
  const selected=seasons.find(s=>s.year===cPlayerShotSeason)||seasons[0];
  const idx=seasons.indexOf(selected);
  const prior=seasons[idx+1];         // next in desc order = chronologically previous season
  const canCompare=!!prior;
  const sfx=cPlayerShotBasis==='pos' ? '_pos_pct' : '_pct';

  let html='<div class="pf-shot-controls">';
  html+='<label class="pf-shot-lbl">Season</label><select class="pf-shot-select" onchange="setPlayerShotSeason(this.value)">';
  seasons.forEach(s=>{ html+=`<option value="${s.year}" ${s.year===selected.year?'selected':''}>${(typeof yLabel==='function'?yLabel(s.year):s.year)}</option>`; });
  html+='</select>';
  html+='<span class="pf-shot-lbl">Percentiles vs</span>';
  html+=`<button class="pf-ctx-btn${cPlayerShotBasis==='national'?' active':''}" onclick="setPlayerShotBasis('national')">National</button>`;
  html+=`<button class="pf-ctx-btn${cPlayerShotBasis==='pos'?' active':''}" onclick="setPlayerShotBasis('pos')">Position</button>`;
  if(canCompare) html+=`<label class="pf-shot-check"><input type="checkbox" ${cPlayerShotCompare?'checked':''} onchange="setPlayerShotCompare(this.checked)"> Compare to previous season</label>`;
  html+='</div>';

  // flag only when it actually contaminates the comparison: Position basis + position bucket changed
  if(cPlayerShotCompare && canCompare && cPlayerShotBasis==='pos' && selected.position!==prior.position){
    html+=`<div class="pf-shot-flag">Position changed (${prior.position} → ${selected.position}) — the two seasons are ranked against different position pools.</div>`;
  }

  html+=pfSeasonCharts(selected, sfx, cPlayerShotCompare);
  if(cPlayerShotCompare && canCompare) html+=pfSeasonCharts(prior, sfx, cPlayerShotCompare);
  wrap.innerHTML=html;
}

// ── TRENDING PANEL ────────────────────────────────────────────────────────────
// Auto-surfaces a player's biggest year-over-year improvements/declines + context.
// Compares the TWO most recent seasons only. Percentiles are direction-normalized
// upstream (higher = better for every stat, incl. TOV%/fouls), so a positive
// percentile delta = improvement uniformly. One representative per family (anti-proxy).

const PF_FAMILIES = [
  {name:'Scoring efficiency',  stat:'ts',              label:'Scoring Efficiency (TS%)',   floor:'total_fga',   chip:true,  vfmt:'pct100'},
  {name:'Scoring volume',      stat:'pts_per_40',      label:'Scoring Volume (Pts/40)',         floor:null,          chip:true,  vfmt:'num1'},
  {name:'Playmaking',          stat:'ast_pct',         label:'Playmaking (AST%)',   floor:null,          chip:true,  vfmt:'pct100'},
  {name:'Ball security',       stat:'tov_pct',         label:'Ball Security (TOV%)',floor:null,          chip:true,  vfmt:'pct100'},
  {name:'Rim pressure',        stat:'rim_att_pg',      label:'Rim Pressure (rim att/g)',        floor:null,          chip:true,  vfmt:'num1'},
  {name:'Rim finishing',       stat:'rim_fg_pct',      label:'Rim Finishing (rim FG%)',       floor:'rim_att',     chip:true,  vfmt:'pctdec'},
  {name:'Midrange',            stat:'midrange_fg_pct', label:'Midrange Finishing (mid FG%)',      floor:'midrange_att',chip:true,  vfmt:'pctdec'},
  {name:'3PT volume',          stat:'three_att_pg',    label:'3PT Volume (3PA/g)',          floor:null,          chip:true,  vfmt:'num1'},
  {name:'3PT efficiency',      stat:'three_fg_pct',    label:'3PT Efficiency (3P%)',       floor:'three_pa',    chip:true,  vfmt:'pctdec'},
  {name:'FT generation',       stat:'ft_rate',         label:'FT Generation (FT rate)',       floor:null,          chip:false, vfmt:'pctdec'},
  {name:'FT efficiency',       stat:'ft_pct',          label:'FT Efficiency (FT%)',        floor:'fta',         chip:false, vfmt:'pctdec'},
  {name:'Off rebounding',      stat:'or_pct',          label:'Offensive Rebounding (OR%)',       floor:null,          chip:true,  vfmt:'pct100'},
  {name:'Def rebounding',      stat:'dr_pct',          label:'Defensive Rebounding (DR%)',       floor:null,          chip:true,  vfmt:'pct100'},
  {name:'Rim protection',      stat:'blk_pct',         label:'Rim Protection (BLK%)',  floor:null,          chip:true,  vfmt:'pct100'},
  {name:'Steal rate',          stat:'stl_pct',         label:'Steal Rate (STL%)',   floor:null,          chip:true,  vfmt:'pct100'},
  {name:'Overall defense',     stat:'dbpm',            label:'Overall Defense (DBPM)',    floor:null,          chip:true,  vfmt:'signed'},
  {name:'Fouls',               stat:'fc_40',           label:'Fouls (FC/40)',       floor:null,          chip:false, vfmt:'num1'},
];
function pfFamVal(vfmt, v){
  if(v==null||isNaN(v)) return '—';
  if(vfmt==='pct100') return v.toFixed(1)+'%';
  if(vfmt==='pctdec') return (v*100).toFixed(1)+'%';
  if(vfmt==='num1')   return v.toFixed(1);
  if(vfmt==='signed') return (v>=0?'+':'')+v.toFixed(1);
  return String(v);
}
const PF_TREND_MIN_MOVE=0.10;   // >=10 percentile points to count as a move
const PF_TREND_FLOOR=40;        // efficiency families need >=40 attempts in current season
const PF_ZONE_SHARE=0.20;       // shooting zones (rim/mid/3PT) must also be >=20% of the player's FG attempts
const PF_STILL_STRONG=0.75;     // declines ending >=75th pct → "still strong", sorted last
const PF_STILL_WEAK=0.25;       // improvements ending <=25th pct → "still below average", sorted last
const PF_TREND_CAP=5;

function pfTierShort(t){ return t ? String(t).replace(/\s*\(.*\)$/,'').trim() : '—'; }
function pfUsageTierLabel(t){ const s=pfTierShort(t); return /usage/i.test(s) ? s : s+' Usage'; }
function pfOrd(n){ if(n==null||isNaN(n)) return n;
  const v=n%100,d=n%10; return n+((v>=11&&v<=13)?'th':(d===1?'st':d===2?'nd':d===3?'rd':'th')); }
function pfLevelWord(pm){ return /power/i.test(pm||'') ? 'power' : 'mid-major'; }

function pfMinUsgCtx(cur, prior){
  const mpct=cur.minutes_per_game_pct, upct=cur.usage_pct_pct;
  const m={tier:pfTierShort(cur.mpg_tier), val:cur.minutes_per_game!=null?Math.round(cur.minutes_per_game):null, changed:false,
           pct: mpct!=null?Math.round(mpct*100):null};
  const u={tier:pfTierShort(cur.usage_tier), val:cur.usage_pct!=null?Math.round(cur.usage_pct):null, changed:false,
           pct: upct!=null?Math.round(upct*100):null};
  if(prior && cur.minutes_per_game!=null && prior.minutes_per_game!=null){
    const d=cur.minutes_per_game-prior.minutes_per_game;
    m.absDelta=Math.abs(d); m.from=Math.round(prior.minutes_per_game); m.up=d>0;
    m.fromPct = prior.minutes_per_game_pct!=null?Math.round(prior.minutes_per_game_pct*100):null;
    if(m.absDelta>=5) m.changed=true;                     // header clause fires only at >=5
  }
  if(prior && cur.usage_pct!=null && prior.usage_pct!=null){
    const d=cur.usage_pct-prior.usage_pct;
    u.absDelta=Math.abs(d); u.from=Math.round(prior.usage_pct); u.up=d>0;
    u.fromPct = prior.usage_pct_pct!=null?Math.round(prior.usage_pct_pct*100):null;
    if(u.absDelta>=4) u.changed=true;                     // header clause fires only at >=4
  }
  return {minutes:m, usage:u};
}
function pfTransferCtx(cur, prior){
  if(!prior || cur.team===prior.team) return null;
  return {from:prior.team, to:cur.team,
          fromLevel:prior.power_mid, toLevel:cur.power_mid,
          fromConf:prior.conference, toConf:cur.conference};
}
function pfTransferLine(tr){   // header sentence form
  if(tr.fromLevel!==tr.toLevel){
    if(/power/i.test(tr.toLevel||''))   return `Transferred from Mid-Major to ${tr.toConf}: ${tr.from} → ${tr.to}`;
    return `Transferred from ${tr.fromConf} to Mid-Major: ${tr.from} → ${tr.to}`;
  }
  return `Transferred: ${tr.from} → ${tr.to}`;
}
function pfTransferCtxLines(tr){   // context grid: [levels line, schools line]
  let l1;
  if(tr.fromLevel!==tr.toLevel){
    l1 = /power/i.test(tr.toLevel||'') ? `Mid-Major → ${tr.toConf}` : `${tr.fromConf} → Mid-Major`;
  } else l1 = tr.toConf || (tr.from+' → '+tr.to);
  return [l1, `${tr.from} → ${tr.to}`];
}
function pfPositionCtx(cur, prior){
  if(!prior) return null;
  const posChanged=cur.position!==prior.position, roleChanged=cur.role!==prior.role;
  if(!posChanged && !roleChanged) return null;
  return {posChanged, roleChanged, fromPos:prior.position, toPos:cur.position, fromRole:prior.role, toRole:cur.role};
}

function pfComputeTrending(seasonsDesc){
  const cur=seasonsDesc[0], prior=seasonsDesc[1];
  const c=pfMinUsgCtx(cur, prior);
  const out={singleSeason:!prior, improving:[], declining:[],
             curYear: cur.year, priorYear: prior?prior.year:null,
             context:{minutes:c.minutes, usage:c.usage,
                      transfer: prior?pfTransferCtx(cur,prior):null,
                      position: prior?pfPositionCtx(cur,prior):null,
                      curPosition: cur.position, curRole: cur.role}};
  if(!prior) return out;

  const movers=[];
  PF_FAMILIES.forEach(f=>{
    const a=prior[f.stat+'_pct'], b=cur[f.stat+'_pct'];
    if(a==null||b==null||isNaN(a)||isNaN(b)) return;        // both seasons must be percentile-eligible
    const delta=b-a;
    if(Math.abs(delta)<PF_TREND_MIN_MOVE) return;           // >=10 percentile points
    if(f.floor){
      const att=cur[f.floor];
      if(att==null||att<PF_TREND_FLOOR) return;                       // volume floor (sample reliability)
      if(f.floor==='rim_att'||f.floor==='midrange_att'||f.floor==='three_pa'){
        const totalFGA=(cur.rim_att||0)+(cur.midrange_att||0)+(cur.three_pa||0);
        if(totalFGA>0 && att/totalFGA < PF_ZONE_SHARE) return;        // zone must be a real part of his shot diet
      }
    }
    movers.push({family:f.name, label:f.label, chip:f.chip,
      start:Math.round(a*100), end:Math.round(b*100), delta:Math.round(delta*100),
      startVal:pfFamVal(f.vfmt, prior[f.stat]), endVal:pfFamVal(f.vfmt, cur[f.stat]),
      improving:delta>0,
      stillStrong:(delta<0 && b>=PF_STILL_STRONG),
      stillWeak:(delta>0 && b<=PF_STILL_WEAK)});
  });

  out.improving = movers.filter(m=>m.improving).sort((x,y)=>{
    if(x.stillWeak!==y.stillWeak) return x.stillWeak?1:-1;         // still-below-average sorts last
    return y.delta-x.delta;
  }).slice(0,PF_TREND_CAP);
  out.declining = movers.filter(m=>!m.improving).sort((x,y)=>{
    if(x.stillStrong!==y.stillStrong) return x.stillStrong?1:-1;   // still-strong sorts last
    return Math.abs(y.delta)-Math.abs(x.delta);
  }).slice(0,PF_TREND_CAP);
  return out;
}

// ---- render: compact header (fills the space beside the identity card) ----
function pfMinUsgText(m,u){
  const mSeg = m.tier + (m.val!=null?` (${m.val} minutes per game${m.changed?`, ${m.up?'up':'down'} from ${m.from}`:''})`:'');
  const uSeg = pfUsageTierLabel(u.tier) + (u.val!=null?` (${u.val}%${u.changed?`, ${u.up?'up':'down'} from ${u.from}%`:''})`:'');
  return `${mSeg} · ${uSeg}`;
}
function pfTopContextFlag(ctx){
  if(ctx.transfer) return pfTransferLine(ctx.transfer);
  if(ctx.position){ const p=ctx.position; return p.posChanged?`Position: ${p.fromPos} → ${p.toPos}`:`Role: ${p.fromRole} → ${p.toRole}`; }
  return null;
}
function pfTrendingHeaderHTML(t){
  let h=`<div class="pf-th-line">${pfMinUsgText(t.context.minutes, t.context.usage)}</div>`;
  if(t.singleSeason){ return h+`<div class="pf-th-note">First D1 season — no year-over-year comparison yet</div>`; }
  const tc=pfTopContextFlag(t.context);
  if(tc) h+=`<div class="pf-th-flag">${tc}</div>`;
  const chips=[...t.improving,...t.declining].filter(m=>m.chip)
    .sort((x,y)=>{                                                 // SELECT the 5 most significant movers
      const xe=x.stillStrong||x.stillWeak, ye=y.stillStrong||y.stillWeak;
      if(xe!==ye) return xe?1:-1;
      return Math.abs(y.delta)-Math.abs(x.delta);
    }).slice(0,5)
    .sort((x,y)=>{                                                 // DISPLAY grouped: all green, then all red
      if(x.improving!==y.improving) return x.improving?-1:1;
      const xe=x.stillStrong||x.stillWeak, ye=y.stillStrong||y.stillWeak;
      if(xe!==ye) return xe?1:-1;                                  // solid before muted within each color
      return Math.abs(y.delta)-Math.abs(x.delta);
    });
  if(chips.length) h+='<div class="pf-th-chips">'+chips.map(m=>{
    const muted=m.stillStrong||m.stillWeak;
    const cls=m.improving?(muted?'pf-up-bg pf-muted':'pf-up-bg'):(muted?'pf-down-bg pf-muted':'pf-down-bg');
    return `<span class="pf-chip ${cls}">${m.improving?'↑':'↓'} ${m.label.replace(/\s*\(.*\)$/,'')}</span>`;
  }).join('')+'</div>';
  return h;
}

// ---- render: Trends tab (Player Context + two-column improving/declining) ----
function pfTrendRow(m){
  const tag = m.stillStrong?'<span class="pf-tag pf-tag-strong">still strong</span>'
            : m.stillWeak ?'<span class="pf-tag pf-tag-weak">still below avg</span>':'';
  return `<div class="pf-trend-row">
    <div class="pf-trend-lbl">${m.label}${tag}</div>
    <div class="pf-trend-vals"><span class="pf-trend-raw">${m.startVal} → ${m.endVal}</span>`+
    `<span class="pf-trend-pct">${pfOrd(m.start)} → ${pfOrd(m.end)} percentile <span class="${m.improving?'pf-up':'pf-down'}">(${m.improving?'↑':'↓'}${Math.abs(m.delta)})</span></span></div>
  </div>`;
}
function pfCtxItem(key, line1, line2){
  return `<div class="pf-ctx-item"><div class="pf-ctx-key">${key}</div>`+
    `<div class="pf-ctx-l1">${line1}</div>`+(line2?`<div class="pf-ctx-l2">${line2}</div>`:'')+`</div>`;
}
// minutes/usage: three-tier language by raw magnitude; percentile detail on line 2
function pfCtxStatLines(unit, o, bigGate, midGate){
  if(o.val==null) return ['—',''];
  const l2 = (o.absDelta!=null && o.fromPct!=null && o.pct!=null)
      ? `${pfOrd(o.fromPct)} to ${pfOrd(o.pct)} percentile`
      : (o.pct!=null?`${pfOrd(o.pct)} percentile`:'');
  const d=o.absDelta;
  let l1;
  if(d==null)            l1=`${o.val}${unit}`;
  else if(d>=bigGate)    l1=`${o.up?'Increased':'Decreased'} ${o.from}${unit} to ${o.val}${unit}`;
  else if(d>=midGate)    l1=`Slight ${o.up?'increase':'decrease'}: ${o.from}${unit} to ${o.val}${unit}`;
  else                   l1=`Similar (${o.from}${unit} to ${o.val}${unit})`;
  return [l1, l2];
}
function pfTrendsTabHTML(t){
  if(t.singleSeason) return '';
  const items=[];
  const [ml1,ml2]=pfCtxStatLines('', t.context.minutes, 5, 3);
  const [ul1,ul2]=pfCtxStatLines('%', t.context.usage, 4, 2);
  items.push(pfCtxItem('Minutes (MPG)', ml1, ml2));
  items.push(pfCtxItem('Usage (USG%)', ul1, ul2));
  // Position / Role — always shown; arrow if changed, else current state
  const p=t.context.position||{};
  const posL = p.posChanged ? `Position: ${p.fromPos} → ${p.toPos}` : `Position: ${t.context.curPosition??'—'}`;
  const roleL= p.roleChanged? `Role: ${p.fromRole} → ${p.toRole}`  : `Role: ${t.context.curRole??'—'}`;
  items.push(pfCtxItem('Position / Role', posL, roleL));
  // Transfer — only if transferred
  if(t.context.transfer){ const [tl1,tl2]=pfTransferCtxLines(t.context.transfer); items.push(pfCtxItem('Transfer', tl1, tl2)); }

  let h='<div class="pf-trends">';
  const yrs = (t.priorYear && t.curYear && typeof yLabel==='function')
      ? ` · ${yLabel(t.priorYear)} → ${yLabel(t.curYear)}` : '';
  h+='<div class="pf-ctx-box"><div class="pf-ctx-h">Player Context'+yrs+'</div><div class="pf-ctx-grid">'+items.join('')+'</div></div>';
  h+='<div class="pf-trend-cols">';
  h+='<div class="pf-trend-col"><div class="pf-trend-h pf-up">Improving</div>'+
     (t.improving.length?t.improving.map(pfTrendRow).join(''):'<div class="pf-trend-empty">No notable improvements</div>')+'</div>';
  h+='<div class="pf-trend-col"><div class="pf-trend-h pf-down">Declining</div>'+
     (t.declining.length?t.declining.map(pfTrendRow).join(''):'<div class="pf-trend-empty">No notable declines</div>')+'</div>';
  h+='</div>';
  h+='<div class="pf-trend-foot">Trends compare the two most recent seasons using national percentiles, held constant across seasons for a fair comparison.</div>';
  return h+'</div>';
}

// ── ONE-PAGER PNG EXPORT ──────────────────────────────────────────────────────
// Builds a purpose-built portrait layout (header + trends + shot charts + supplement
// + core/advanced tables) in an off-screen node and rasterizes it via html2canvas.
// Dual percentiles (national + position) on the most-recent season row; national on prior.

const OP_CORE=[['minutes_per_game','num1','MPG'],['usage_pct','pct100','USG%'],['bpm','signed','BPM'],
               ['ppg','num1','PTS'],['rebpg','num1','REB'],['astpg','num1','AST']];
const OP_ADV=[['obpm','signed','OBPM'],['dbpm','signed','DBPM'],['or_pct','pct100','OR%'],['dr_pct','pct100','DR%'],
              ['ast_pct','pct100','AST%'],['tov_pct','pct100','TOV%'],['blk_pct','pct100','BLK%'],['stl_pct','pct100','STL%'],['fc_40','num1','FC/40']];

function pfSlug(n){ return (n||'player').replace(/[^A-Za-z0-9]+/g,'_').replace(/^_+|_+$/g,''); }
function pfPctPair(season, statKey, showPos){
  const n=season[statKey+'_pct'], p=season[statKey+'_pos_pct'];
  if(n==null||isNaN(n)) return '';
  const nP=Math.round(n*100);
  if(showPos && p!=null && !isNaN(p)) return `${nP}N / ${Math.round(p*100)}P`;
  return `${nP}N`;
}
function pfOpCell(season, statKey, vfmt, showPos){
  const val=pfFamVal(vfmt, season[statKey]);
  const pct=pfPctPair(season, statKey, showPos);
  return `<td><div class="op-v">${val}</div>${pct?`<div class="op-p">${pct}</div>`:''}</td>`;
}
function pfOpTable(seasonsDesc, cols, showTeam, showGames){
  const curPos = seasonsDesc[0] && seasonsDesc[0].position;
  let h='<table class="op-table"><thead><tr><th class="op-lft">Season</th>'+(showTeam?'<th class="op-lft">Team</th>':'')+(showGames?'<th>G</th>':'')+
    cols.map(c=>`<th>${c[2]}</th>`).join('')+'</tr></thead><tbody>';
  seasonsDesc.forEach(s=>{
    const showPos = (s.position===curPos);   // position percentile only where bucket matches current
    h+='<tr>'+`<td class="op-lft op-season">${yLabel(s.year)}</td>`+
       (showTeam?`<td class="op-lft">${s.team||''}</td>`:'')+
       (showGames?`<td><div class="op-v">${s.games!=null?s.games:''}</div></td>`:'')+
       cols.map(c=>pfOpCell(s,c[0],c[1],showPos)).join('')+'</tr>';
  });
  return h+'</tbody></table>';
}
function pfOpSupplement(s){
  const cell=(lbl,val,pctHtml)=>`<div class="op-sup-item"><div class="op-sup-k">${lbl}</div><div class="op-sup-v">${val}</div>${pctHtml?`<div class="op-sup-p">${pctHtml}</div>`:''}</div>`;
  const ftpg=(s.ft_made_pg!=null&&s.ft_att_pg!=null)?`${s.ft_made_pg.toFixed(1)}/${s.ft_att_pg.toFixed(1)}`:'—';
  return '<div class="op-sup">'+cell('TS%',pfFamVal('pct100',s.ts),pfPctPair(s,'ts',true))+
    cell('FT rate',pfFamVal('pctdec',s.ft_rate),pfPctPair(s,'ft_rate',true))+
    cell('FT/g',ftpg,'')+cell('FT%',pfFamVal('pctdec',s.ft_pct),pfPctPair(s,'ft_pct',true))+'</div>';
}
function pfOnePagerHeader(){
  const s=pfLatest(cPlayer.seasons);
  const d1=(s.years_in_d1!=null&&!isNaN(s.years_in_d1))?parseInt(s.years_in_d1)+' yr'+(parseInt(s.years_in_d1)===1?'':'s')+' D1':null;
  const bio=[s.position,s.role,pfHeightStr(s.height_in),s.class,
             (s.age!=null&&!isNaN(s.age)?parseFloat(s.age).toFixed(1)+' yrs':null), d1].filter(Boolean).join(' · ');
  const team=[s.team,s.conference?`(${s.conference})`:null].filter(Boolean).join(' ');
  const seasonsDesc=cPlayer.seasons.slice().sort((a,b)=>(b.year||0)-(a.year||0));
  const trend=pfComputeTrending(seasonsDesc);
  const tier=pfMinUsgText(trend.context.minutes,trend.context.usage);
  const flag=pfTopContextFlag(trend.context);
  return `<div class="op-header">
    <div class="op-name">${cPlayer.name||'—'}</div>
    <div class="op-bio">${bio}</div>
    <div class="op-team">${team}</div>
    <div class="op-tier">${tier}</div>
    ${flag?`<div class="op-flag">${flag}</div>`:''}
  </div>`;
}
function pfOnePagerCharts(s, sfx){
  const base={showPct:true, showLabels:true, stackPct:true, zoneFont:18};
  const rate=buildCourtSVG({...base, zones:pfShotZones(s,sfx,'rate'), metricsShown:'rate'});
  const fg  =buildCourtSVG({...base, zones:pfShotZones(s,sfx,'fg'),   metricsShown:'fg'});
  return `<div class="op-court"><div class="op-court-lbl">Shot Rate</div>${rate}</div>`+
         `<div class="op-court"><div class="op-court-lbl">FG% &amp; Volume</div>${fg}</div>`;
}
function pfOnePagerTrends(trend){
  if(trend.singleSeason) return '<div class="op-sec-h">Trends</div><div class="op-tr-empty">First D1 season — no year-over-year comparison yet</div>';
  const row=m=>{
    const tag = m.stillStrong ? ' <span class="op-tag">still strong</span>'
              : m.stillWeak   ? ' <span class="op-tag">still below avg</span>' : '';
    return `<div class="op-tr-row"><div class="op-tr-lbl">${m.label}</div>`+
    `<div class="op-tr-mv">${m.startVal} → ${m.endVal} <span class="op-tr-sep">·</span> <span class="op-tr-pctl">Pct: ${m.start} → ${m.end}</span> <span class="${m.improving?'pf-up':'pf-down'}">(${m.improving?'↑':'↓'}${Math.abs(m.delta)})</span>${tag}</div></div>`;
  };
  const col=(title,arr,cls)=>`<div class="op-tr-col"><div class="op-tr-h ${cls}">${title}</div>${arr.length?arr.map(row).join(''):'<div class="op-tr-empty">None</div>'}</div>`;
  return `<div class="op-sec-h">Trends · ${yLabel(trend.priorYear)} → ${yLabel(trend.curYear)} · National Percentiles</div>
    <div class="op-tr-cols">${col('Improving',trend.improving,'pf-up')}${col('Declining',trend.declining,'pf-down')}</div>`;
}
function pfOnePagerHTML(){
  const seasonsDesc=cPlayer.seasons.slice().sort((a,b)=>(b.year||0)-(a.year||0));
  const cur=seasonsDesc[0];
  const trend=pfComputeTrending(seasonsDesc);
  const posChanged=seasonsDesc.some(s=>s.position!==cur.position);
  const posNote=posChanged?' <span class="op-note">· position percentiles shown for current-position seasons only</span>':'';
  return `<div class="op-page">
    ${pfOnePagerHeader()}
    ${pfOnePagerTrends(trend)}
    <div class="op-sec-h">Shot Profile · ${yLabel(cur.year)} · National Percentiles</div>
    <div class="op-shot-row">
      <div class="op-charts">${pfOnePagerCharts(cur,'_pct')}</div>
      ${pfOpSupplement(cur)}
    </div>
    <div class="op-sec-h">Core Production (per game)${posNote}</div>
    ${pfOpTable(seasonsDesc, OP_CORE, true, true)}
    <div class="op-sec-h">Advanced (rates)</div>
    ${pfOpTable(seasonsDesc, OP_ADV, false, false)}
    <div class="op-footer">
      <div class="op-legend">N = national percentile &nbsp;·&nbsp; P = position percentile &nbsp;·&nbsp; both vs. all D1</div>
      <div class="op-brand">bhstern.github.io/NCAA-Basketball-Team-Profiles-D1 &nbsp;·&nbsp; Benj Stern</div>
    </div>
  </div>`;
}
function pfLoadHtml2Canvas(){
  return new Promise((res,rej)=>{
    if(window.html2canvas) return res(window.html2canvas);
    const sc=document.createElement('script');
    sc.src='https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
    sc.onload=()=>res(window.html2canvas); sc.onerror=()=>rej(new Error('could not load html2canvas'));
    document.head.appendChild(sc);
  });
}
async function pfExportOnePager(){
  if(!cPlayer) return;
  const btn=document.getElementById('pf-op-btn'); const label=btn?btn.textContent:'';
  if(btn){ btn.disabled=true; btn.textContent='Generating…'; }
  try{
    const h2c=await pfLoadHtml2Canvas();
    const host=document.createElement('div');
    host.style.cssText='position:fixed;left:-99999px;top:0;z-index:-1;';
    host.innerHTML=pfOnePagerHTML();
    document.body.appendChild(host);
    const page=host.querySelector('.op-page');
    const canvas=await h2c(page,{scale:2, backgroundColor:'#0d1526', logging:false, useCORS:true, windowWidth:page.scrollWidth, windowHeight:page.scrollHeight});
    const a=document.createElement('a');
    const yr = (function(){ const ss=cPlayer.seasons.slice().sort((x,y)=>(y.year||0)-(x.year||0))[0]; return ss&&ss.year?yLabel(ss.year):''; })();
    a.download=(yr?yr+'_':'')+pfSlug(cPlayer.name)+'_Profile.png';
    a.href=canvas.toDataURL('image/png'); a.click();
    document.body.removeChild(host);
  }catch(e){ alert('One-pager export failed: '+(e&&e.message?e.message:e)); }
  finally{ if(btn){ btn.disabled=false; btn.textContent=label||'Export one-pager (PNG)'; } }
}
