// ── TAB SWITCHING ─────────────────────────────────────────────────────────────
function updateURL(){
  if(!cTeam||!cYear)return;
  const params=new URLSearchParams();
  params.set('team',cTeam);
  params.set('year',cYear);
  if(cTab&&cTab!=='profile')params.set('tab',cTab);
  if(cView&&cView!=='d1')params.set('view',cView);
  if(cHistComp&&cHistComp!=='d1conf')params.set('hcomp',cHistComp);
  if(cTrendWindow&&cTrendWindow!==1)params.set('trend',cTrendWindow);
  history.replaceState(null,'','?'+params.toString());
}

function switchTab(tab,btn){
  cTab=tab;
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(el=>el.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  if(btn)btn.classList.add('active');
  updateURL();
  // Hide banner on About tab
  document.getElementById('banner').style.display=tab==='about'?'none':'';
  document.getElementById('page-desc').style.display=tab==='about'?'none':'';
  updatePageDesc();
  if(tab==='h2h')syncH2HTeamA();
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
  }
});

