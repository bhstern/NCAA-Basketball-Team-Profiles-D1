// ── ROUTING ───────────────────────────────────────────────────────────────────
// Two layers (back/forward nav spec, 10.27):
//   * History entries — pushed ONLY by navigation: a top tab, a team / season, a player.
//   * View state — every in-view change (filters, sort, sub-tabs, toggles) rewrites the
//     CURRENT entry's URL in place, so Back / refresh / a shared link restore it, without
//     adding Back entries.
// applyRoute(params) is the one URL -> app-state function; the initial page load and
// Back/Forward (popstate) both go through it. While it runs, URL writes are suppressed,
// so a restore can never push. Scroll position and the explorer's "Show More" depth ride
// in history.state (Back restores them; a shared link starts at the top).

const ROUTE_TABS = ['profile','conference','explorer','historical','h2h','shotcharts','about','player'];
const TEAM_TABS = new Set(['profile','conference','historical']);
const ROUTE = {restoring:false, token:0, batch:0, pending:null, timer:null, replaceURL:null, scrollY:0};
const BANNER_TABS = new Set(['profile','conference','historical','h2h']);   // tabs that show the team banner
let cAboutSection = 'creator';
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
// Last scroll position, tracked as you scroll: when a navigation pushes, the new view is already
// on screen and the browser has clamped scrollY, so the entry being left must use this value.
window.addEventListener('scroll', () => { ROUTE.scrollY = window.scrollY; }, {passive:true});

// ---- current state -> URL ----
function routeParams(){
  const p = new URLSearchParams();
  const set = (k, v, def) => { if (v != null && v !== '' && v !== def) p.set(k, v); };
  if (cTab !== 'profile') p.set('tab', cTab);
  if (BANNER_TABS.has(cTab) && cTeam && cYear) { p.set('team', cTeam); p.set('year', cYear); }
  if (TEAM_TABS.has(cTab)) {
    if (cTab === 'profile') {
      set('view', cView, 'd1');
      if (profileSubTab() === 'roster') { p.set('sub', 'roster'); set('rstat', cRosterStatTab, 'overview'); }
    } else if (cTab === 'conference') {
      set('ccat', cConfCat, 'Overview');
      if (cCustomMode && cCompTeams.length) p.set('cmp', cCompTeams.join(','));
      else set('top', cTopN, 0);
    } else {
      set('hcat', cHistCat, 'Overview'); set('hcomp', cHistComp, 'd1conf'); set('trend', cTrendWindow, 1);
    }
  } else if (cTab === 'explorer') explorerRouteParams(p);
  else if (cTab === 'h2h') h2hRouteParams(p);
  else if (cTab === 'shotcharts') scRouteParams(p);
  else if (cTab === 'about') set('sec', cAboutSection, 'creator');
  else if (cTab === 'player') playerRouteParams(p);
  return p;
}
function routeURL(){ const qs = routeParams().toString(); return location.pathname + (qs ? '?' + qs : ''); }
function profileSubTab(){
  const r = document.getElementById('profile-subtab-roster');
  return r && r.style.display === 'block' ? 'roster' : 'stats';
}
function h2hRouteParams(p){
  const v = id => document.getElementById(id).value;
  if (v('h2h-team-a') && v('h2h-year-a')) p.set('a', v('h2h-team-a') + ':' + v('h2h-year-a'));
  if (v('h2h-team-b') && v('h2h-year-b')) p.set('b', v('h2h-team-b') + ':' + v('h2h-year-b'));
  if (cH2HCat !== 'Overview') p.set('cat', cH2HCat);
}

// ---- URL writes ----
// syncURL('push')    navigation: a new Back entry (only if the URL actually changes) + one GA page_view
// syncURL('replace') view-state change: rewrite the current entry in place (debounced — typing in a
//                    search box must not hit the browsers' replaceState rate limits)
function syncURL(mode){
  if (ROUTE.restoring) return;
  if (ROUTE.batch) { if (mode === 'push' || !ROUTE.pending) ROUTE.pending = mode; return; }
  if (mode === 'push') {
    // the entry being left keeps its latest view state (a pending replace) + where it was scrolled
    const here = ROUTE.replaceURL || (location.pathname + location.search);
    clearTimeout(ROUTE.timer); ROUTE.timer = null; ROUTE.replaceURL = null;
    const url = routeURL();
    if (url === here) { historyWrite('replace', {more: viewMore()}, url); return; }
    historyWrite('replace', {scrollY: ROUTE.scrollY}, here);
    historyWrite('push', {more: viewMore()}, url);
    sendPageView();
  } else {
    ROUTE.replaceURL = routeURL();          // computed now, so a navigation right after keeps it
    clearTimeout(ROUTE.timer);
    ROUTE.timer = setTimeout(() => {
      const url = ROUTE.replaceURL; ROUTE.timer = null; ROUTE.replaceURL = null;
      if (url && !ROUTE.restoring) historyWrite('replace', {more: viewMore()}, url);
    }, 150);
  }
}
function updateURL(){ syncURL('replace'); }
function viewMore(){ return cTab === 'explorer' ? cExplorerPage : 1; }
function historyWrite(kind, state, url){
  try {
    if (kind === 'push') history.pushState(state, '', url);
    else history.replaceState({...(history.state || {}), ...state}, '', url);
  } catch (e) { console.warn('history write skipped', e); }
}
// Several state changes that make up ONE navigation (e.g. a team link: team + season + tab)
// produce one history entry.
function routeBatch(fn){
  ROUTE.batch++;
  try { fn(); }
  finally {
    ROUTE.batch--;
    if (!ROUTE.batch && ROUTE.pending) { const m = ROUTE.pending; ROUTE.pending = null; syncURL(m); }
  }
}
// One GA page_view per real navigation (push + Back/Forward); none for in-place view-state updates.
// The initial load's page_view is gtag('config') itself. Assumes GA's "page changes based on
// browser history events" setting is OFF, so GA does not also count history changes on its own.
function sendPageView(){
  if (typeof gtag === 'function')
    gtag('event', 'page_view', {page_location: location.href, page_title: document.title});
}

// ---- URL -> state ----
async function applyRoute(params, opts = {}){
  const token = ++ROUTE.token;
  clearTimeout(ROUTE.timer); ROUTE.timer = null; ROUTE.replaceURL = null;
  ROUTE.restoring = true;
  try { await routeTo(params, token, opts); }
  catch (e) { console.error('route restore failed', e); }
  finally {
    if (token === ROUTE.token) {
      ROUTE.restoring = false;
      historyWrite('replace', {more: viewMore()}, routeURL());   // canonical URL for this entry
      // Back/Forward/refresh: back to where that page was scrolled (top if it was at the top);
      // a fresh shared link has no saved state and stays at the top
      if (opts.state) {
        const y = opts.state.scrollY || 0;
        requestAnimationFrame(() => { window.scrollTo(0, y); ROUTE.scrollY = window.scrollY; });
      }
    }
  }
  return token === ROUTE.token;
}

async function routeTo(params, token, opts){
  const stale = () => token !== ROUTE.token;
  let tab = params.get('tab');
  if (!ROUTE_TABS.includes(tab)) tab = 'profile';
  if (params.get('pid')) tab = 'player';               // ?pid=… alone is a player link
  if (tab === 'player' && !params.get('pid')) tab = 'profile';

  // each destination restores only its OWN view state; other tabs' state is left alone
  if (tab === 'profile' || (TEAM_TABS.has(tab) && params.has('view'))) {
    const v = params.get('view');
    cView = ['d1','conf','sub'].includes(v) ? v : 'd1';
    routeActivate('#profile-content .view-toggle .view-btn', cView);
  }
  if (tab === 'profile' && params.get('sub') === 'roster') {
    const r = params.get('rstat');
    cRosterStatTab = ['overview','advanced','shooting'].includes(r) ? r : 'overview';
    routeActivate('#roster-stat-tabs .hist-cat-btn', cRosterStatTab);
  }
  if (tab === 'historical' || (TEAM_TABS.has(tab) && (params.has('hcomp') || params.has('trend')))) {
    const hc = params.get('hcomp');
    cHistComp = ['d1conf','d1','sub'].includes(hc) ? hc : 'd1conf';
    cTrendWindow = [1,2,3].includes(parseInt(params.get('trend'))) ? parseInt(params.get('trend')) : 1;
    routeActivate('.hist-comp-btn[onclick^="setHistComp"]', cHistComp);
    routeActivate('.hist-comp-btn[onclick^="setTrendWindow"]', cTrendWindow);
  }
  if (tab === 'historical') {
    const hcat = params.get('hcat');
    cHistCat = ['Overview','Offense','Defense','Shot Profile'].includes(hcat) ? hcat : 'Overview';
    document.querySelectorAll('#hist-cat-filter .hist-cat-btn').forEach(b => b.classList.toggle('active', b.textContent === cHistCat));
  }

  // team context: a team URL sets it; a team tab without one is the "no team selected" page;
  // other tabs keep whatever team you had
  const teamParam = params.get('team');
  if (teamParam) {
    const team = selectTeamYear(teamParam, params.get('year'));
    if (team) {
      const yr = parseInt(document.getElementById('year-select').value);
      if (team !== cTeam || yr !== cYear || !cRow) await onSelectionChange();
      if (stale()) return;
    }
  } else if (TEAM_TABS.has(tab)) clearTeamSelection();

  if (tab === 'conference') {
    const cc = params.get('ccat');
    cConfCat = ['Overview','Offense','Defense','Shot Profile','All'].includes(cc) ? cc : 'Overview';
    routeActivate('#conf-cat-filter .hist-cat-btn', cConfCat);
    cCompTeams = params.get('cmp') ? params.get('cmp').split(',').filter(t => t && t !== cTeam) : [];
    cCustomMode = cCompTeams.length > 0;
    const n = parseInt(params.get('top'));
    cTopN = [1,2,3,4,5].includes(n) ? n : 0;
    document.querySelectorAll('.top-n-btn').forEach(b => b.classList.toggle('active',
      !cCustomMode && parseInt(b.textContent) == cTopN || (b.textContent === 'All' && cTopN === 0)));
  }
  if (tab === 'explorer') cExplorerPendingRoute = {params, more: opts.state && opts.state.more};

  if (tab === 'player') {
    await openPlayerProfile(params.get('pid'), params.get('view'), {
      st: params.get('st'), ctx: params.get('ctx'), ss: params.get('ss'),
      sb: params.get('sb'), cmp: params.get('cmp'),
    });
    return;
  }

  await switchTab(tab, document.querySelector(`.nav-tab[data-tab="${tab}"]`));
  if (stale()) return;

  if (tab === 'profile') {
    const sub = params.get('sub') === 'roster' ? 'roster' : 'stats';
    await switchProfileSubTab(sub, document.getElementById(sub === 'roster' ? 'pst-roster' : 'pst-stats'));
  } else if (tab === 'h2h') {
    const pick = (k, team, year) => {
      const v = params.get(k); if (!v) return false;
      const i = v.lastIndexOf(':');
      document.getElementById(team).value = v.slice(0, i);
      document.getElementById(year).value = v.slice(i + 1);
      return true;
    };
    pick('a', 'h2h-team-a', 'h2h-year-a');      // after switchTab's sync, so a URL matchup wins
    if (!pick('b', 'h2h-team-b', 'h2h-year-b')) {
      document.getElementById('h2h-team-b').value = ''; document.getElementById('h2h-year-b').value = '';
    }
    const cat = params.get('cat');
    cH2HCat = ['Overview','Offense','Defense','Shot Profile','All'].includes(cat) ? cat : 'Overview';
    routeActivate('#h2h-cat-filter .hist-cat-btn', cH2HCat);
    await renderH2H();
  } else if (tab === 'shotcharts') {
    await scApplyRoute(params);
  } else if (tab === 'about') {
    const sec = ['creator','dictionary','sources'].includes(params.get('sec')) ? params.get('sec') : 'creator';
    setAboutSection(sec, document.querySelector(`#tab-about .view-btn[onclick*="'${sec}'"]`));
  }
}

// select a team (case-insensitive) + a season it has (else its most recent) in the banner selects;
// returns the team name, or null if no such team
function selectTeamYear(teamName, year){
  const tSel = document.getElementById('team-select');
  const ySel = document.getElementById('year-select');
  const opt = [...tSel.options].find(o => o.value && o.value.toLowerCase() === String(teamName).toLowerCase());
  if (!opt) return null;
  tSel.value = opt.value;
  const availYears = Object.keys(INDEX).map(Number).filter(y => INDEX[String(y)].includes(opt.value)).sort((a,b) => b - a);
  ySel.innerHTML = '';
  availYears.forEach(y => { const o = document.createElement('option'); o.value = y; o.textContent = yLabel(y); ySel.appendChild(o); });
  document.getElementById('year-group').style.display = 'flex';
  if (year && availYears.includes(parseInt(year))) ySel.value = String(parseInt(year));
  else if (availYears.length > 0) ySel.value = availYears[0];
  return opt.value;
}

// back to the "no team selected" page (a bare URL)
function clearTeamSelection(){
  if (!cTeam) return;
  document.getElementById('team-select').value = '';
  document.getElementById('year-group').style.display = 'none';
  cTeam = null; cYear = null; cRow = null; cYearData = null; cCompTeams = []; cCustomMode = false;
  document.getElementById('banner-team').style.display = 'none';
  document.getElementById('banner-summary').style.display = 'none';
  showLoading(); showEmpty('Select a team and season above');
}

// mark the button whose onclick's first argument equals `value` as active, within `selector`
function routeActivate(selector, value){
  document.querySelectorAll(selector).forEach(b => {
    const m = (b.getAttribute('onclick') || '').match(/^\s*\w+\(\s*'?([^']*?)'?\s*,/);
    b.classList.toggle('active', !!m && m[1] === String(value));
  });
}

window.addEventListener('popstate', e => {
  applyRoute(new URLSearchParams(location.search), {state: e.state}).then(current => { if (current) sendPageView(); });
});

// ── TAB SWITCHING ─────────────────────────────────────────────────────────────
function switchProfileSubTab(sub, btn) {
  document.querySelectorAll('#profile-subtab-nav .hist-cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('profile-subtab-stats').style.display = sub === 'stats' ? 'block' : 'none';
  document.getElementById('profile-subtab-roster').style.display = sub === 'roster' ? 'block' : 'none';
  syncURL('replace');
  if (sub === 'roster' && cTeam && cYear) return renderRoster();
  if (sub === 'stats' && cRow) renderProfile();
}

// navigate to a team's Team Profile from a clickable team name (roster, explorer, player profile)
// year (optional): land on that season if the team has it, else the team's most recent
// One click = one Back entry (team + season + tab are batched into a single push).
function goToTeamProfile(teamName, year){
  if(!teamName) return;
  const tSel=document.getElementById('team-select');
  if(!tSel) return;
  const opt=[...tSel.options].find(o=>o.value.toLowerCase()===String(teamName).toLowerCase());
  if(!opt) return;                       // team not selectable (name mismatch) — do nothing
  routeBatch(()=>{
    tSel.value=opt.value;
    onTeamChange();                        // populate years + load the team's most-recent season
    if(year){                              // override to the clicked row's season if available
      const ySel=document.getElementById('year-select');
      const target=ySel && [...ySel.options].find(o=>String(o.value)===String(year));
      if(target && ySel.value!==target.value){ ySel.value=target.value; onSelectionChange(); }
    }
    const btn=document.querySelector('.nav-tab[data-tab="profile"]')||document.querySelector('.nav-tab');
    switchTab('profile', btn);
  });
  window.scrollTo(0,0);
}
function goToTeamFromExplorer(teamName){   // explorer shows one selected year — carry it into the team profile
  const y=document.getElementById('explorer-year-select');
  goToTeamProfile(teamName, y?y.value:null);
}

// returns the tab's init promise (explorer, shot charts) so the router can wait for it
function switchTab(tab,btn){
  cTab=tab;
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el=>el.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  if(btn)btn.classList.add('active');
  syncURL('push');
  // Hide banner and page desc on explorer and about tabs
  const hideBanner = tab==='about' || tab==='explorer' || tab==='shotcharts';
  const bannerEl = document.getElementById('banner');
  const descEl = document.getElementById('page-desc');
  if(bannerEl) bannerEl.style.display = hideBanner ? 'none' : '';
  if(descEl) descEl.style.display = hideBanner ? 'none' : '';
  if(tab !== 'about' && tab !== 'explorer' && tab !== 'shotcharts') updatePageDesc();
  let ready=null;
  if(tab==='explorer') ready=initExplorer();
  if(tab==='shotcharts') ready=initShotCharts();
  if(tab==='h2h') syncH2HTeamA();
  if(cRow){
    if(tab==='profile')renderProfile();
    else if(tab==='conference')renderConference();
    else if(tab==='historical'){initHistSelectors();renderHistorical();}
  }
  return ready;
}

function setAboutSection(section,btn){
  cAboutSection=section;
  document.querySelectorAll('#tab-about .view-btn').forEach(b=>b.classList.remove('active'));
  if(btn) btn.classList.add('active');
  document.getElementById('about-creator').style.display=section==='creator'?'block':'none';
  document.getElementById('about-sources').style.display=section==='sources'?'block':'none';
  document.getElementById('about-dictionary').style.display=section==='dictionary'?'block':'none';
  syncURL('replace');
}

// initial load: deep links, refresh and bare URLs all go through the router
// (a refresh keeps history.state, so scroll position + Show More depth survive it)
loadIndex().then(()=>applyRoute(new URLSearchParams(window.location.search), {initial:true, state:history.state}));
