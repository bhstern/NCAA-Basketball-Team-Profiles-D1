// ── PLAYER PROFILE ────────────────────────────────────────────────────────────
// Slice 1: identity card + career table (seasons as rows, most recent first).
// Reuses the explorer's formatters + cell renderer (explorerStackedCell) and its
// tooltip map (EXPLORER_TIPS/explorerTip) so cells + headers match the Player Explorer.
// Career table uses NATIONAL percentile (stat + '_pct') — fixed reference pool across
// seasons, so year-over-year moves aren't distorted by position changes.

let cPlayer = null;              // loaded career file {player_id, name, seasons:[...]}
let cPlayerStatTab = 'overview'; // active career-table stat group

function pfHeightStr(inches){
  const i = parseInt(inches);
  if (isNaN(i)) return null;
  return Math.floor(i/12) + "'" + (i%12) + '"';
}

function pfLatest(seasons){
  return seasons.slice().sort((a,b)=>(b.year||0)-(a.year||0))[0];
}

// ── entry point: roster/explorer row click, or a ?pid= deep link ──
async function openPlayerProfile(playerId){
  if(!playerId) return;
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
  renderPlayerCareer();
}

// ── identity card (from the most recent season) ──
function pfIdentityCard(){
  const s = pfLatest(cPlayer.seasons);
  const bits1 = [s.position, s.role, s.class, pfHeightStr(s.height_in),
                 (s.age!=null && !isNaN(s.age) ? parseFloat(s.age).toFixed(1)+' yrs' : null)].filter(Boolean);
  const teamLine = [s.team, s.conference?`(${s.conference})`:null].filter(Boolean).join(' ');
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
    {label:'Team',   w:120, get:s=> s.team ?? '—'},
    {label:'Yr',     w:40,  get:s=> s.class ?? '—'},
    {label:'Pos',    w:52,  get:s=> s.position ?? '—'},
    {label:'Role',   w:80,  get:s=> s.role ?? '—'},
    {label:'G',      w:38,  get:s=> s.games ?? '—'},
    {label:'MPG',    w:50,  get:s=> (s.minutes_per_game!=null? fmtNumE(s.minutes_per_game) : '—')},
  ];

  const stickyStyle=(left,w,z,bg)=>`position:sticky;left:${left}px;z-index:${z};width:${w}px;min-width:${w}px;max-width:${w}px;background:${bg};`;

  let html='<div class="pf-table-scroll"><table class="roster-table pf-table"><thead><tr>';
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
                     ? null : season[s.key+'_pct'];
      html+=`<td class="roster-stat-td">${explorerStackedCell(rawDisplay, pctVal)}</td>`;
    });
    html+='<td class="pf-spacer"></td>';
    html+='</tr>';
  });
  html+='</tbody></table></div>';
  wrap.innerHTML=html;
}
