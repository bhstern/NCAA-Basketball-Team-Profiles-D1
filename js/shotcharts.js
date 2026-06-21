/* ============================================================================
   shotcharts.js — the Shot Charts authoring tab.

   Integration layer only. The court geometry, color ramps, and PNG export live
   in shotcourt.js (lifted verbatim). This file wires the live per-year JSON to
   that engine and unifies the three subjects (Team / Player / Group) and two
   modes (Builder / Compare) behind one tab.

   Data sources (already loaded elsewhere on the site):
     Team        -> loadYear(year)          -> data/cbb_{year}.json   (YCACHE)
     Player/Group-> loadExplorerYear(year)   -> player_data/layer2_explorer/players_{year}.json (EXPLORER_CACHE)

   Percentile rules (spec §8):
     Team        -> precomputed team percentiles, 3 bases (_pct/_conf_pct/_sub_pct)
     Single player-> precomputed player percentiles, 6 bases (default _pos_pct)
     Group (2+)  -> runtime pooling + ranking vs the season's qualified players
   ========================================================================== */

const SC_YEARS = [2026,2025,2024,2023,2022,2021,2020,2019,2018,2017,2016];

const SC = {
  mounted:false,
  subject:'team',     // 'team' | 'player' | 'group'
  mode:'builder',     // 'builder' | 'compare'
  intent:'pop',       // 'pop' | 'diff'   (diff only in compare)
  diffMetric:'fg',    // 'fg' | 'rate'
  basis:'_pct',       // current shared basis key/suffix
  showPct:false,
  showLabels:true,
  _seededTeam:null,   // team chart A was last auto-seeded to (so context changes can follow it)
  charts:{
    A:{year:2026, side:'o', team:null, players:[], title:'', subtitle:'', titleEdited:false},
    B:{year:2026, side:'o', team:null, players:[], title:'', subtitle:'', titleEdited:false},
  },
};

const SC_POP_CACHE = {};   // year -> POP distributions (group mode)

/* ---------- team field maps ---------- */
const SC_TEAM_F = {
  rim:  ['rim_rate_total','rim_fg'],
  mid:  ['long_twos_rate_total','long_twos_fg'],
  three:['threes_rate_total','threes_fg'],
};
/* ---------- player zone keys ---------- */
const SC_PZ = { rim:'rim', mid:'midrange', three:'three' };
const SC_MA = { rim:'rim_made_att_str', mid:'midrange_made_att_str', three:'three_made_att_str' };
const SC_MIN_TOT_ATT = 30, SC_MIN_ZONE_ATT = 10;

/* ============================== DATA HELPERS ============================== */

function scActiveCharts(){ return SC.mode==='compare' ? ['A','B'] : ['A']; }

async function scEnsureData(year, subject){
  if(subject==='team') return await loadYear(year);
  return await loadExplorerYear(year);   // player + group
}

function scParseMA(s){ if(!s||String(s).indexOf('/')<0) return [0,0];
  const [m,a]=String(s).split('/'); return [parseInt(m,10)||0, parseInt(a,10)||0]; }

function scPoolGroup(players){
  const made={rim:0,mid:0,three:0}, att={rim:0,mid:0,three:0};
  players.forEach(p=>{ for(const z in SC_MA){ const [m,a]=scParseMA(p[SC_MA[z]]); made[z]+=m; att[z]+=a; } });
  const tot=att.rim+att.mid+att.three, out={};
  for(const z in SC_MA) out[z]={ rate: tot?att[z]/tot:0, fg: att[z]?made[z]/att[z]:null, made:made[z], att:att[z] };
  out._tot=tot;
  return out;
}

function scIsEligible(p){
  const v=p.percentile_eligible;
  if(v===true||v==='True'||v==='true'||v===1) return true;
  if(v===false||v==='False'||v==='false'||v===0) return false;
  return null;   // unknown -> caller falls back to attempt threshold
}

function scBuildPop(players){
  const blank=()=>({rim:{fg:[],rate:[]},mid:{fg:[],rate:[]},three:{fg:[],rate:[]}});
  const POP={all:blank(),Guard:blank(),Wing:blank(),Big:blank()};
  players.forEach(p=>{
    const pr=scPoolGroup([p]);
    const elig=scIsEligible(p);
    if(elig===false) return;
    if(elig===null && pr._tot < SC_MIN_TOT_ATT) return;   // fallback gate
    const pos=p.position;
    for(const z in SC_MA){
      const dst=[POP.all[z]]; if(POP[pos]) dst.push(POP[pos][z]);
      dst.forEach(D=>{ D.rate.push(pr[z].rate); if(pr[z].att>=SC_MIN_ZONE_ATT && pr[z].fg!=null) D.fg.push(pr[z].fg); });
    }
  });
  for(const k in POP) for(const z in SC_MA){ POP[k][z].fg.sort((a,b)=>a-b); POP[k][z].rate.sort((a,b)=>a-b); }
  return POP;
}

async function scGetPop(year){
  if(SC_POP_CACHE[year]) return SC_POP_CACHE[year];
  const players=await loadExplorerYear(year);
  const POP=scBuildPop(players);
  SC_POP_CACHE[year]=POP;
  return POP;
}

function scPctileIn(val,arr){ if(val==null||!arr.length) return null;
  let lo=0,hi=arr.length; while(lo<hi){const m=(lo+hi)>>1; if(arr[m]<=val)lo=m+1; else hi=m;} return lo/arr.length; }

/* ---------- value profiles (for diff mode + display) ---------- */
function scTeamProfile(row, side){
  const pre=side==='o'?'off_':'def_', out={};
  for(const z in SC_TEAM_F){ out[z]={ rate: row[pre+SC_TEAM_F[z][0]], fg: row[pre+SC_TEAM_F[z][1]] }; }
  return out;
}
function scPlayerProfile(row){
  const out={};
  for(const z in SC_PZ){ out[z]={ rate: row[`${SC_PZ[z]}_rate`], fg: row[`${SC_PZ[z]}_fg_pct`] }; }
  return out;
}

/* ============================== ZONE BUILDERS ============================== */

function scZonesTeam(row, side, intent, basisSuffix, otherProf){
  const pre=side==='o'?'off_':'def_', out={};
  for(const z of ['rim','mid','three']){
    const rf=pre+SC_TEAM_F[z][0], ff=pre+SC_TEAM_F[z][1];
    const r=row[rf], fg=row[ff], zd={ r, fg, rp:null, fgp:null };
    if(intent==='pop'){
      zd.rp=row[rf+basisSuffix]; zd.fgp=row[ff+basisSuffix];
      zd.color=scPctColor(zd.fgp);
    } else {
      const od=otherProf?otherProf[z]:null;
      zd.dRate=(od&&r!=null&&od.rate!=null)?(r-od.rate)*100:null;
      zd.dFg  =(od&&fg!=null&&od.fg!=null)?(fg-od.fg)*100:null;
      zd.color=scDiffColor(SC.diffMetric==='fg'?zd.dFg:zd.dRate);
    }
    out[z]=zd;
  }
  return out;
}

function scZonesPlayer(row, intent, basisSuffix, otherProf){
  const out={};
  for(const z of ['rim','mid','three']){
    const k=SC_PZ[z], r=row[`${k}_rate`], fg=row[`${k}_fg_pct`], zd={ r, fg, rp:null, fgp:null };
    if(intent==='pop'){
      zd.rp=row[`${k}_rate${basisSuffix}`]; zd.fgp=row[`${k}_fg_pct${basisSuffix}`];
      zd.color=scPctColor(zd.fgp);
    } else {
      const od=otherProf?otherProf[z]:null;
      zd.dRate=(od&&r!=null&&od.rate!=null)?(r-od.rate)*100:null;
      zd.dFg  =(od&&fg!=null&&od.fg!=null)?(fg-od.fg)*100:null;
      zd.color=scDiffColor(SC.diffMetric==='fg'?zd.dFg:zd.dRate);
    }
    out[z]=zd;
  }
  return out;
}

function scZonesGroup(prof, POP, basisKey, intent, otherProf){
  const out={};
  for(const z of ['rim','mid','three']){
    const zd={ r:prof[z].rate, fg:prof[z].fg, rp:null, fgp:null };
    if(intent==='pop'){
      const base=POP[basisKey]||POP.all;
      zd.rp=scPctileIn(prof[z].rate, base[z].rate);
      zd.fgp=scPctileIn(prof[z].fg,   base[z].fg);
      zd.color=scPctColor(zd.fgp);
    } else {
      const od=otherProf?otherProf[z]:null;
      zd.dRate=(od&&prof[z].rate!=null&&od.rate!=null)?(prof[z].rate-od.rate)*100:null;
      zd.dFg  =(od&&prof[z].fg!=null&&od.fg!=null)?(prof[z].fg-od.fg)*100:null;
      zd.color=scDiffColor(SC.diffMetric==='fg'?zd.dFg:zd.dRate);
    }
    out[z]=zd;
  }
  return out;
}

const SC_EMPTY_ZONES = ()=>({
  rim:{r:null,fg:null,rp:null,fgp:null,color:'#1e2d42'},
  mid:{r:null,fg:null,rp:null,fgp:null,color:'#1e2d42'},
  three:{r:null,fg:null,rp:null,fgp:null,color:'#1e2d42'},
});

/* ============================== BASIS OPTIONS ============================== */

function scBasisOptions(){
  if(SC.subject==='team'){
    return [['_pct','vs all D1'],['_conf_pct','vs conference'],['_sub_pct','vs power/mid tier']];
  }
  if(SC.subject==='player'){
    return [
      ['_pos_pct','vs position (all D1)'],
      ['_pct','vs all D1'],
      ['_pos_conf_pct','vs position (conference)'],
      ['_conf_pct','vs conference'],
      ['_pos_sub_pct','vs position (power/mid)'],
      ['_sub_pct','vs power/mid tier'],
    ];
  }
  // group: union of selected players across active charts; offer shared position only if uniform
  const all=scActiveCharts().flatMap(c=>SC.charts[c].players);
  const opts=[['all','vs all D1 players']];
  const positions=[...new Set(all.map(p=>p.position))];
  if(all.length && positions.length===1) opts.push([positions[0], `vs all D1 ${positions[0].toLowerCase()}s`]);
  return opts;
}
function scDefaultBasis(){
  if(SC.subject==='player') return '_pos_pct';
  if(SC.subject==='group')  return 'all';
  return '_pct';
}
/* current basis as human text (e.g. "vs all D1 guards"); DOM-free so the SVG and legend agree */
function scBasisText(){
  const o=scBasisOptions().find(([v])=>v===SC.basis);
  return o ? o[1] : '';
}

/* population phrase for the on-chart footer of chart c.
   Reads cleaner than the dropdown menu wording on purpose: for a player it names
   the actual position ("all D1 guards") instead of the menu's "position (all D1)". */
function scFooterText(c){
  if(SC.subject==='team'){
    return ({'_pct':'all D1','_conf_pct':'conference','_sub_pct':'power/mid tier'})[SC.basis] || '';
  }
  if(SC.subject==='player'){
    const p=SC.charts[c].players[0];
    const pos=p && p.position ? p.position.toLowerCase()+'s' : 'position';
    return ({
      '_pos_pct':`all D1 ${pos}`, '_pct':'all D1',
      '_pos_conf_pct':`conference ${pos}`, '_conf_pct':'conference',
      '_pos_sub_pct':`power/mid ${pos}`, '_sub_pct':'power/mid tier',
    })[SC.basis] || '';
  }
  // group: reuse the basis label, drop the "vs " / trailing " players"
  return scBasisText().replace(/^vs /,'').replace(/ players$/,'');
}

/* auto-title for a pooled group, used when the user hasn't typed their own.
   Small groups (<=5) list the players by last name ("2025-26: Perkins, Lewis, ...")
   since a group IS its members; larger groups use a summary that includes the
   player count so it can't be misread as the full team. */
function scGroupTitle(st){
  const ps=st.players; if(!ps.length) return '';
  const yr=yLabel(st.year), n=ps.length;
  if(n<=5) return `${yr}: ${ps.map(p=>scLastName(p.name)).join(', ')}`;
  const teams=[...new Set(ps.map(p=>p.team))];
  const poss =[...new Set(ps.map(p=>p.position))];
  if(teams.length===1) return poss.length===1 ? `${teams[0]} ${yr} ${poss[0]}s (${n})` : `${teams[0]} ${yr} (${n} players)`;
  return poss.length===1 ? `${yr} ${poss[0]}s (${n})` : `${yr} Group (${n})`;
}
function scRefreshBasis(){
  const opts=scBasisOptions();
  const keys=opts.map(o=>o[0]);
  if(!keys.includes(SC.basis)) SC.basis = keys.includes(scDefaultBasis())?scDefaultBasis():keys[0];
  const sel=document.getElementById('sc-basis');
  if(sel){
    sel.innerHTML=opts.map(([v,l])=>`<option value="${v}">${l}</option>`).join('');
    sel.value=SC.basis;
  }
}

/* ============================== RENDER ============================== */

let scRenderToken=0;
async function scRender(){
  const token=++scRenderToken;
  const charts=scActiveCharts();

  // gather rows / profiles for each active chart
  const ctx={};
  for(const c of charts){
    const st=SC.charts[c];
    if(SC.subject==='team'){
      const arr=await scEnsureData(st.year,'team');
      ctx[c]={ row: st.team ? arr.find(r=>r.team_name===st.team) : null };
    } else if(SC.subject==='player'){
      const arr=await scEnsureData(st.year,'player');
      const p=st.players[0];
      ctx[c]={ row: p ? arr.find(r=>r.player_id===p.player_id) || p : null };
    } else { // group
      ctx[c]={ prof: st.players.length ? scPoolGroup(st.players) : null,
               pop: st.players.length ? await scGetPop(st.year) : null };
    }
  }
  if(token!==scRenderToken) return; // a newer render superseded this one

  // value profiles (needed for diff mode)
  const profOf={};
  for(const c of charts){
    const st=SC.charts[c];
    if(SC.subject==='team')   profOf[c]= ctx[c].row ? scTeamProfile(ctx[c].row, st.side) : null;
    else if(SC.subject==='player') profOf[c]= ctx[c].row ? scPlayerProfile(ctx[c].row) : null;
    else profOf[c]= ctx[c].prof;
  }

  const showPct = SC.intent==='pop' && SC.showPct;

  // in compare, both titles use one shared size (the smaller fit) so they match side by side
  const sharedTitleSize = SC.mode==='compare'
    ? Math.min(scTitleFontSize(scDisplayTitle('A')), scTitleFontSize(scDisplayTitle('B')))
    : null;

  for(const c of charts){
    const st=SC.charts[c];
    const other = c==='A'?'B':'A';
    const otherProf = SC.mode==='compare' ? profOf[other] : null;
    let zones;
    const hasData = (SC.subject==='group') ? !!ctx[c].prof : !!ctx[c].row;
    if(!hasData){
      zones=SC_EMPTY_ZONES();
    } else if(SC.subject==='team'){
      zones=scZonesTeam(ctx[c].row, st.side, SC.intent, SC.basis, otherProf);
    } else if(SC.subject==='player'){
      zones=scZonesPlayer(ctx[c].row, SC.intent, SC.basis, otherProf);
    } else {
      zones=scZonesGroup(ctx[c].prof, ctx[c].pop, SC.basis, SC.intent, otherProf);
    }
    const mount=document.getElementById('sc-court'+c);
    if(mount) mount.innerHTML=buildCourtSVG({
      zones, showPct: showPct && hasData, showLabels:SC.showLabels,
      title: scDisplayTitle(c), subtitle: st.subtitle.trim(), titleSize: sharedTitleSize,
      basisNote: (SC.intent==='pop' && hasData) ? 'Compared vs. '+scFooterText(c) : '',
      diffMetric: SC.intent==='diff' ? SC.diffMetric : null,
    });
  }

  scUpdateLegend();
}

function scUpdateLegend(){
  const bar=document.getElementById('sc-legbar'), lbl=document.getElementById('sc-leglbl'), sub=document.getElementById('sc-legsub');
  if(!bar) return;
  const groupMulti = SC.subject==='group' && scActiveCharts().some(c=>SC.charts[c].players.length>1);
  const poolNote = " Group zones pool every player's makes and attempts, so values are volume-weighted, not a flat average of the players' rates.";
  if(SC.intent==='pop'){
    bar.style.background='linear-gradient(90deg,#c0392b,#e67e22,#f1c40f,#82b74b,#27ae60)';
    lbl.innerHTML='<span>Poor</span><span>Avg</span><span>Elite</span>';
    let basisLabel=scBasisText()||'population';
    let s='FG% percentile, '+basisLabel+'.';
    if(SC.subject==='team') s+=' Defense is inverted: green = holds opponents below average.';
    if(groupMulti) s+=' Pooled-group percentiles read muted vs. individuals \u2014 treat as directional.'+poolNote;
    if(SC.mode==='compare') s+=' Both charts share one basis so the colors are comparable.';
    sub.textContent=s;
  } else {
    bar.style.background='linear-gradient(90deg,rgb(192,57,43),rgb(120,128,150),rgb(39,174,96))';
    lbl.innerHTML='<span>-10 pts</span><span>even</span><span>+10 pts</span>';
    let s=`Each zone colored by the raw ${SC.diffMetric==='fg'?'FG%':'rate'} difference between the two charts (fixed \u00B110-point scale). Green = this side is better in that zone. No population involved.`;
    if(groupMulti) s+=poolNote;
    sub.textContent=s;
  }
}

/* ============================== UI: per-chart controls ============================== */

function scLastName(n){
  const p=String(n).trim().split(/\s+/);
  let i=p.length-1;
  if(i>0 && /^(jr|sr|ii|iii|iv)\.?$/i.test(p[i])) i--;   // skip a trailing generational suffix
  return p[i];
}

function scFillTeams(c){
  const st=SC.charts[c];
  const arr=YCACHE[st.year]||[];
  const teams=arr.map(r=>r.team_name).sort();
  const sel=document.getElementById('sc-team'+c);
  if(!sel) return;
  sel.innerHTML=teams.map(t=>`<option ${t===st.team?'selected':''}>${SC_esc(t)}</option>`).join('');
  if(!st.team || !teams.includes(st.team)){ st.team=teams[0]||null; sel.value=st.team||''; }
}

function scRenderChips(c){
  const st=SC.charts[c], box=document.getElementById('sc-chips'+c);
  if(!box) return;
  box.innerHTML=st.players.map(r=>
    `<span class="sc-chip"><b>${SC_esc(r.name)}</b> <small>${SC_esc(r.team)}·${(r.position||'')[0]||''}</small><span data-pid="${r.player_id}">×</span></span>`
  ).join('');
  box.querySelectorAll('span[data-pid]').forEach(x=>x.onclick=()=>{
    st.players=st.players.filter(r=>String(r.player_id)!==String(x.dataset.pid));
    scRenderChips(c); scAutoTitle(c); scRefreshBasis(); scRender();
  });
}

async function scSetupSearch(c){
  const inp=document.getElementById('sc-search'+c), dd=document.getElementById('sc-dd'+c);
  if(!inp) return;
  inp.oninput=async ()=>{
    const q=inp.value.trim().toLowerCase();
    if(q.length<2){ dd.style.display='none'; return; }
    const arr=await loadExplorerYear(SC.charts[c].year);
    const ms=arr.filter(r=>r.name && r.name.toLowerCase().includes(q))
                .sort((a,b)=>(b.minutes_per_game||0)-(a.minutes_per_game||0)).slice(0,14);
    dd.innerHTML=ms.map(r=>`<div data-pid="${r.player_id}">${SC_esc(r.name)} <small>· ${SC_esc(r.team)} · ${r.position||''} · ${(r.minutes_per_game||0).toFixed?.(1)||r.minutes_per_game} mpg</small></div>`).join('')||'<div><small>no match</small></div>';
    dd.style.display='block';
    dd.querySelectorAll('div[data-pid]').forEach(d=>d.onclick=()=>{
      const r=ms.find(x=>String(x.player_id)===String(d.dataset.pid));
      if(!r) return;
      const st=SC.charts[c];
      if(SC.subject==='player') st.players=[r];                       // single -> replace
      else if(!st.players.some(x=>String(x.player_id)===String(r.player_id))) st.players.push(r); // group -> add
      inp.value=''; dd.style.display='none';
      scRenderChips(c); scAutoTitle(c); scRefreshBasis(); scRender();
    });
  };
  inp.onblur=()=>setTimeout(()=>dd.style.display='none',180);
}

/* auto title when the user hasn't typed their own; clears to '' when nothing is
   selected so the chart falls back to the "Pick a team / player" placeholder */
function scAutoTitle(c){
  const st=SC.charts[c];
  if(st.titleEdited) return;                         // user owns the title
  if(SC.subject==='team')        st.title = st.team ? st.team+' '+yLabel(st.year) : '';
  else if(SC.subject==='player') st.title = st.players.length ? `${st.players[0].name} ${yLabel(st.year)}` : '';
  else                           st.title = st.players.length ? scGroupTitle(st) : '';
  syncInput('sc-title'+c, st.title);
}
function syncInput(id,val){ const el=document.getElementById(id); if(el && document.activeElement!==el) el.value=val; }

/* title-field example reflects the chart's team ("e.g. Virginia Tech 2025-26 Guards") */
function scTitlePlaceholder(c){
  const st=SC.charts[c];
  return `e.g. ${st.team||'Villanova'} ${yLabel(st.year)} Guards`;
}
function scSyncTitlePlaceholders(){
  ['A','B'].forEach(c=>{ const el=document.getElementById('sc-title'+c); if(el) el.placeholder=scTitlePlaceholder(c); });
}

/* the title actually drawn on chart c (custom title, else a placeholder prompt) */
function scDisplayTitle(c){
  const t=SC.charts[c].title.trim();
  if(t) return t;
  return SC.subject==='team' ? 'Pick a team' : SC.subject==='player' ? 'Pick a player' : 'Add 2+ players';
}

/* ============================== MOUNT / EVENTS ============================== */

function scChartColumnHTML(c){
  return `
  <div class="sc-col">
    <div class="sc-court" id="sc-court${c}"></div>
    <div class="sc-cell sc-team-only"><span class="sc-lab">Season</span>
      <select class="sc-input" id="sc-year${c}"></select></div>

    <div class="sc-cell sc-team-only sc-subj-team"><span class="sc-lab">Team</span>
      <select class="sc-input" id="sc-team${c}"></select></div>
    <div class="sc-cell sc-team-only sc-subj-team"><span class="sc-lab">Side</span>
      <div class="sc-seg sc-full">
        <button class="sc-side${c} on" data-s="o">Offense</button>
        <button class="sc-side${c}" data-s="d">Defense</button></div></div>

    <div class="sc-cell sc-subj-players"><span class="sc-lab" id="sc-searchlab${c}">Players</span>
      <div class="sc-results">
        <input type="text" class="sc-input" id="sc-search${c}" placeholder="Search any D1 player…" autocomplete="off"/>
        <div class="sc-dd" id="sc-dd${c}"></div></div>
      <div class="sc-chips" id="sc-chips${c}"></div></div>

    <div class="sc-grid2">
      <div><span class="sc-lab">Title</span><input type="text" class="sc-input" id="sc-title${c}" placeholder="e.g. Villanova 2025-26 Guards"/></div>
      <div><span class="sc-lab">Subtitle</span><input type="text" class="sc-input" id="sc-sub${c}" placeholder="subtitle"/></div>
    </div>
    <div class="sc-btnrow">
      <button class="sc-btn ghost sc-subj-players" id="sc-namefill${c}">Subtitle = names</button>
      <button class="sc-btn ghost sc-subj-team" id="sc-fill${c}">Fill title</button>
      <button class="sc-btn ghost sc-subj-players" id="sc-clear${c}">Clear</button>
    </div>
  </div>`;
}

function scMount(){
  const host=document.getElementById('tab-shotcharts');
  if(!host) return;
  host.innerHTML=`
  <div class="sc-wrap">
    <h1 class="sc-h1">Shot Charts</h1>
    <p class="sc-lead">Build half-court shot-zone charts for a team, a player, or a group — color by percentile vs a population, or directly against another chart. Export as PNG.</p>

    <div class="sc-topbar">
      <div class="sc-fld"><label>Subject</label>
        <div class="sc-seg" id="sc-subject">
          <button data-v="team" class="on">Team</button>
          <button data-v="player">Player</button>
          <button data-v="group">Group</button></div></div>
      <div class="sc-fld"><label>Mode</label>
        <div class="sc-seg" id="sc-mode">
          <button data-v="builder" class="on">Builder</button>
          <button data-v="compare">Compare</button></div></div>
      <div class="sc-fld sc-compare-only"><label>Comparison</label>
        <div class="sc-seg" id="sc-intent">
          <button data-v="pop" class="on">vs Population</button>
          <button data-v="diff">vs Each Other</button></div></div>
      <div class="sc-fld" id="sc-basiswrap"><label>Basis</label>
        <select class="sc-input" id="sc-basis"></select></div>
      <div class="sc-fld" id="sc-diffwrap" style="display:none"><label>Difference by</label>
        <div class="sc-seg" id="sc-diffmetric">
          <button data-v="fg" class="on">FG%</button>
          <button data-v="rate">Rate</button></div></div>
      <div class="sc-fld"><label>Display</label>
        <div class="sc-togrow">
          <label class="sc-toggle"><input type="checkbox" id="sc-showpct"/> Percentiles</label>
          <label class="sc-toggle"><input type="checkbox" id="sc-showlbl" checked/> Labels</label></div></div>
      <div class="sc-fld sc-reset-fld"><label>&nbsp;</label>
        <button class="sc-btn ghost" id="sc-reset">Reset</button></div>
    </div>

    <div class="sc-courts" id="sc-courts">
      ${scChartColumnHTML('A')}
      ${scChartColumnHTML('B')}
    </div>

    <div class="sc-legend">
      <div class="sc-legbar" id="sc-legbar"></div>
      <div class="sc-leglbl" id="sc-leglbl"></div>
      <div class="sc-legsub" id="sc-legsub"></div>
      <div class="sc-btnrow" style="max-width:380px">
        <button class="sc-btn" id="sc-expA">Export A</button>
        <button class="sc-btn" id="sc-expB">Export B</button>
        <button class="sc-btn" id="sc-expPair">Export pair</button></div>
    </div>
  </div>`;

  // season selects
  ['A','B'].forEach(c=>{
    const sel=document.getElementById('sc-year'+c);
    sel.innerHTML=SC_YEARS.map(y=>`<option value="${y}" ${y===SC.charts[c].year?'selected':''}>${yLabel(y)}</option>`).join('');
    sel.onchange=async ()=>{
      const st=SC.charts[c];
      st.year=parseInt(sel.value);
      if(SC.subject==='team'){ await loadYear(st.year); scFillTeams(c); }
      else if(st.players.length){
        // player_id is career-stable, so carry chips into the new season; drop any
        // player who didn't play that year (name guard handles rare id collisions)
        const arr=await loadExplorerYear(st.year);
        st.players = st.players
          .map(p=>arr.find(r=>String(r.player_id)===String(p.player_id) && r.name===p.name))
          .filter(Boolean);
        scRenderChips(c);
      }
      scAutoTitle(c); scSyncTitlePlaceholders(); scRefreshBasis(); scRender();
    };
    // team select
    document.getElementById('sc-team'+c).onchange=e=>{ SC.charts[c].team=e.target.value; scAutoTitle(c); scSyncTitlePlaceholders(); scRender(); };
    // side toggle
    document.querySelectorAll('.sc-side'+c).forEach(btn=>btn.onclick=()=>{
      SC.charts[c].side=btn.dataset.s;
      document.querySelectorAll('.sc-side'+c).forEach(b=>b.classList.remove('on')); btn.classList.add('on');
      scRender();
    });
    // title / subtitle
    const tEl=document.getElementById('sc-title'+c);
    tEl.oninput=()=>{ SC.charts[c].title=tEl.value; SC.charts[c].titleEdited=tEl.value.trim().length>0; if(!SC.charts[c].titleEdited) scAutoTitle(c); scRender(); };
    const sEl=document.getElementById('sc-sub'+c);
    sEl.oninput=()=>{ SC.charts[c].subtitle=sEl.value; scRender(); };
    // helpers
    document.getElementById('sc-fill'+c).onclick=()=>{
      const st=SC.charts[c]; if(st.team){ st.title=st.team+' '+yLabel(st.year); st.titleEdited=true; document.getElementById('sc-title'+c).value=st.title; scRender(); }
    };
    document.getElementById('sc-namefill'+c).onclick=()=>{
      const st=SC.charts[c]; st.subtitle=st.players.map(r=>scLastName(r.name)).join(', ');
      document.getElementById('sc-sub'+c).value=st.subtitle; scRender();
    };
    document.getElementById('sc-clear'+c).onclick=()=>{
      SC.charts[c].players=[]; scRenderChips(c); scRefreshBasis(); scRender();
    };
    scSetupSearch(c);
  });

  // subject
  document.querySelectorAll('#sc-subject button').forEach(b=>b.onclick=async ()=>{
    SC.subject=b.dataset.v;
    document.querySelectorAll('#sc-subject button').forEach(x=>x.classList.toggle('on',x===b));
    SC.charts.A.players=[]; SC.charts.B.players=[];
    SC.basis=scDefaultBasis();
    if(SC.subject==='team'){ for(const c of ['A','B']){ await loadYear(SC.charts[c].year); scFillTeams(c);} }
    ['A','B'].forEach(c=>{ scRenderChips(c); SC.charts[c].titleEdited=false; scAutoTitle(c); });
    scApplyVisibility(); scRefreshBasis(); scRender();
  });
  // mode
  document.querySelectorAll('#sc-mode button').forEach(b=>b.onclick=()=>{
    SC.mode=b.dataset.v;
    document.querySelectorAll('#sc-mode button').forEach(x=>x.classList.toggle('on',x===b));
    if(SC.mode==='builder'){ SC.intent='pop'; scSetIntentButtons(); }
    scApplyVisibility(); scRefreshBasis(); scRender();
  });
  // intent
  document.querySelectorAll('#sc-intent button').forEach(b=>b.onclick=()=>{
    SC.intent=b.dataset.v; scSetIntentButtons();
    if(SC.intent==='diff'){ SC.showPct=false; document.getElementById('sc-showpct').checked=false; }
    scApplyVisibility(); scRender();
  });
  // diff metric
  document.querySelectorAll('#sc-diffmetric button').forEach(b=>b.onclick=()=>{
    SC.diffMetric=b.dataset.v;
    document.querySelectorAll('#sc-diffmetric button').forEach(x=>x.classList.toggle('on',x===b));
    scRender();
  });
  // basis / toggles
  document.getElementById('sc-basis').onchange=e=>{ SC.basis=e.target.value; scRender(); };
  document.getElementById('sc-showpct').onchange=e=>{ SC.showPct=e.target.checked; scRender(); };
  document.getElementById('sc-showlbl').onchange=e=>{ SC.showLabels=e.target.checked; scRender(); };
  document.getElementById('sc-reset').onclick=scReset;
  // export
  document.getElementById('sc-expA').onclick=()=>scExportPNG(document.querySelector('#sc-courtA svg'), scSlugName(SC.charts.A.title.trim(),'chartA'));
  document.getElementById('sc-expB').onclick=()=>scExportPNG(document.querySelector('#sc-courtB svg'), scSlugName(SC.charts.B.title.trim(),'chartB'));
  document.getElementById('sc-expPair').onclick=()=>scExportPair(document.querySelector('#sc-courtA svg'), document.querySelector('#sc-courtB svg'), 'shot-chart-compare.png');

  SC.mounted=true;
}

function scSetIntentButtons(){
  document.querySelectorAll('#sc-intent button').forEach(x=>x.classList.toggle('on',x.dataset.v===SC.intent));
}

/* full reset to the opening defaults (Team / Builder / vs Population, Houston→Duke seed) */
function scReset(){
  SC.subject='team'; SC.mode='builder'; SC.intent='pop'; SC.diffMetric='fg';
  SC.showPct=false; SC.showLabels=true; SC.basis='_pct';
  ['A','B'].forEach(c=>Object.assign(SC.charts[c],
    {year:2026, side:'o', team:null, players:[], title:'', subtitle:'', titleEdited:false, _seeded:false}));
  scMount();          // rebuild DOM + rebind (segmented defaults match the reset state)
  initShotCharts();   // reload team data, re-seed marquee teams, render
}

/* show/hide controls based on subject + mode + intent */
function scApplyVisibility(){
  const compare=SC.mode==='compare';
  document.querySelectorAll('.sc-compare-only').forEach(el=>el.style.display=compare?'':'none');
  // second column only in compare
  const colB=document.querySelectorAll('#sc-courts .sc-col')[1];
  if(colB) colB.style.display=compare?'':'none';
  document.getElementById('sc-expB').style.display=compare?'':'none';
  document.getElementById('sc-expPair').style.display=compare?'':'none';

  const teamSubj=SC.subject==='team';
  document.querySelectorAll('.sc-subj-team').forEach(el=>el.style.display=teamSubj?'':'none');
  document.querySelectorAll('.sc-subj-players').forEach(el=>el.style.display=teamSubj?'none':'');
  // search label wording
  ['A','B'].forEach(c=>{ const l=document.getElementById('sc-searchlab'+c); if(l) l.textContent = SC.subject==='player'?'Player':'Players (add 2+)'; });

  const pop=SC.intent==='pop';
  document.getElementById('sc-basiswrap').style.display=pop?'':'none';
  document.getElementById('sc-diffwrap').style.display=(!pop&&compare)?'':'none';
}

/* entry point — called by switchTab('shotcharts') */
async function initShotCharts(){
  if(!SC.mounted) scMount();
  if(SC.subject==='team'){
    for(const c of scActiveCharts()){ await loadYear(SC.charts[c].year); scFillTeams(c); }
    const arr=YCACHE[SC.charts.A.year]||[];
    // the team you were just viewing on Team Profile, if it exists in this season
    const ctx = (typeof cTeam==='string' && arr.find(r=>r.team_name===cTeam)) ? cTeam : null;
    if(!SC.charts.A._seeded){
      const seedA = ctx || (arr.find(r=>r.team_name==='Houston') ? 'Houston' : (arr[0]&&arr[0].team_name));
      if(seedA){ SC.charts.A.team=seedA; SC._seededTeam=seedA; const sel=document.getElementById('sc-teamA'); if(sel) sel.value=seedA; }
      if(SC.mode==='compare'){
        let seedB = arr.find(r=>r.team_name==='Duke') ? 'Duke' : (arr[1]&&arr[1].team_name);
        if(seedB===seedA){ const alt=arr.find(r=>r.team_name!==seedA); if(alt) seedB=alt.team_name; }
        if(seedB){ SC.charts.B.team=seedB; const selB=document.getElementById('sc-teamB'); if(selB) selB.value=seedB; }
      }
      SC.charts.A._seeded=true;
    } else if(ctx && ctx!==SC.charts.A.team && SC.charts.A.team===SC._seededTeam){
      // already seeded, but chart A is still on the auto-seeded team (untouched) and you
      // switched teams on Team Profile — follow you. A manual team pick is left alone.
      SC.charts.A.team=ctx; SC._seededTeam=ctx;
      const sel=document.getElementById('sc-teamA'); if(sel) sel.value=ctx;
    }
    scSyncTitlePlaceholders();
    ['A','B'].forEach(c=>scAutoTitle(c));
  }
  scApplyVisibility(); scRefreshBasis(); scRender();
}
