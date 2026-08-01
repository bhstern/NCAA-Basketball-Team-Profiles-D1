// ── TAB SWITCHING ─────────────────────────────────────────────────────────────
function updateURL(){
  const params=new URLSearchParams();
  if(cTab==='explorer'){
    params.set('tab','explorer');            // Player Explorer is team-agnostic; keep the URL clean
    history.replaceState(null,'','?'+params.toString());
    return;
  }
  if(!cTeam||!cYear)return;
  params.set('team',cTeam);
  params.set('year',cYear);
  if(cTab&&cTab!=='profile')params.set('tab',cTab);
  if(cView&&cView!=='d1')params.set('view',cView);
  if(cHistComp&&cHistComp!=='d1conf')params.set('hcomp',cHistComp);
  if(cTrendWindow&&cTrendWindow!==1)params.set('trend',cTrendWindow);
  history.replaceState(null,'','?'+params.toString());
}

function switchProfileSubTab(sub, btn) {
  document.querySelectorAll('#profile-subtab-nav .hist-cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('profile-subtab-stats').style.display = sub === 'stats' ? 'block' : 'none';
  document.getElementById('profile-subtab-roster').style.display = sub === 'roster' ? 'block' : 'none';
  if (sub === 'roster' && cTeam && cYear) renderRoster();
  if (sub === 'stats' && cRow) renderProfile();
}

// navigate to a team's Team Profile from a clickable team name (roster, explorer, player profile)
// year (optional): land on that season if the team has it, else the team's most recent
function goToTeamProfile(teamName, year){
  if(!teamName) return;
  const tSel=document.getElementById('team-select');
  if(!tSel) return;
  const opt=[...tSel.options].find(o=>o.value.toLowerCase()===String(teamName).toLowerCase());
  if(!opt) return;                       // team not selectable (name mismatch) — do nothing
  tSel.value=opt.value;
  onTeamChange();                        // populate years + load the team's most-recent season
  if(year){                              // override to the clicked row's season if available
    const ySel=document.getElementById('year-select');
    const target=ySel && [...ySel.options].find(o=>String(o.value)===String(year));
    if(target && ySel.value!==target.value){ ySel.value=target.value; onSelectionChange(); }
  }
  const btn=document.querySelector('.nav-tab[data-tab="profile"]')||document.querySelector('.nav-tab');
  switchTab('profile', btn);
  window.scrollTo(0,0);
}
function goToTeamFromExplorer(teamName){   // explorer shows one selected year — carry it into the team profile
  const y=document.getElementById('explorer-year-select');
  goToTeamProfile(teamName, y?y.value:null);
}

function switchTab(tab,btn){
  cTab=tab;
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el=>el.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  if(btn)btn.classList.add('active');
  updateURL();
  // Hide banner and page desc on explorer and about tabs
  const hideBanner = tab==='about' || tab==='explorer' || tab==='shotcharts';
  const bannerEl = document.getElementById('banner');
  const descEl = document.getElementById('page-desc');
  if(bannerEl) bannerEl.style.display = hideBanner ? 'none' : '';
  if(descEl) descEl.style.display = hideBanner ? 'none' : '';
  if(tab !== 'about' && tab !== 'explorer' && tab !== 'shotcharts') updatePageDesc();
  if(tab==='explorer') initExplorer();
  if(tab==='shotcharts') initShotCharts();
  if(tab==='h2h') syncH2HTeamA();
  if(cRow){
    if(tab==='profile')renderProfile();
    else if(tab==='conference')renderConference();
    else if(tab==='historical'){initHistSelectors();renderHistorical();}
  }
}

function setAboutSection(section,btn){
  document.querySelectorAll('#tab-about .view-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('about-creator').style.display=section==='creator'?'block':'none';
  document.getElementById('about-sources').style.display=section==='sources'?'block':'none';
  document.getElementById('about-dictionary').style.display=section==='dictionary'?'block':'none';
}
loadIndex().then(async ()=>{
  // Check URL params for team deep link
  const params=new URLSearchParams(window.location.search);
  const pidParam=params.get('pid');
  if(pidParam){ openPlayerProfile(pidParam, params.get('view')); return; }   // shared player-profile deep link (+ optional tab)
  const teamParam=params.get('team');
  const yearParam=params.get('year');
  if(teamParam){
    const tSel=document.getElementById('team-select');
    const ySel=document.getElementById('year-select');
    const opt=[...tSel.options].find(o=>o.value.toLowerCase()===teamParam.toLowerCase());
    if(opt){
      tSel.value=opt.value;
      const teamName=opt.value;
      const availYears=Object.keys(INDEX).map(Number).filter(y=>INDEX[String(y)].includes(teamName)).sort((a,b)=>b-a);
      ySel.innerHTML='';
      availYears.forEach(y=>{const o=document.createElement('option');o.value=y;o.textContent=yLabel(y);ySel.appendChild(o);});
      document.getElementById('year-group').style.display='flex';
      if(yearParam&&availYears.includes(parseInt(yearParam)))ySel.value=yearParam;
      else if(availYears.length>0)ySel.value=availYears[0];
      // Restore view settings from URL
      const tabParam=params.get('tab');
      const viewParam=params.get('view');
      const hcompParam=params.get('hcomp');
      const trendParam=params.get('trend');
      if(viewParam)cView=viewParam;
      if(hcompParam)cHistComp=hcompParam;
      if(trendParam)cTrendWindow=parseInt(trendParam);
      await onSelectionChange();
      // Switch to saved tab after data loads
      if(tabParam){
        const tabBtn=[...document.querySelectorAll('.nav-tab')].find(b=>b.getAttribute('onclick')&&b.getAttribute('onclick').includes(`'${tabParam}'`));
        if(tabBtn)switchTab(tabParam,tabBtn);
      }
      // Restore view toggle button state
      if(viewParam){
        document.querySelectorAll('.view-btn').forEach(b=>{
          if(b.getAttribute('onclick')&&b.getAttribute('onclick').includes(`'${viewParam}'`))b.classList.add('active');
          else b.classList.remove('active');
        });
      }
    }
  } else if(params.get('tab')){
    // team-agnostic tab (e.g. Player Explorer) deep-linked without a team
    const tabParam=params.get('tab');
    const tabBtn=[...document.querySelectorAll('.nav-tab')].find(b=>b.getAttribute('onclick')&&b.getAttribute('onclick').includes(`'${tabParam}'`));
    if(tabBtn)switchTab(tabParam,tabBtn);
  }
});

