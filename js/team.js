
async function loadIndex(){
  try{const r=await fetch('data/index.json');INDEX=await r.json();initSelectors();}
  catch(e){document.getElementById('profile-empty').textContent='Error: '+e.message;console.error(e);}
}

async function loadYear(y){
  if(YCACHE[y])return YCACHE[y];
  const r=await fetch(`data/cbb_${y}.json`);const d=await r.json();YCACHE[y]=d;return d;
}

function initSelectors(){
  const years=Object.keys(INDEX).map(Number).sort((a,b)=>b-a);
  const teams=[...new Set(Object.values(INDEX).flat())].sort();
  const tSel=document.getElementById('team-select');
  teams.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;tSel.appendChild(o);});
  const ySel=document.getElementById('year-select');
  years.forEach(y=>{const o=document.createElement('option');o.value=y;o.textContent=yLabel(y);ySel.appendChild(o);});
  ['h2h-team-a','h2h-team-b'].forEach(id=>{const s=document.getElementById(id);teams.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;s.appendChild(o);});});
  ['h2h-year-a','h2h-year-b'].forEach(id=>{const s=document.getElementById(id);years.forEach(y=>{const o=document.createElement('option');o.value=y;o.textContent=yLabel(y);s.appendChild(o);});});
  const cf=document.getElementById('hist-cat-filter');
  ['Overview','Offense','Defense','Shot Profile'].forEach((c,i)=>{
    const b=document.createElement('button');b.className='hist-cat-btn'+(i===0?' active':'');
    b.textContent=c;b.onclick=()=>setHistCat(c,b);cf.appendChild(b);
  });
  // No default team - blank on load unless URL param provided
}

function onTeamChange(){
  const team=document.getElementById('team-select').value;
  if(!team)return;
  const ySel=document.getElementById('year-select');
  const availYears=Object.keys(INDEX).map(Number).filter(y=>INDEX[String(y)].includes(team)).sort((a,b)=>b-a);
  ySel.innerHTML='';
  availYears.forEach(y=>{const o=document.createElement('option');o.value=y;o.textContent=yLabel(y);ySel.appendChild(o);});
  document.getElementById('year-group').style.display='flex';
  if(availYears.length>0)ySel.value=availYears[0];
  onSelectionChange();
}

async function onSelectionChange(){
  const team=document.getElementById('team-select').value;
  const year=parseInt(document.getElementById('year-select').value);
  if(!team||!year)return;
  cTeam=team;cYear=year;cCompTeams=[];cCustomMode=false;
  // Update URL so refresh/share preserves selection
  updateURL();
  showLoading();
  try{
    const yd=await loadYear(year);cYearData=yd;
    const row=yd.find(d=>d.team_name===team);
    if(!row){showEmpty(`No data for ${team} in ${year}`);return;}
    cRow=row;
    updateBanner(row);updateSubLabels(row);
    renderTab();
    // If roster sub-tab is active, re-render roster for new team/year
    const rosterSubTab = document.getElementById('profile-subtab-roster');
    if (rosterSubTab && rosterSubTab.style.display !== 'none') {
      renderRoster();
    }
  }catch(e){showEmpty('Error: '+e.message);console.error(e);}
}

function showLoading(){
  ['profile','conference','historical','roster'].forEach(t=>{
    const e=document.getElementById(`${t}-empty`);if(e)e.style.display='none';
    const l=document.getElementById(`${t}-loading`);if(l)l.style.display='flex';
    const c=document.getElementById(`${t}-content`);if(c)c.style.display='none';
  });
  // Hide roster controls while loading new team/year
  const cw=document.getElementById('roster-controls-wrap');if(cw)cw.style.display='none';
}
function showEmpty(msg){
  ['profile','conference','historical','roster'].forEach(t=>{
    const l=document.getElementById(`${t}-loading`);if(l)l.style.display='none';
    const e=document.getElementById(`${t}-empty`);if(e){e.textContent=msg;e.style.display='flex';}
  });
}

function updateBanner(row){
  document.getElementById('banner-team').style.display='flex';
  document.getElementById('banner-summary').style.display='flex';
  const tlogo=document.getElementById('banner-team-logo');
  tlogo.style.display='block';
  tlogo.src=`${TDIR}${sf(row.team_name)}.png`;
  document.getElementById('banner-team-name').textContent=row.team_name;
  const cs=row.conference.replace(/ /g,'_').replace(/-/g,'_').replace(/\//g,'_');
  const clogo=document.getElementById('banner-conf-logo');
  clogo.style.display='block';
  clogo.src=`${CDIR}${cs}.png`;
  document.getElementById('banner-conf-name').textContent=row.conference;
  document.getElementById('banner-record').textContent=row.full_season_record;
  const em=parseFloat(row.adj_em);
  document.getElementById('banner-adjem').textContent=(em>0?'+':'')+em.toFixed(1);
  document.getElementById('banner-rank').textContent='#'+row.adj_em_rank;

  // ── Strengths / weaknesses — 3-pass tiered system ────────────────────
  const strTags=[], wkTags=[];
  const subLbl=isPower(row)?'vs. Power Conf':'vs. Mid Major';

  // Categorize each tag as offense or defense
  const OFF_KEYS=new Set(['efg_rate_off','tov_rate_off','orb_rate_off','ft_rate_off','ft_pct_off','ast_pct_off']);
  const DEF_KEYS=new Set(['efg_rate_def','tov_rate_def','orb_rate_def','ft_rate_def','ast_pct_def']);
  const OFF_SHOTS=new Set(['3-Point Shooting','Rim Finishing','Midrange Shooting']);
  const DEF_SHOTS=new Set(['3PT Defense','Rim Protection','Midrange Defense']);
  function getSide(label,key){
    if(key&&OFF_KEYS.has(key))return'off';
    if(key&&DEF_KEYS.has(key))return'def';
    if(OFF_SHOTS.has(label))return'off';
    if(DEF_SHOTS.has(label))return'def';
    return'off';
  }

  // Shot checks — custom str/wk logic per shot type and side
  const shotDefs=[
    {rk:'off_threes_rate_total_pct',fk:'off_threes_fg_pct',srk:'off_threes_rate_total_sub_pct',sfk:'off_threes_fg_sub_pct',label:'3-Point Shooting',
     strFn:(r,f)=>r>=0.65&&f>=0.65, wkFn:(r,f)=>r>=0.65&&f<=0.35, sortKey:(r,f)=>f*0.65+(1-r)*0.35},
    {rk:'off_rim_rate_total_pct',fk:'off_rim_fg_pct',srk:'off_rim_rate_total_sub_pct',sfk:'off_rim_fg_sub_pct',label:'Rim Finishing',
     strFn:(r,f)=>r>=0.65&&f>=0.65, wkFn:(r,f)=>r>=0.50&&f<=0.35, sortKey:(r,f)=>f*0.65+(1-r)*0.35},
    {rk:'off_long_twos_rate_total_pct',fk:'off_long_twos_fg_pct',srk:'off_long_twos_rate_total_sub_pct',sfk:'off_long_twos_fg_sub_pct',label:'Midrange Shooting',
     strFn:(r,f)=>r>=0.65&&f>=0.65, wkFn:(r,f)=>r>=0.65&&f<=0.35, sortKey:(r,f)=>f*0.65+(1-r)*0.35},
    {rk:'def_threes_rate_total_pct',fk:'def_threes_fg_pct',srk:'def_threes_rate_total_sub_pct',sfk:'def_threes_fg_sub_pct',label:'3PT Defense',
     strFn:(r,f)=>f>=0.75, wkFn:(r,f)=>f<=0.25&&r>=0.35, sortKey:(r,f)=>f},
    {rk:'def_rim_rate_total_pct',fk:'def_rim_fg_pct',srk:'def_rim_rate_total_sub_pct',sfk:'def_rim_fg_sub_pct',label:'Rim Protection',
     strFn:(r,f)=>f>=0.75&&r<=0.50, wkFn:(r,f)=>f<=0.25&&r>=0.35, sortKey:(r,f)=>f},
    {rk:'def_long_twos_rate_total_pct',fk:'def_long_twos_fg_pct',srk:'def_long_twos_rate_total_sub_pct',sfk:'def_long_twos_fg_sub_pct',label:'Midrange Defense',
     strFn:(r,f)=>false, wkFn:(r,f)=>f<=0.25, sortKey:(r,f)=>f},
  ];

  // Collect all qualifiers for a given pass
  function collectPass(pctField,subField,strCls,wkCls,passNum){
    const strs=[],wks=[];
    SUMMARY_KEYS.forEach(k=>{
      const p=parseFloat(row[k+pctField]);if(isNaN(p))return;
      const lbl=SUMMARY_LABELS[k];
      if(p>=0.75)strs.push({label:lbl,cls:strCls,pass:passNum,pct:p,side:getSide(lbl,k)});
      else if(p<=0.25)wks.push({label:lbl,cls:wkCls,pass:passNum,pct:p,side:getSide(lbl,k)});
    });
    shotDefs.forEach(sc=>{
      const rk=subField?sc.srk:sc.rk, fk=subField?sc.sfk:sc.fk;
      const rate=parseFloat(row[rk]),fg=parseFloat(row[fk]);
      if(isNaN(rate)||isNaN(fg))return;
      if(sc.strFn(rate,fg))strs.push({label:sc.label,cls:strCls,pass:passNum,pct:sc.sortKey(rate,fg),side:getSide(sc.label,null)});
      else if(sc.wkFn(rate,fg))wks.push({label:sc.label,cls:wkCls,pass:passNum,pct:sc.sortKey(rate,fg),side:getSide(sc.label,null)});
    });
    return{strs,wks};
  }

  // Pass 2 uses looser thresholds for SUMMARY_KEYS and shot checks
  function collectPass2(){
    const strs=[],wks=[];
    const usedStrLabels=new Set(strTags.map(t=>t.label));
    const usedWkLabels=new Set(wkTags.map(t=>t.label));
    SUMMARY_KEYS.forEach(k=>{
      const p=parseFloat(row[k+'_pct']);if(isNaN(p))return;
      const lbl=SUMMARY_LABELS[k];
      if(p>=0.65&&p<0.75&&!usedStrLabels.has(lbl))strs.push({label:lbl,cls:'strength-tag-2',pass:2,pct:p,side:getSide(lbl,k)});
      else if(p<=0.35&&p>0.25&&!usedWkLabels.has(lbl))wks.push({label:lbl,cls:'weakness-tag-2',pass:2,pct:p,side:getSide(lbl,k)});
    });
        // Shot checks: Pass 1 only
    return{strs,wks};
  }

  // Smart fill: pass quality first, balance as tiebreaker when 4+ qualify
  function smartFill(tags,candidates,isStr){
    if(tags.length>=4)return;
    const slots=4-tags.length;
    if(candidates.length<=slots){candidates.forEach(t=>tags.push(t));return;}
    const offCands=candidates.filter(t=>t.side==='off');
    const defCands=candidates.filter(t=>t.side==='def');
    const hasBothSides=offCands.length>0&&defCands.length>0;
    if(hasBothSides&&slots>=2){
      const bestOff=offCands[0],bestDef=defCands[0];
      // Only guarantee defensive slot if best def pct is within 20pts of best off
      // Otherwise just take top by percentile (don't sacrifice quality for balance)
      const pctGap=Math.abs(bestOff.pct-bestDef.pct);
      if(pctGap<=0.20){
        const guaranteed=[bestOff,bestDef];
        const remaining=candidates.filter(t=>t!==bestOff&&t!==bestDef);
        [...guaranteed,...remaining].slice(0,slots).forEach(t=>tags.push(t));
      } else {
        candidates.slice(0,slots).forEach(t=>tags.push(t));
      }
    } else if(hasBothSides&&slots===1){
      const sidesInTags=new Set(tags.map(t=>t.side));
      const missingSide=sidesInTags.has('off')&&!sidesInTags.has('def')?'def':
                        sidesInTags.has('def')&&!sidesInTags.has('off')?'off':null;
      if(missingSide){
        const mc=candidates.find(t=>t.side===missingSide);
        // Only prefer missing side if within 15pct of best overall
        if(mc&&Math.abs(candidates[0].pct-mc.pct)<=0.15)tags.push(mc);
        else tags.push(candidates[0]);
      } else {
        tags.push(candidates[0]);
      }
    } else {
      candidates.slice(0,slots).forEach(t=>tags.push(t));
    }
  }

  // ── PASS 1 ────────────────────────────────────────────────────────────────
  const p1=collectPass('_pct',false,'strength-tag','weakness-tag',1);
  const p1Strs=p1.strs.sort((a,b)=>b.pct-a.pct);
  const p1Wks=p1.wks.sort((a,b)=>a.pct-b.pct);
  smartFill(strTags,p1Strs,true);
  smartFill(wkTags,p1Wks,false);

  // ── PASS 2 ────────────────────────────────────────────────────────────────
  if(strTags.length<4||wkTags.length<4){
    const p2=collectPass2();
    const p2Strs=p2.strs.sort((a,b)=>b.pct-a.pct);
    const p2Wks=p2.wks.sort((a,b)=>a.pct-b.pct);
    if(strTags.length<4)smartFill(strTags,p2Strs,true);
    if(wkTags.length<4)smartFill(wkTags,p2Wks,false);
  }

  // ── PASS 3: subgroup ──────────────────────────────────────────────────────
  if(strTags.length<4||wkTags.length<4){
    const usedStrLabels=new Set(strTags.map(t=>t.label));
    const usedWkLabels=new Set(wkTags.map(t=>t.label));
    const p3Strs=[],p3Wks=[];
    SUMMARY_KEYS.forEach(k=>{
      const sp=parseFloat(row[k+'_sub_pct']);if(isNaN(sp))return;
      const lbl=SUMMARY_LABELS[k];
      if(sp>=0.75&&!usedStrLabels.has(lbl))p3Strs.push({label:lbl,cls:'strength-tag-3',pass:3,pct:sp,side:getSide(lbl,k)});
      else if(sp<=0.35&&!usedWkLabels.has(lbl))p3Wks.push({label:lbl,cls:'weakness-tag-3',pass:3,pct:sp,side:getSide(lbl,k)});
    });
    // Shot checks: Pass 1 only — no Pass 3 for shot types
    if(strTags.length<4)smartFill(strTags,p3Strs.sort((a,b)=>b.pct-a.pct),true);
    if(wkTags.length<4)smartFill(wkTags,p3Wks.sort((a,b)=>a.pct-b.pct),false);
  }

  // ── Sort: pass first, then offense/defense, then pct ─────────────────────
  strTags.sort((a,b)=>{
    if(a.pass!==b.pass)return a.pass-b.pass;
    const s=(a.side==='off'?0:1)-(b.side==='off'?0:1);
    return s!==0?s:b.pct-a.pct;
  });
  wkTags.sort((a,b)=>{
    if(a.pass!==b.pass)return a.pass-b.pass;
    const s=(a.side==='off'?0:1)-(b.side==='off'?0:1);
    return s!==0?s:a.pct-b.pct;
  });

    const sEl=document.getElementById('summary-strengths');
  sEl.innerHTML=`<span class="summary-label">Strengths</span>`+
    (strTags.length?strTags.map(t=>{
      const lbl=t.pass===3?` <span style="font-size:8px;opacity:0.8">${subLbl}</span>`:t.pass===2?` <span style="font-size:8px;opacity:0.8">Relative</span>`:'';
      return`<span class="${t.cls}">${t.label}${lbl}</span>`;
    }).join(''):'<span style="font-size:10px;color:var(--text4)">—</span>')+
    `<span class="d1-label">vs. All D1</span>`;
  const wEl=document.getElementById('summary-weaknesses');
  wEl.innerHTML=`<span class="summary-label">Weaknesses</span>`+
    (wkTags.length?wkTags.map(t=>{
      const lbl=t.pass===3?` <span style="font-size:8px;opacity:0.8">${subLbl}</span>`:t.pass===2?` <span style="font-size:8px;opacity:0.8">Relative</span>`:'';
      return`<span class="${t.cls}">${t.label}${lbl}</span>`;
    }).join(''):'<span style="font-size:10px;color:var(--text4)">—</span>')+
    `<span class="d1-label">vs. All D1</span>`;

  recalcBlurb(row,'d1');
}

function recalcBlurb(row,view){
  const pctSuffix=view==='conf'?'_conf_pct':view==='sub'?'_sub_pct':'_pct';
  const offThreeR=parseFloat(row['off_threes_rate_total'+pctSuffix]);
  const offRimR=parseFloat(row['off_rim_rate_total'+pctSuffix]);
  const offMidR=parseFloat(row['off_long_twos_rate_total'+pctSuffix]);
  const offRimRaw=parseFloat(row.off_rim_rate_total);
  const offThreeRaw=parseFloat(row.off_threes_rate_total);
  const offMidRaw=parseFloat(row.off_long_twos_rate_total);
  const fg3=parseFloat(row['off_threes_fg'+pctSuffix]);
  const fgRim=parseFloat(row['off_rim_fg'+pctSuffix]);
  const fgMid=parseFloat(row['off_long_twos_fg'+pctSuffix]);
  const defThreeR=parseFloat(row['def_threes_rate_total'+pctSuffix]);
  const defRimR=parseFloat(row['def_rim_rate_total'+pctSuffix]);
  const defMidR=parseFloat(row['def_long_twos_rate_total'+pctSuffix]);
  const dfg3=parseFloat(row['def_threes_fg'+pctSuffix]);
  const dfgRim=parseFloat(row['def_rim_fg'+pctSuffix]);
  const dfgMid=parseFloat(row['def_long_twos_fg'+pctSuffix]);
  const offDunkR=parseFloat(row.off_dunks_rate_total_pct);
  const offDunkFG=parseFloat(row.off_dunks_fg_pct);
  const efgOff=parseFloat(row['efg_rate_off'+pctSuffix]);
  const efgDef=parseFloat(row['efg_rate_def'+pctSuffix]);
  const nm=row.team_name;
  // Standalone thresholds: D1=80/20, conf/sub=75/25
  const stLo=view==='d1'?0.20:0.25;
  const stHi=view==='d1'?0.80:0.75;
  let blurb='';

  if(!isNaN(offThreeR)&&!isNaN(offRimR)&&!isNaN(offMidR)){

    // ── FG% TIER — view-aware ────────────────────────────────────────────────
    function fgTier(pct){
      if(isNaN(pct))return 'neutral';
      const d=view==='d1';
      if(pct>=(d?0.85:0.80))return 'elite';
      if(pct>=(d?0.75:0.70))return 'strong';
      if(pct>=(d?0.65:0.60))return 'abvavg';
      if(pct>=(d?0.35:0.40))return 'neutral';
      if(pct>=(d?0.25:0.30))return 'blwavg';
      if(pct>=(d?0.15:0.20))return 'poor';
      return 'verypoor';
    }
    function isPos(t){return t==='elite'||t==='strong'||t==='abvavg';}
    function isNeg(t){return t==='blwavg'||t==='poor'||t==='verypoor';}

    // ── PRIORITY SCORING ─────────────────────────────────────────────────────
    const locWeights={rim:1.0,threes:1.0,mid:0.75};
    function extremity(pct){return Math.abs(pct-0.5)*2;}
    function shotScore(r,fg,s){return(extremity(r)+extremity(fg))/2*locWeights[s];}
    function rankShots(rm,fgm){
      return['rim','threes','mid'].sort((a,b)=>shotScore(rm[b],fgm[b],b)-shotScore(rm[a],fgm[a],a));
    }

    // ── DEFENSE VERB TRACKING ────────────────────────────────────────────────
    let defPosMentions=0,defNegMentions=0,defFGQCount=0;
    function defPosVerb(){return defPosMentions++===0?'maintain':'sustain';}
    function defNegVerb(){return defNegMentions++===0?'post':'register';}
    // defFGQuality rotates elite↔very strong, solid↔above average
    function defFGQuality(shot,fgPct){
      const t=fgTier(fgPct);
      const i=defFGQCount++%2;
      const labels={
        rim:{
          elite:['elite rim protection','very strong rim protection'],
          strong:['strong rim protection','strong rim protection'],
          abvavg:['solid rim protection','above average rim protection'],
          blwavg:['below average rim protection','below average rim protection'],
          poor:['poor rim protection','poor rim protection'],
          verypoor:['very poor rim protection','very poor rim protection']
        },
        threes:{
          elite:['elite three-point defense','very strong three-point defense'],
          strong:['strong three-point defense','strong three-point defense'],
          abvavg:['solid three-point defense','above average three-point defense'],
          blwavg:['below average three-point defense','below average three-point defense'],
          poor:['poor three-point defense','poor three-point defense'],
          verypoor:['very poor three-point defense','very poor three-point defense']
        },
        mid:{
          elite:['elite midrange defense','very strong midrange defense'],
          strong:['strong midrange defense','strong midrange defense'],
          abvavg:['solid midrange defense','above average midrange defense'],
          blwavg:['below average midrange defense','below average midrange defense'],
          poor:['poor midrange defense','poor midrange defense'],
          verypoor:['very poor midrange defense','very poor midrange defense']
        }
      };
      const pool=labels[shot];
      if(!pool||!pool[t])return '';
      return pool[t][Math.min(i,pool[t].length-1)];
    }

    // ── OFF FG% INLINE MODIFIER ──────────────────────────────────────────────
    let usedOffPhrases=[];
    function offFGMod(shot,fgPct,ratePct){
      const t=fgTier(fgPct);
      const highRate=!isNaN(ratePct)&&ratePct>=0.65;
      if(t==='neutral'&&!highRate)return '';
      const phrases={
        threes:{
          elite:[' and shoots at an elite percentage from deep',' and knocks them down at an elite rate',' and converts at an elite clip from three'],
          strong:[' and shoots at a strong percentage from deep',' and knocks them down at a strong rate',' and converts at a strong clip from three'],
          abvavg:[' and shoots at an above average percentage from deep',' and converts at an above average rate from deep'],
          neutral:[', though they convert at an average clip from deep',', though they shoot at an average percentage from deep'],
          blwavg:[', but shoots a below average percentage from deep',', but converts from three at a below average rate'],
          poor:[', but shoots a poor percentage from deep',', but struggles to knock them down from deep',', but has poor conversion from deep'],
          verypoor:[', but shoots a very poor percentage from deep',', but struggles to convert from three',', but has very poor finishing from deep']
        },
        rim:{
          elite:[' and finishes at an elite percentage',' and converts at an elite rate around the basket',' and has elite finishing at the rim'],
          strong:[' and finishes at a strong percentage',' and converts at a strong rate inside',' and is a strong finisher at the rim'],
          abvavg:[' and finishes at an above average percentage',' and converts at an above average rate at the rim',' and is an above average finisher at the rim'],
          neutral:[', though they finish at an average percentage',', though they convert at an average rate at the rim'],
          blwavg:[' but finishes at a below average percentage',' but converts at a below average rate at the rim',' but has poor finishing inside'],
          poor:[' but struggles to finish inside',' but has poor finishing at the rim',' but converts at a poor rate at the rim'],
          verypoor:[' but struggles significantly to finish at the rim',' but has very poor finishing inside',' but greatly struggles to convert at the rim']
        },
        mid:{
          elite:[' and shoots midrange at an elite percentage',' and converts midrange shots at an elite rate',' and has elite midrange efficiency'],
          strong:[' and shoots midrange at a strong percentage',' and converts midrange shots at a strong rate'],
          abvavg:[' and shoots midrange at an above average percentage',' and converts midrange shots at an above average rate'],
          neutral:[', though they shoot midrange at an average percentage'],
          blwavg:[', but shoots midrange at a below average percentage',', but converts midrange shots at a below average rate'],
          poor:[', but shoots midrange at a poor percentage',', but struggles from midrange'],
          verypoor:[', but shoots midrange at a very poor percentage',', but has very poor midrange conversion']
        }
      };
      const pool=phrases[shot];
      if(!pool)return '';
      const arr=pool[t];
      if(!arr||!arr.length)return '';
      const pick=arr.find(p=>!usedOffPhrases.includes(p))||arr[0];
      usedOffPhrases.push(pick);
      // Low rate + positive FG%: "but" not "and" — avoiding a shot then finishing well is a contrast
      if(!isNaN(ratePct)&&ratePct<=0.35&&isPos(t)&&pick.startsWith(' and ')){
        return pick.replace(/^ and /,' but ');
      }
      return pick;
    }

    // ── AVOIDED SHOT PHRASE ──────────────────────────────────────────────────
    function avoPhrase(pct,shot){
      const label={threes:'three-point attempts',rim:'rim attempts',mid:'midrange attempts'}[shot];
      if(pct<=0.15)return 'rarely taking '+label;
      if(pct<=0.25)return 'infrequently taking '+label;
      return 'tending to avoid '+label;
    }

    // ── BUILD DEF CLAUSE ─────────────────────────────────────────────────────
    function defRatePhrase(pct,label){
      if(pct>=0.85)return 'allow a very high volume of '+label;
      if(pct>=0.75)return 'frequently allow '+label;
      if(pct>=0.65)return 'tend to allow '+label;
      if(pct<=0.15)return 'rarely allow '+label;
      if(pct<=0.25)return 'infrequently allow '+label;
      return 'tend to limit '+label;
    }
    function buildDefClause(shot,ratePct,fgPct,usedWhile){
      const label={rim:'rim attacks',threes:'three-point attempts',mid:'midrange attempts'}[shot];
      const rPhrase=defRatePhrase(ratePct,label);
      const t=fgTier(fgPct);
      const fgQ=defFGQuality(shot,fgPct);
      const highRate=ratePct>=0.65;
      const lowRate=ratePct<=0.35;
      const conn=usedWhile?'and':'while';
      if(t==='neutral'){
        if(highRate){
          const nL={rim:'an average FG% at the rim',threes:'an average three-point percentage',mid:'an average midrange percentage'}[shot];
          return{clause:rPhrase+' while allowing '+nL,usedWhile:true};
        }
        return{clause:rPhrase,usedWhile};
      }
      if(!fgQ)return{clause:rPhrase,usedWhile};
      if(highRate&&isNeg(t)){const v=defNegVerb();return{clause:rPhrase+' while '+v+'ing '+fgQ,usedWhile:true};}
      if(highRate&&isPos(t)){const v=defPosVerb();return{clause:rPhrase+' but '+v+' '+fgQ,usedWhile};}
      if(lowRate&&isPos(t)){const v=defPosVerb();return{clause:rPhrase+' and '+v+' '+fgQ,usedWhile};}
      if(lowRate&&isNeg(t)){return{clause:rPhrase+', though they have '+fgQ+' when challenged',usedWhile:false};}
      const v=defNegVerb();return{clause:rPhrase+' while '+v+'ing '+fgQ,usedWhile:true};
    }

    // ── FALLBACKS ────────────────────────────────────────────────────────────
    function efgOffDesc(pct){
      const t=fgTier(pct);
      const m={elite:'elite',strong:'strong',abvavg:'above average',blwavg:'below average',poor:'poor',verypoor:'very poor'};
      return 'takes a balanced offensive approach with '+(m[t]||'average')+' overall shooting efficiency';
    }
    function efgDefDesc(pct){
      const t=fgTier(pct);
      if(t==='elite')return 'they defend without a clear tendency, limiting opponents to elite overall shooting efficiency';
      if(t==='strong')return 'they defend without a clear tendency, holding opponents to strong overall shooting efficiency';
      if(t==='abvavg')return 'they defend without a clear tendency, allowing above average overall shooting efficiency';
      if(t==='blwavg')return 'they defend without a clear tendency, allowing below average overall shooting efficiency';
      if(t==='poor')return 'they defend without a clear tendency, allowing poor overall shooting efficiency';
      if(t==='verypoor')return 'they defend without a clear tendency, giving up very poor overall shooting efficiency';
      return 'they defend without a clear tendency, allowing average overall shooting efficiency';
    }

    // ════════════════════════════════════════════════════════════════════════
    // OFFENSE
    // ════════════════════════════════════════════════════════════════════════
    const offRMap={rim:offRimR,threes:offThreeR,mid:offMidR};
    const offFGMap={rim:fgRim,threes:fg3,mid:fgMid};
    const offRanked=rankShots(offRMap,offFGMap);
    const offPrimary=offRanked[0];
    const offPrimRate=offRMap[offPrimary];
    const offPrimFG=offFGMap[offPrimary];
    const offPrimRateNotable=offPrimRate>=0.65||offPrimRate<=0.35;

    // Mid leads only if highest raw rate AND rim/three both not notable
    const rawMax=Math.max(offRimRaw,offThreeRaw,offMidRaw);
    const rimOrThreeNotable=offRimR>=0.65||offRimR<=0.35||offThreeR>=0.65||offThreeR<=0.35;
    const midCanLead=offPrimary==='mid'&&offMidRaw===rawMax&&!rimOrThreeNotable;

    let offDesc='';
    let offMentioned=new Set(); // tracks which shots mentioned

    // ── STEP 1: Primary rate + inline FG% ───────────────────────────────────
    if(offPrimRateNotable&&(offPrimary!=='mid'||midCanLead)){
      offMentioned.add(offPrimary);
      if(offPrimary==='threes'){
        if(offPrimRate>=0.85)offDesc='very frequently attacks the three-point line';
        else if(offPrimRate>=0.75)offDesc='frequently attacks the three-point line';
        else if(offPrimRate>=0.65)offDesc='favors shooting from three';
        else if(offPrimRate<=0.15)offDesc='rarely takes three-point attempts';
        else if(offPrimRate<=0.25)offDesc='infrequently shoots from three';
        else offDesc='tends to avoid three-point attempts';
      } else if(offPrimary==='rim'){
        if(offPrimRate>=0.85)offDesc='very frequently attacks the rim';
        else if(offPrimRate>=0.75)offDesc='frequently attacks the rim';
        else if(offPrimRate>=0.65)offDesc='favors attacking the rim';
        else if(offPrimRate<=0.15)offDesc='rarely attacks the rim';
        else if(offPrimRate<=0.25)offDesc='infrequently attacks the rim';
        else offDesc='tends to avoid rim attempts';
      } else {
        if(offPrimRate>=0.75)offDesc='frequently looks to the midrange';
        else offDesc='favors the midrange';
      }
      offDesc+=offFGMod(offPrimary,offPrimFG,offPrimRate);

      // ── STEP 2: Secondary rate + inline FG% ─────────────────────────────
      const offSec=offRanked[1];
      const offSecRate=offRMap[offSec];
      const offSecFG=offFGMap[offSec];
      const offSecRateNotable=offSecRate>=0.65||offSecRate<=0.35;
      // Mid secondary: only if rate >=65th (they actually shoot a lot)
      const midSecOK=offSec!=='mid'||(offSecRate>=0.65);
      if(offSecRateNotable&&midSecOK){
        offMentioned.add(offSec);
        if(offSecRate<=0.35){
          // Avoided shot — "while rarely taking X, but finishes well when they do"
          const ft=fgTier(offSecFG);
          const avoPhr=avoPhrase(offSecRate,offSec);
          if(isPos(ft)){
            const locLbl={threes:'from deep',rim:'at the rim',mid:'from midrange'}[offSec];
            const posLbl={elite:'an elite',strong:'a strong',abvavg:'an above average'}[ft]||'';
            offDesc+=' while '+avoPhr+(posLbl?', but finishes at '+posLbl+' percentage '+locLbl+' when they do':'');
          } else if(isNeg(ft)){
            const secMod=offFGMod(offSec,offSecFG,offSecRate);
            offDesc+=' while '+avoPhr+(secMod?secMod:'');
          } else {
            offDesc+=' while '+avoPhr;
          }
        } else {
          // High secondary rate — gerund form
          const secVerb={
            threes:offSecRate>=0.85?'also very frequently attacking the three-point line':offSecRate>=0.75?'also frequently attacking the three-point line':'also favoring shooting from three',
            rim:offSecRate>=0.85?'also very frequently attacking the rim':offSecRate>=0.75?'also frequently attacking the rim':'also favoring attacking the rim',
            mid:offSecRate>=0.75?'also frequently looking to the midrange':'also favoring the midrange'
          }[offSec];
          const secMod=offFGMod(offSec,offSecFG,offSecRate);
          const secModG=secMod.replace(' and converts',' and converting').replace(' and shoots',' and shooting').replace(' and knocks',' and knocking').replace(' and finishes',' and finishing').replace(' and is',' and being').replace(', but converts',', but converting').replace(', but shoots',', but shooting').replace(', but struggles',', but struggling').replace(', though they convert at an average clip from deep',', converting at an average clip from deep').replace(', though they shoot at an average percentage from deep',', shooting at an average percentage from deep').replace(', though they shoot midrange at an average percentage',', shooting midrange at an average percentage').replace(', though they convert',', converting at an average clip').replace(', though they shoot',', shooting at an average clip').replace(', though they finish at an average percentage',', finishing at an average percentage').replace(', though they convert at an average rate at the rim',', converting at an average rate at the rim').replace(', though they finish',', finishing at an average clip');
          offDesc+=' while '+secVerb+secModG;
        }
      }
    } else {
      // Fallback — balanced eFG% description
      offDesc=efgOffDesc(efgOff);
    }

    // ── STEP 3: Standalone FG% sentence ─────────────────────────────────────
    // Collect rim, three, mid FG% callouts not already mentioned
    // Thresholds: D1=80/20, conf/sub=75/25
    const offStans=[];
    if(!offMentioned.has('threes')){
      const t3=fgTier(fg3);
      if(fg3>=stHi)offStans.push({dir:'pos',phrase:'shoot at '+(t3==='elite'?'an elite':'a strong')+' percentage from deep'});
      else if(fg3<=stLo)offStans.push({dir:'neg',phrase:t3==='verypoor'?'shoot a very poor percentage from deep':'struggle to knock them down from deep'});
    }
    if(!offMentioned.has('rim')){
      const tr=fgTier(fgRim);
      if(fgRim>=stHi)offStans.push({dir:'pos',phrase:'finish at '+(tr==='elite'?'an elite':'a strong')+' percentage at the rim'});
      else if(fgRim<=stLo)offStans.push({dir:'neg',phrase:tr==='verypoor'?'struggle significantly to finish at the rim':'struggle to finish at the rim'});
    }
    if(!offMentioned.has('mid')){
      // Mid standalone: FG% >=80/20 AND rate >=35th
      // When mid rate is very high (>=90th), always mention it — it's a genuine identity
      // When mid rate is high (>=85th), lower FG% threshold
      const tm=fgTier(fgMid);
      const midFGHi=offMidR>=0.85?0.70:stHi;
      const midFGLo=offMidR>=0.85?0.30:stLo;
      if(offMidR>=0.90){
        // Very extreme mid rate — mention rate regardless of FG%
        const midRateDesc='rely heavily on midrange attempts';
        if(fgMid>=midFGHi)offStans.push({dir:'pos',phrase:midRateDesc+', converting at '+(tm==='elite'?'an elite':'a strong')+' percentage'});
        else if(fgMid<=midFGLo)offStans.push({dir:'neg',phrase:midRateDesc+', though they '+( tm==='verypoor'?'have very poor midrange conversion':'struggle to convert them')});
        else offStans.push({dir:'neu',phrase:midRateDesc});
      } else if((fgMid>=midFGHi||fgMid<=midFGLo)&&offMidR>=0.35){
        if(fgMid>=midFGHi)offStans.push({dir:'pos',phrase:'convert midrange shots at '+(tm==='elite'?'an elite':'a strong')+' percentage'});
        else offStans.push({dir:'neg',phrase:tm==='verypoor'?'have very poor midrange conversion':'struggle with midrange conversion'});
      }
    }
    if(offStans.length>0){
      const posI=offStans.filter(s=>s.dir==='pos'||s.dir==='neu').map(s=>s.phrase);
      const negI=offStans.filter(s=>s.dir==='neg').map(s=>s.phrase);
      const ep=offDesc.trim().endsWith('.');
      const join=items=>items.length===1?items[0]:items.length===2?items[0]+' and '+items[1]:items.slice(0,-1).join(', ')+', and '+items[items.length-1];
      let stanResult='';
      if(posI.length>0&&negI.length===0){
        stanResult=(ep?' They ':'; they ')+join(posI)+'.';
      } else if(negI.length>0&&posI.length===0){
        stanResult=(ep?' However, they ':'; however, they ')+join(negI)+'.';
      } else {
        // Mixed — lead with direction matching overall efficiency
        const offIsPos=offDesc.toLowerCase().includes('elite')||offDesc.toLowerCase().includes('strong')||offDesc.toLowerCase().includes('above average');
        if(offIsPos){
          stanResult=(ep?' They ':'; they ')+join(posI)+'. However, they '+join(negI)+'.';
        } else {
          stanResult=(ep?' They ':'; they ')+join(negI)+'. However, they '+join(posI)+'.';
        }
      }
      offDesc+=stanResult;
    }

    // Dunk callout
    if(!isNaN(offDunkR)&&!isNaN(offDunkFG)&&offDunkR>=0.85&&offDunkFG>=0.85)
      offDesc+=offDesc.trim().endsWith('.')?'':'';//skip — covered by rim story

    // ════════════════════════════════════════════════════════════════════════
    // DEFENSE
    // ════════════════════════════════════════════════════════════════════════
    const defRMap={rim:defRimR,threes:defThreeR,mid:defMidR};
    const defFGMap={rim:dfgRim,threes:dfg3,mid:dfgMid};
    const defRanked=rankShots(defRMap,defFGMap);
    const defMentioned=new Set();

    // Mid can lead/appear in defense only with high rate
    function midDefCanAppear(asPrimary){
      if(asPrimary){
        // Mid can only lead if rate is HIGH (>=65th) AND scores highest
        // Low mid rate (<=20th) with great FG% is a standalone story, not a lead
        if(defRMap.mid<0.65)return false;
        const rs=shotScore(defRimR,dfgRim,'rim'),ts=shotScore(defThreeR,dfg3,'threes'),ms=shotScore(defMidR,dfgMid,'mid');
        return ms>rs&&ms>ts;
      }
      // Secondary: mid force condition — high rate with rim+three both limited
      return defRMap.mid>=0.65&&defRimR<=0.60&&defThreeR<=0.60;
    }

    let defDesc='';

    // ── STEP 0: PATTERN DETECTION ────────────────────────────────────────────
    // Always uses D1 percentiles for pattern triggers
    const chaseArc=defThreeR<=0.20&&defMidR>=0.65&&defRimR>=0.65;
    const packPaint=defRimR<=0.20&&defMidR>=0.65&&defThreeR>=0.65;

    if(chaseArc||packPaint){
      defMentioned.add('threes');defMentioned.add('rim');defMentioned.add('mid');
      const suppShot=chaseArc?'threes':'rim';
      const suppFG=chaseArc?dfg3:dfgRim;
      const suppFGT=fgTier(suppFG);
      const suppFGQ=defFGQuality(suppShot,suppFG);
      const forcedDir=chaseArc?'forcing opponents toward the rim and midrange':'pushing opponents to the perimeter and midrange';
      const forcedShots=chaseArc?['rim','mid']:['threes','mid'];

      // Sentence 1: intro + suppressed FG% + forcing direction
      let patternS1='';
      if(chaseArc){
        patternS1=defThreeR<=0.10?'chase opponents off the three-point line':'limit opponent three-point attempts';
      } else {
        patternS1=defRimR<=0.10?'pack the paint, limiting rim attacks to a very low rate':'limit opponent rim attacks';
      }

      if(suppFGT==='neutral'){
        // Neutral suppressed FG% — just add forcing direction
        patternS1+=', '+forcedDir;
        defDesc=patternS1;
      } else if(isPos(suppFGT)){
        // Good suppressed FG% — inline, then forcing direction
        patternS1+=' while maintaining '+suppFGQ+', '+forcedDir;
        defDesc=patternS1;
      } else {
        // Bad suppressed FG% — split into 2 sentences
        // Sentence 1: scheme + vulnerability
        if(chaseArc)patternS1+=' though they have '+suppFGQ;
        else{
          // Pack paint with bad rim FG%
          patternS1=defRimR<=0.10?'pack the paint but are vulnerable when teams do get inside':'limit opponent rim attacks but are vulnerable when teams do get inside';
        }
        defDesc=patternS1+'. ';
        // Sentence 2: forcing direction + forced shot FG%
        let s2='They force opponents '+(chaseArc?'toward the rim and midrange':'to the perimeter and midrange');
        const forcedQuals=[];
        for(const fs of forcedShots){
          const fgQ=defFGQuality(fs,defFGMap[fs]);
          const fgT=fgTier(defFGMap[fs]);
          if(fgT==='neutral')continue;
          if(isPos(fgT))forcedQuals.push({dir:'pos',q:fgQ,verb:defPosVerb()});
          else forcedQuals.push({dir:'neg',q:fgQ});
        }
        if(forcedQuals.length>0){
          const posQ=forcedQuals.filter(f=>f.dir==='pos');
          const negQ=forcedQuals.filter(f=>f.dir==='neg');
          if(posQ.length>0&&negQ.length===0){
            s2+=' where they '+posQ.map((f,i)=>i===0?f.verb+' '+f.q:(defPosVerb()+' '+f.q)).join(' and ');
          } else if(negQ.length>0&&posQ.length===0){
            s2+='. However, they have '+negQ.map(f=>f.q).join(' and ');
          } else {
            s2+=' where they '+posQ.map((f,i)=>i===0?f.verb+' '+f.q:(defPosVerb()+' '+f.q)).join(' and ');
            s2+='. However, they have '+negQ.map(f=>f.q).join(' and ');
          }
        }
        defDesc+=s2+'.';
      }

      // For neutral/positive suppressed — add sentence 2 for forced shot FG% if notable
      if(!defDesc.includes('. ')){
        const forcedQuals=[];
        for(const fs of forcedShots){
          const fgQ=defFGQuality(fs,defFGMap[fs]);
          const fgT=fgTier(defFGMap[fs]);
          if(fgT==='neutral')continue;
          if(isPos(fgT))forcedQuals.push({dir:'pos',q:fgQ});
          else forcedQuals.push({dir:'neg',q:fgQ});
        }
        if(forcedQuals.length>0){
          const posQ=forcedQuals.filter(f=>f.dir==='pos');
          const negQ=forcedQuals.filter(f=>f.dir==='neg');
          // Ensure sentence 1 ends with period before sentence 2
          if(!defDesc.trim().endsWith('.'))defDesc+='.';
          let s2='';
          if(posQ.length>0&&negQ.length===0){
            s2=' They '+posQ.map((f,i)=>i===0?defPosVerb()+' '+f.q:defPosVerb()+' '+f.q).join(' and ')+'.';
          } else if(negQ.length>0&&posQ.length===0){
            s2=' However, they have '+negQ.map(f=>f.q).join(' and ')+'.';
          } else {
            s2=' They '+posQ.map((f,i)=>i===0?defPosVerb()+' '+f.q:defPosVerb()+' '+f.q).join(' and ')+'. However, they have '+negQ.map(f=>f.q).join(' and ')+'.';
          }
          defDesc+=s2;
        }
      }

    } else {
      // ── STEPS 1+2: Normal priority ────────────────────────────────────────
      // Primary must have non-neutral rate (not 35-65th)
      // Neutral rate shots are FG%-only stories that belong in standalone
      let defPrimaryIdx=defRanked[0]==='mid'&&!midDefCanAppear(true)?1:0;
      while(defPrimaryIdx<defRanked.length){
        const candidate=defRanked[defPrimaryIdx];
        const cRate=defRMap[candidate];
        // Skip if rate is neutral (35-65th) — FG% alone doesn't anchor a primary
        if(cRate<0.35||cRate>0.65)break;
        defPrimaryIdx++;
      }
      const defPrimary=defPrimaryIdx<defRanked.length?defRanked[defPrimaryIdx]:defRanked[0];
      const defPrimRate=defRMap[defPrimary];
      const defPrimFG=defFGMap[defPrimary];
      const defPrimRateNotable=defPrimRate>=0.65||defPrimRate<=0.35;
      const defPrimFGNotable=fgTier(defPrimFG)!=='neutral';

      // Primary must have notable rate — FG%-only stories go to standalone
      if(defPrimRateNotable){
        defMentioned.add(defPrimary);
        const r=buildDefClause(defPrimary,defPrimRate,defPrimFG,false);
        defDesc=r.clause;
        const defUW=r.usedWhile;

        // Secondary
        const defSecOpts=defRanked.filter(s=>s!==defPrimary);
        let defSec=null;
        for(const s of defSecOpts){
          if(s==='mid'&&!midDefCanAppear(false))continue;
          const sR=defRMap[s],sFG=defFGMap[s];
          // Only fire as secondary if rate is notable — FG%-only stories go to standalone
          if(sR>=0.65||sR<=0.35){defSec=s;break;}
        }
        if(defSec){
          defMentioned.add(defSec);
          const secRate=defRMap[defSec],secFG=defFGMap[defSec];
          if(secRate>=0.65||secRate<=0.35){
            const r2=buildDefClause(defSec,secRate,secFG,defUW);
            defDesc+='; additionally, they '+r2.clause;
          } else {
            const fgQ=defFGQuality(defSec,secFG);
            if(fgQ)defDesc+='; additionally, they display '+fgQ;
          }
        }
      }

      // ── STEP 3: Standalone def FG% ──────────────────────────────────────
      const defStans=[];
      for(const s of['threes','rim','mid']){
        if(defMentioned.has(s))continue;
        const fg=defFGMap[s];
        const rate=defRMap[s];
        // Mid standalone: only fire if rate is high (>=65th positive, >=55th negative)
        if(s==='mid'&&rate<0.65&&!(rate>=0.55&&fg<=stLo))continue;
        if(fg>=stHi){
          const fgQ=defFGQuality(s,fg);
          if(fgQ)defStans.push({dir:'pos',phrase:'display '+fgQ});
        } else if(fg<=stLo){
          const fgQ=defFGQuality(s,fg);
          if(fgQ)defStans.push({dir:'neg',phrase:'have '+fgQ});
        }
      }
      if(defStans.length>0){
        const posI=defStans.filter(s=>s.dir==='pos').map(s=>s.phrase);
        const negI=defStans.filter(s=>s.dir==='neg').map(s=>s.phrase);
        const ep=defDesc.trim().endsWith('.');
        const join=items=>items.length===1?items[0]:items.length===2?items[0]+' and '+items[1]:items.slice(0,-1).join(', ')+', and '+items[items.length-1];
        let stanResult='';
        if(posI.length>0&&negI.length===0){
          stanResult=(ep?' They ':(defDesc.includes('additionally')?'; beyond that, they ':'; additionally, they '))+join(posI)+'.';
        } else if(negI.length>0&&posI.length===0){
          stanResult=(ep?' However, they ':'; however, they ')+join(negI)+'.';
        } else {
          stanResult=(ep?' They ':'; additionally, they ')+join(posI)+'. However, they '+join(negI)+'.';
        }
        defDesc+=stanResult;
      }

      if(!defDesc)defDesc=efgDefDesc(efgDef);
    }

    // ── FINAL ASSEMBLY ───────────────────────────────────────────────────────
    const hasPeriod=offDesc.includes('.')||defDesc.includes('.');
    const defNeedsThey=!['opponents','force','funnel','limit','struggle','they','chase','rarely','infrequently','tend','frequently','allow'].some(w=>defDesc.startsWith(w));
    const defClause=defNeedsThey?'they '+defDesc:defDesc;
    blurb=hasPeriod?
      nm+' '+offDesc+'. Defensively, '+defClause+'.':
      nm+' '+offDesc+'; defensively, '+defClause+'.';
    // Clean up double periods
    blurb=blurb.replace(/\.\.+/g,'.').replace(/\. \./g,'.').replace(/\.\./g,'.');
  }
  window._shotBlurb=blurb;
}

function updateSubLabels(row){
  if(!row)return;
  const lbl=isPower(row)?'vs. Power Conf':'vs. Mid Major';
  document.getElementById('sub-view-btn').textContent=lbl;
  document.getElementById('hist-sub-btn').textContent=lbl;
}

function updatePageDesc(){
  const el=document.getElementById('page-desc');
  if(!cTeam||!cYear){el.textContent='Select a team and season to begin.';return;}
  const conf=cRow?cRow.conference:'';
  el.textContent=PAGE_DESCS[cTab]?PAGE_DESCS[cTab](cTeam,cYear,conf):'';
}

function renderTab(){
  if(cTab==='profile')renderProfile();
  else if(cTab==='conference')renderConference();
  else if(cTab==='historical'){initHistSelectors();renderHistorical();}
}

// ── PROFILE ───────────────────────────────────────────────────────────────────
function setView(v,btn){
  cView=v;document.querySelectorAll('.view-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');
  updateURL();
  if(cRow){recalcBlurb(cRow,v);renderProfile();}
}

function getPct(row,key,view){
  if(view==='conf'){const v=parseFloat(row[key+'_conf_pct']);return isNaN(v)?null:v;}
  if(view==='sub'){const v=parseFloat(row[key+'_sub_pct']);return isNaN(v)?null:v;}
  const v=parseFloat(row[key+'_pct']);return isNaN(v)?null:v;
}

function pctCls(pct,isTempo,isFreq){
  if(pct===null||pct===undefined){
    return{color:'pct-avg',bar:'bar-avg',badge:'badge-avg',label:'N/A'};
  }
  if(isTempo){
    if(pct>=0.80)return{color:'pct-fast',bar:'bar-elite',badge:'badge-fast',label:'Very Fast'};
    if(pct>=0.60)return{color:'pct-faster',bar:'bar-good',badge:'badge-faster',label:'Faster'};
    if(pct>=0.40)return{color:'pct-avgpace',bar:'bar-avg',badge:'badge-avgpace',label:'Avg Pace'};
    if(pct>=0.20)return{color:'pct-slower',bar:'bar-below',badge:'badge-slower',label:'Slower'};
    return{color:'pct-slow',bar:'bar-poor',badge:'badge-slow',label:'Very Slow'};
  }
  if(isFreq){
    if(pct>=0.80)return{color:'pct-fast',bar:'bar-elite',badge:'badge-hifreq',label:'Very High Freq'};
    if(pct>=0.60)return{color:'pct-faster',bar:'bar-good',badge:'badge-hifreq2',label:'Higher Freq'};
    if(pct>=0.40)return{color:'pct-avgpace',bar:'bar-avg',badge:'badge-avgfreq',label:'Avg Freq'};
    if(pct>=0.20)return{color:'pct-slower',bar:'bar-below',badge:'badge-lofreq2',label:'Lower Freq'};
    return{color:'pct-slow',bar:'bar-poor',badge:'badge-lofreq',label:'Very Low Freq'};
  }
  if(pct>=0.85)return{color:'pct-elite',bar:'bar-elite',badge:'badge-elite',label:'Elite'};
  if(pct>=0.65)return{color:'pct-good',bar:'bar-good',badge:'badge-good',label:'Above Avg'};
  if(pct>=0.40)return{color:'pct-avg',bar:'bar-avg',badge:'badge-avg',label:'Average'};
  if(pct>=0.20)return{color:'pct-below',bar:'bar-below',badge:'badge-below',label:'Below Avg'};
  return{color:'pct-poor',bar:'bar-poor',badge:'badge-poor',label:'Poor'};
}

function tip(key){
  const t=TIPS[key];
  const customKeys=["ppp_diff","xPPP_diff","residual_diff","ppp_off_full","xPPP_off","ppp_residual_off","ppp_def_full","xPPP_def","ppp_residual_def"];
  const scrapedKeys=["off_rim_rate_total","off_rim_fg","def_rim_rate_total","def_rim_fg","off_dunks_rate_total","off_dunks_fg","def_dunks_rate_total","def_dunks_fg","off_close_twos_rate_total","off_close_twos_fg","def_close_twos_rate_total","def_close_twos_fg","off_long_twos_rate_total","off_long_twos_fg","def_long_twos_rate_total","def_long_twos_fg","off_threes_rate_total","off_threes_fg","def_threes_rate_total","def_threes_fg"];
  const badge=customKeys.includes(key)?'<span class="custom-badge">Custom</span>':scrapedKeys.includes(key)?'<span class="scraped-badge">Engineered</span>':'';
  if(!t)return badge;
  return `<span class="info-icon" onclick="toggleTip(event,this)">i<span class="tooltip">${t}</span></span>`+badge;
}
function toggleTip(e,el){
  e.stopPropagation();
  const tip=el.querySelector('.tooltip');
  const wasOpen=tip.style.display==='block';
  document.querySelectorAll('.tooltip').forEach(t=>t.style.display='none');
  tip.style.display=wasOpen?'none':'block';
}
document.addEventListener('click',e=>{
  if(!e.target.closest('.info-icon'))document.querySelectorAll('.tooltip').forEach(t=>t.style.display='');
});

function statRowHtml(row,stat,view){
  const pct=getPct(row,stat.key,view);
  const cls=pctCls(pct,stat.isTempo,false);
  const bw=pct!==null?Math.round(pct*100):0;
  const dp=pct!==null?Math.round(pct*100)+'%':'—';
  const rawV=parseFloat(row[stat.key]);
  const fv=!isNaN(rawV)?stat.fmt(rawV):'—';
  const rd=view==='conf'?`Conf #${row[stat.key+'_conf_rank']||'—'}`:view==='sub'?`Sub #${row[stat.key+'_sub_rank']||'—'}`:`#${row[stat.key+'_rank']||'—'}`;
  // Conference rank view — show bar + percentile + rank + descriptor
  if(view==='conf'){
    const confRank=row[stat.key+'_conf_rank'];
    const confPctRaw=parseFloat(row[stat.key+'_conf_pct']);
    const confPct=isNaN(confPctRaw)?null:confPctRaw;
    const confCls=pctCls(confPct,stat.isTempo,false);
    const confBw=confPct!==null?Math.round(confPct*100):0;
    const confDp=confPct!==null?Math.round(confPct*100)+'%':'—';
    return`<div class="stat-row">
      <div class="stat-name">${stat.label}${tip(stat.key)}</div>
      <div class="stat-val">${fv}</div>
      <div class="stat-bar-wrap"><div class="stat-bar ${confCls.bar}" style="width:${confBw}%"></div></div>
      <div class="stat-pct-val ${confCls.color}">${confDp}</div>
      <div class="stat-rank-val">Conf #${confRank||'—'}</div>
      <div class="descriptor-badge ${confCls.badge}">${confCls.label}</div>
    </div>`;
  }
  // Sub view: show sub rank
  if(view==='sub'){
    const subRank=row[stat.key+'_sub_rank'];
    const subPct=parseFloat(row[stat.key+'_sub_pct']);
    const subCls=pctCls(isNaN(subPct)?null:subPct,stat.isTempo,false);
    const bwS=!isNaN(subPct)?Math.round(subPct*100):0;
    const dpS=!isNaN(subPct)?Math.round(subPct*100)+'%':'—';
    return`<div class="stat-row">
      <div class="stat-name">${stat.label}${tip(stat.key)}</div>
      <div class="stat-val">${fv}</div>
      <div class="stat-bar-wrap"><div class="stat-bar ${subCls.bar}" style="width:${bwS}%"></div></div>
      <div class="stat-pct-val ${subCls.color}">${dpS}</div>
      <div class="stat-rank-val">Sub #${subRank||'—'}</div>
      <div class="descriptor-badge ${subCls.badge}">${subCls.label}</div>
    </div>`;
  }
  return`<div class="stat-row">
    <div class="stat-name">${stat.label}${tip(stat.key)}</div>
    <div class="stat-val">${fv}</div>
    <div class="stat-bar-wrap"><div class="stat-bar ${cls.bar}" style="width:${bw}%"></div></div>
    <div class="stat-pct-val ${cls.color}">${dp}</div>
    <div class="stat-rank-val">${rd}</div>
    <div class="descriptor-badge ${cls.badge}">${cls.label}</div>
  </div>`;
}

function shotMetricCell(row,key,isFreq,view){
  if(!row||!key)return'<div class="shot-metric-cell"><span class="shot-val">—</span></div>';
  const rawV=parseFloat(row[key]);
  const fv=!isNaN(rawV)?(rawV<1?(rawV*100).toFixed(1)+'%':rawV.toFixed(1)):'—';
  let pct;
  if(view==='conf'){const v=parseFloat(row[key+'_conf_pct']);pct=isNaN(v)?null:v;}
  else if(view==='sub'){const v=parseFloat(row[key+'_sub_pct']);pct=isNaN(v)?null:v;}
  else{const v=parseFloat(row[key+'_pct']);pct=isNaN(v)?null:v;}
  const cls=pctCls(pct,false,isFreq);
  const bw=pct!==null?Math.round(pct*100):0;
  const rd=view==='conf'?`Conf #${row[key+'_conf_rank']||'—'}`:view==='sub'?`Sub #${row[key+'_sub_rank']||'—'}`:`#${row[key+'_rank']||'—'}`;
  // Conference rank view — show bar + percentile + rank + descriptor
  if(view==='conf'){
    const confR=row[key+'_conf_rank'];
    const confPctRaw2=parseFloat(row[key+'_conf_pct']);
    const confPct2=isNaN(confPctRaw2)?null:confPctRaw2;
    const confCls=pctCls(confPct2,false,isFreq);
    const confBw2=confPct2!==null?Math.round(confPct2*100):0;
    return`<div class="shot-metric-cell">
      <span class="shot-val">${fv}</span>
      <div class="shot-bar-wrap"><div class="shot-bar ${confCls.bar}" style="width:${confBw2}%"></div></div>
      <span class="shot-pct ${confCls.color}">${confPct2!==null?Math.round(confPct2*100)+'%':'—'}</span>
      <span class="shot-rank">Conf #${confR||'—'}</span>
      <span class="shot-badge ${confCls.badge}">${confCls.label}</span>
    </div>`;
  }
  return`<div class="shot-metric-cell">
    <span class="shot-val">${fv}</span>
    <div class="shot-bar-wrap"><div class="shot-bar ${cls.bar}" style="width:${bw}%"></div></div>
    <span class="shot-pct ${cls.color}">${pct!==null?Math.round(pct*100)+'%':'—'}</span>
    <span class="shot-rank">${rd}</span>
    <span class="shot-badge ${cls.badge}">${cls.label}</span>
  </div>`;
}

function renderShotProfile(row,view){
  let html=`<div class="shot-grid">
    <div class="shot-header-cell cat-h">Shot Type</div>
    <div class="shot-header-cell">Rate (Freq)</div>
    <div class="shot-header-cell">FG%</div>
    <div class="shot-header-cell">Rate Allowed</div>
    <div class="shot-header-cell">FG% Allowed</div>`;
  SHOT_CATS.forEach(c=>{
    const isExp=expandedShotRows.has(c.name);
    const arrowChar=isExp?'▼':'►';
    const arrow=c.expandable?('<span class="shot-expand-arrow" data-cat="'+c.name+'" onclick="toggleShotRowByName(this)" style="cursor:pointer;margin-left:8px;font-size:13px;color:var(--accent);user-select:none;vertical-align:middle">'+arrowChar+'</span>'):'';
    const fw=c.expandable?'600':'500';
    const shotTip=tip(c.rk);
    html+=`<div class="shot-cat-cell" style="font-weight:${fw};flex-direction:column;align-items:flex-start">${c.name}${shotTip}${arrow}</div>
      ${shotMetricCell(row,c.rk,true,view)}
      ${shotMetricCell(row,c.fk,false,view)}
      ${shotMetricCell(row,c.drk,true,view)}
      ${shotMetricCell(row,c.dfk,false,view)}`;
    if(c.expandable&&isExp&&c.children){
      c.children.forEach(ch=>{
        const childTip=tip(ch.rk);
        html+=`<div class="shot-cat-cell" style="padding-left:28px;font-size:13px;color:var(--text3)">${ch.name}${childTip}</div>
          ${shotMetricCell(row,ch.rk,true,view)}
          ${shotMetricCell(row,ch.fk,false,view)}
          ${shotMetricCell(row,ch.drk,true,view)}
          ${shotMetricCell(row,ch.dfk,false,view)}`;
      });
    }
  });
  html+='</div>';
  return html;
}
function toggleShotRow(name,el){
  if(expandedShotRows.has(name))expandedShotRows.delete(name);
  else expandedShotRows.add(name);
  if(cRow)renderProfile();
}
function setTrendWindow(n,btn){
  cTrendWindow=n;
  document.querySelectorAll('.hist-btn-row .hist-comp-btn').forEach(b=>{
    if(b.textContent.includes('yr'))b.classList.remove('active');
  });
  btn.classList.add('active');
  renderHistorical();
}
function setH2HCat(cat,btn){
  cH2HCat=cat;
  document.querySelectorAll('#h2h-cat-filter .hist-cat-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  renderH2H();
}
function setConfCat(cat,btn){
  cConfCat=cat;
  document.querySelectorAll('#conf-cat-filter .hist-cat-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  renderConfStats();
}
function toggleShotRowByName(el){
  const name=el.getAttribute('data-cat');
  toggleShotRow(name,el);
}

function renderProfile(){
  document.getElementById('profile-loading').style.display='none';
  document.getElementById('profile-empty').style.display='none';
  document.getElementById('profile-content').style.display='block';
  updatePageDesc();
  const grid=document.getElementById('profile-grid');grid.innerHTML='';
  Object.entries(STAT_CATS).forEach(([cat,stats])=>{
    const card=document.createElement('div');card.className='stat-card';
    card.innerHTML=`<div class="stat-card-title">${cat}</div>`;
    stats.forEach(s=>{card.innerHTML+=statRowHtml(cRow,s,cView);});
    grid.appendChild(card);
  });
  // Shot profile full width
  const sp=document.createElement('div');sp.className='stat-card shot-profile-wrap';
  try{
    const blurbText=window._shotBlurb||'';
    const contextLabel=cView==='conf'?('vs. '+cRow.conference):cView==='sub'?(isPower(cRow)?'vs. Power Conf':'vs. Mid Major'):'vs. All D1';
    const blurbHtml=blurbText?`<div class="shot-blurb-wrap"><div class="shot-blurb-text">${blurbText}</div></div>`:'';
    sp.innerHTML=`<div class="stat-card-title" style="display:flex;align-items:center;gap:8px">Shot Profile Summary<span class="shot-blurb-context">${contextLabel}</span></div>${blurbHtml}${renderShotProfile(cRow,cView)}`;
  }catch(e){
    sp.innerHTML=`<div class="stat-card-title">Shot Profile — Offense & Defense</div><div style="padding:20px;color:var(--text4);font-size:12px">Shot profile error: ${e.message}</div>`;
    console.error('Shot profile error:',e);
  }
  grid.appendChild(sp);
}

// ── CONFERENCE ────────────────────────────────────────────────────────────────
function setTopN(n,btn){
  cTopN=n;cCustomMode=false;cCompTeams=[];
  document.querySelectorAll('.top-n-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');
  renderConfStats();
}

function renderConference(){
  if(!cRow||!cYearData)return;
  document.getElementById('conference-content').style.display='block';
  updatePageDesc();
  const conf=cRow.conference,year=cRow.year;
  document.getElementById('conf-standings-label').textContent=`${conf} — ${yLabel(year)}`;
  const ct=cYearData.filter(d=>d.conference===conf).sort((a,b)=>parseFloat(b.adj_em)-parseFloat(a.adj_em));
  const tbody=document.getElementById('conf-standings-body');tbody.innerHTML='';
  ct.forEach((t,i)=>{
    const em=parseFloat(t.adj_em),isMe=t.team_name===cRow.team_name;
    const isComp=cCompTeams.includes(t.team_name);
    const tr=document.createElement('tr');
    tr.className=isMe?'highlighted':isComp?'selected-compare':'';
    tr.innerHTML=`<td style="font-family:var(--font-mono);font-size:10px;color:var(--text4)">${i+1}</td>
      <td><div style="display:flex;align-items:center;gap:6px">
        <img src="${TDIR}${sf(t.team_name)}.png" style="width:16px;height:16px;object-fit:contain" onerror="this.style.display='none'"/>
        <span style="font-size:12px;color:${isMe?'var(--accent)':isComp?'var(--yellow)':'var(--text2)'}">${t.team_name}</span>
        ${isComp?'<span style="font-size:9px;color:var(--yellow);margin-left:auto">✓</span>':''}
      </div></td>
      <td style="font-family:var(--font-mono);font-size:11px;color:${em>0?'var(--green)':'var(--red)'}">${em>0?'+':''}${em.toFixed(1)}</td>
      <td style="font-size:11px;color:var(--text3)">${t.full_season_record}</td>`;
    tr.onclick=()=>{
      if(t.team_name===cRow.team_name)return;
      cCustomMode=true;
      const idx=cCompTeams.indexOf(t.team_name);
      if(idx>=0)cCompTeams.splice(idx,1);
      else cCompTeams.push(t.team_name);
      if(cCompTeams.length===0)cCustomMode=false;
      // Deactivate top N buttons when in custom mode
      document.querySelectorAll('.top-n-btn').forEach(b=>b.classList.toggle('active',!cCustomMode&&parseInt(b.textContent)==cTopN||(b.textContent==='All'&&cTopN===0)));
      renderConference();
    };
    tbody.appendChild(tr);
  });
  renderConfStats();
}

function renderConfStats(){
  if(!cRow||!cYearData)return;
  const conf=cRow.conference;
  const ct=cYearData.filter(d=>d.conference===conf).sort((a,b)=>parseFloat(b.adj_em)-parseFloat(a.adj_em));

  // Determine compare teams
  let compareTeams=[];
  if(cCustomMode&&cCompTeams.length>0){
    compareTeams=cCompTeams.map(n=>cYearData.find(d=>d.team_name===n)).filter(Boolean);
  } else if(cTopN>0){
    compareTeams=ct.filter(t=>t.team_name!==cRow.team_name).slice(0,cTopN);
  }
  // cTopN===0 and no custom = All mode = just show conf avg, no compare columns

  // Title
  const titleEl=document.getElementById('conf-detail-title');
  if(cCustomMode&&cCompTeams.length>0){
    titleEl.textContent=`${cRow.team_name} vs. ${cCompTeams.join(', ')} (Custom)`;
  } else if(cTopN===0){
    titleEl.textContent=`${cRow.team_name} vs. Conference Average`;
  } else {
    titleEl.textContent=`${cRow.team_name} vs. Top ${cTopN} in ${cRow.conference}`;
  }

  const shotStats=SHOT_CATS.flatMap(c=>[
    {key:c.rk,label:`${c.name} Rate (Off)`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:true},
    {key:c.fk,label:`${c.name} FG% (Off)`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:false},
    {key:c.drk,label:`${c.name} Rate Allowed`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:true},
    {key:c.dfk,label:`${c.name} FG% Allowed`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:false},
  ]);
  const allStatsAll=[...Object.entries(STAT_CATS).flatMap(([cat,stats])=>stats.map(s=>({...s,cat}))), ...shotStats];
  const allStats=cConfCat==='All'?allStatsAll:allStatsAll.filter(s=>s.cat===cConfCat);

  // Avg source: compare teams if any, otherwise full conference
  const avgSource=compareTeams.length>0?compareTeams:cYearData.filter(d=>d.conference===conf);

  // Build header
  let thead=`<thead><tr>
    <th class="stat-col">Stat</th>
    <th style="color:var(--accent)">${cRow.team_name}</th>`;
  compareTeams.forEach(t=>{
    const col=cCustomMode?'var(--yellow)':'var(--text3)';
    thead+=`<th style="color:${col}">${t.team_name}</th>`;
  });
  const avgLabel=(cCustomMode&&cCompTeams.length>0)||cTopN>0?'Selected Avg':'Conf Avg';
  thead+=`<th style="color:var(--text4);font-style:italic">${avgLabel}</th></tr></thead>`;

  let tbody='<tbody>';
  let lastCat='';
  allStats.forEach(stat=>{
    const mv=parseFloat(cRow[stat.key]);
    if(isNaN(mv))return;
    if(stat.cat!==lastCat){
      const cols=2+compareTeams.length+1;
      tbody+=`<tr class="cat-row"><td colspan="${cols}">${stat.cat}</td></tr>`;
      lastCat=stat.cat;
    }
    const myRank=cRow[stat.key+'_conf_rank'];
    const myConfPct=parseFloat(cRow[stat.key+'_conf_pct']);
    const myConfCls=pctCls(isNaN(myConfPct)?null:myConfPct,stat.isTempo,false);

    tbody+=`<tr class="my-row"><td class="stat-col">${stat.label}${tip(stat.key)}</td>
      <td><div class="conf-cell">
        <span class="conf-val" style="color:var(--accent)">${stat.fmt(mv)}</span>
        <span class="conf-pct ${myConfCls.color}">${!isNaN(myConfPct)?Math.round(myConfPct*100)+'%':''}</span>
        <span class="conf-rank">Conf #${myRank||'—'}</span>
      </div></td>`;

    compareTeams.forEach(t=>{
      const v=parseFloat(t[stat.key]);
      const r=t[stat.key+'_conf_rank'];
      const vConfPct=parseFloat(t[stat.key+'_conf_pct']);
      const vCls=pctCls(isNaN(vConfPct)?null:vConfPct,stat.isTempo,false);
      const col=cCustomMode?'var(--yellow)':'var(--text2)';
      tbody+=`<td><div class="conf-cell">
        <span class="conf-val" style="color:${col}">${!isNaN(v)?stat.fmt(v):'—'}</span>
        <span class="conf-pct ${vCls.color}">${!isNaN(vConfPct)?Math.round(vConfPct*100)+'%':''}</span>
        <span class="conf-rank">Conf #${r||'—'}</span>
      </div></td>`;
    });

    // Conf avg column with descriptor
    const avgVals=avgSource.map(t=>parseFloat(t[stat.key])).filter(v=>!isNaN(v));
    const avg=avgVals.length?avgVals.reduce((a,b)=>a+b,0)/avgVals.length:null;
    let avgDesc='',avgDescCls='';
    // Use z-score based comparison for accuracy at extremes
    const myZ=parseFloat(cRow[stat.key+'_z']);
    const avgZs=avgSource.map(t=>parseFloat(t[stat.key+'_z'])).filter(v=>!isNaN(v));
    const avgZ=avgZs.length?avgZs.reduce((a,b)=>a+b,0)/avgZs.length:null;
    if(!isNaN(myZ)&&avgZ!==null){
      const diff=myZ-avgZ;
      if(stat.isTempo){
        if(diff>=1.0){avgDesc='Much Faster';avgDescCls='pct-fast';}
        else if(diff>=0.4){avgDesc='Faster';avgDescCls='pct-good';}
        else if(diff>-0.4){avgDesc='Avg Pace';avgDescCls='pct-avg';}
        else if(diff>-1.0){avgDesc='Slower';avgDescCls='pct-below';}
        else{avgDesc='Much Slower';avgDescCls='pct-slow';}
      } else if(stat.isFreq){
        if(diff>=1.0){avgDesc='Much Higher Freq';avgDescCls='pct-elite';}
        else if(diff>=0.4){avgDesc='Higher Freq';avgDescCls='pct-good';}
        else if(diff>-0.4){avgDesc='Avg Freq';avgDescCls='pct-avg';}
        else if(diff>-1.0){avgDesc='Lower Freq';avgDescCls='pct-below';}
        else{avgDesc='Much Lower Freq';avgDescCls='pct-poor';}
      } else {
        if(diff>=1.0){avgDesc='Well Above';avgDescCls='pct-elite';}
        else if(diff>=0.4){avgDesc='Above Avg';avgDescCls='pct-good';}
        else if(diff>-0.4){avgDesc='On Par';avgDescCls='pct-avg';}
        else if(diff>-1.0){avgDesc='Below Avg';avgDescCls='pct-below';}
        else{avgDesc='Well Below';avgDescCls='pct-poor';}
      }
    }
    tbody+=`<td><div class="conf-cell">
      <span class="conf-val" style="color:var(--text4);font-style:italic">${avg!==null?stat.fmt(avg):'—'}</span>
      ${avgDesc?`<span style="font-size:9px;font-weight:700;letter-spacing:0.04em" class="${avgDescCls}">${avgDesc}</span>`:''}
    </div></td></tr>`;
  });
  tbody+='</tbody>';

  document.getElementById('conf-stats-container').innerHTML=
    `<div class="conf-stats-wrap"><table class="conf-stats-table">${thead}${tbody}</table></div>`;
}

// ── HISTORICAL ────────────────────────────────────────────────────────────────
function setHistCat(cat,btn){cHistCat=cat;document.querySelectorAll('.hist-cat-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');renderHistorical();}
function setHistComp(comp,btn){cHistComp=comp;document.querySelectorAll('.hist-comp-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');renderHistorical();}

function initHistSelectors(){
  // No-op — season range replaced by trend window (years back from current season)
}

async function renderHistorical(){
  if(!cTeam||!cYear)return;
  document.getElementById('historical-loading').style.display='flex';
  document.getElementById('historical-empty').style.display='none';
  document.getElementById('historical-content').style.display='none';

  // Build year list: current year back cTrendWindow years
  const allYears=Object.keys(INDEX).map(Number).filter(y=>INDEX[String(y)].includes(cTeam)).sort((a,b)=>a-b);
  const maxBack=cTrendWindow;
  // Take current year + up to maxBack prior years
  const yn=allYears.filter(y=>y<=cYear).slice(-( maxBack+1));

  if(yn.length<2){
    document.getElementById('historical-loading').style.display='none';
    document.getElementById('historical-empty').style.display='flex';
    document.getElementById('historical-empty').textContent='Not enough seasons available.';return;
  }
  await Promise.all(yn.map(y=>loadYear(y)));
  const td=yn.map(y=>YCACHE[y].find(d=>d.team_name===cTeam)).filter(Boolean);
  document.getElementById('historical-loading').style.display='none';
  document.getElementById('historical-content').style.display='block';
  updatePageDesc();

  // Caveat if team has fewer years than requested
  const caveatEl=document.getElementById('hist-caveat');
  const firstYear=yn[0];
  const requestedStart=allYears.filter(y=>y<=cYear).slice(-(maxBack+1))[0];
  if(yn.length<=maxBack){
    caveatEl.style.display='block';
    caveatEl.textContent=`* ${cTeam} data begins in ${yLabel(firstYear)}. Showing all available seasons.`;
  } else {
    caveatEl.style.display='none';
  }

  // Build stats list
  let stats;
  if(cHistCat==='All'){
    const shotFlat=SHOT_CATS.flatMap(c=>[
      {key:c.rk,label:`${c.name} Rate (Off)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:true,cat:'Shot Profile'},
      {key:c.fk,label:`${c.name} FG% (Off)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:false,cat:'Shot Profile'},
      {key:c.drk,label:`${c.name} Rate (Def)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:true,cat:'Shot Profile'},
      {key:c.dfk,label:`${c.name} FG% (Def)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:false,cat:'Shot Profile'},
    ]);
    stats=[...Object.entries(STAT_CATS).flatMap(([cat,ss])=>ss.map(s=>({...s,cat}))), ...shotFlat];
  } else if(cHistCat==='Shot Profile'){
    stats=SHOT_CATS.flatMap(c=>[
      {key:c.rk,label:`${c.name} Rate (Off)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:true},
      {key:c.fk,label:`${c.name} FG% (Off)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:false},
      {key:c.drk,label:`${c.name} Rate (Def)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:true},
      {key:c.dfk,label:`${c.name} FG% (Def)`,fmt:v=>(v*100).toFixed(1)+'%',isTempo:false,isFreq:false},
    ]);
  } else {
    stats=STAT_CATS[cHistCat]||[];
  }

  const years=td.map(d=>d.year);
  const isD1Conf=cHistComp==='d1conf';
  const confName=cRow?cRow.conference:'Conf';

  // Build header
  let thead=`<thead><tr><th class="stat-col">Stat</th>`;
  years.forEach(y=>{
    if(isD1Conf){
      thead+=`<th colspan="2" style="text-align:center;border-left:1px solid var(--border2)">${yLabel(y)}</th>`;
    } else {
      thead+=`<th>${yLabel(y)}</th>`;
    }
  });
  thead+=`<th>Trend</th></tr>`;
  if(isD1Conf){
    thead+=`<tr><th class="stat-col"></th>`;
    years.forEach(()=>{
      thead+=`<th style="font-size:9px;color:var(--text4);border-left:1px solid var(--border2)">All D1</th>`;
      thead+=`<th style="font-size:9px;color:var(--text4)">${confName}</th>`;
    });
    thead+=`<th></th></tr>`;
  }
  thead+=`</thead>`;

  let tbody='<tbody>';
  stats.forEach(stat=>{
    const vals=td.map(d=>{
      const raw=parseFloat(d[stat.key]);
      let pct,rank,confPct,confRank;
      if(cHistComp==='sub'){
        pct=parseFloat(d[stat.key+'_sub_pct']);if(isNaN(pct))pct=null;
        rank=d[stat.key+'_sub_rank'];
      } else {
        // d1 or d1conf — both use D1 pct for trend
        pct=parseFloat(d[stat.key+'_pct']);if(isNaN(pct))pct=null;
        rank=d[stat.key+'_rank'];
      }
      if(isD1Conf){
        const cp=parseFloat(d[stat.key+'_conf_pct']);confPct=isNaN(cp)?null:cp;
        confRank=d[stat.key+'_conf_rank'];
      }
      return{raw,pct,rank,confPct:confPct||null,confRank:confRank||null};
    });

    // Trend using last cTrendWindow years
    const trendVals=vals.slice(-Math.min(cTrendWindow+1,vals.length));
    const tFirst=trendVals[0],tLast=trendVals[trendVals.length-1];
    let arrow='';
    {
      // Helper: get trend label + css class from a pct diff
      function trendLabel(diff,isTempo,isFreq){
        if(isTempo){
          if(diff>=0.20)return{txt:'↑↑ Much Faster',cls:'arrow-up'};
          if(diff>=0.07)return{txt:'↑ Faster',cls:'arrow-up'};
          if(diff<=-0.20)return{txt:'↓↓ Much Slower',cls:'arrow-down'};
          if(diff<=-0.07)return{txt:'↓ Slower',cls:'arrow-down'};
          return{txt:'→ Stable Pace',cls:'arrow-flat'};
        } else if(isFreq){
          if(diff>=0.20)return{txt:'↑↑ Much Higher Freq',cls:'arrow-up'};
          if(diff>=0.07)return{txt:'↑ Higher Freq',cls:'arrow-up'};
          if(diff<=-0.20)return{txt:'↓↓ Much Lower Freq',cls:'arrow-down'};
          if(diff<=-0.07)return{txt:'↓ Lower Freq',cls:'arrow-down'};
          return{txt:'→ Stable Freq',cls:'arrow-flat'};
        } else {
          if(diff>=0.20)return{txt:'↑↑ Strong Improvement',cls:'arrow-up'};
          if(diff>=0.07)return{txt:'↑ Improving',cls:'arrow-up'};
          if(diff<=-0.20)return{txt:'↓↓ Sharp Decline',cls:'arrow-down'};
          if(diff<=-0.07)return{txt:'↓ Declining',cls:'arrow-down'};
          return{txt:'→ Stable',cls:'arrow-flat'};
        }
      }

      const fp=tFirst?.pct,lp=tLast?.pct;
      if(fp!==null&&fp!==undefined&&lp!==null&&lp!==undefined&&tFirst!==tLast){
        const diff=lp-fp;
        const d1Label=trendLabel(diff,stat.isTempo,stat.isFreq||false);
        arrow=`<span class="hist-arrow ${d1Label.cls}">${d1Label.txt}</span>`;

        // Second line for D1+Conf view — conf trend using same labels
        if(isD1Conf){
          const fcp=tFirst?.confPct,lcp=tLast?.confPct;
          if(fcp!==null&&fcp!==undefined&&lcp!==null&&lcp!==undefined){
            const confDiff=lcp-fcp;
            const confLabel=trendLabel(confDiff,stat.isTempo,stat.isFreq||false);
            // Only show second line if conf label differs from D1 label
            if(confLabel.txt!==d1Label.txt){
              arrow+=`<br><span class="hist-arrow ${confLabel.cls}" style="font-size:11px">${confLabel.txt} vs. ${confName}</span>`;
            }
          }
        }
      }
    }

    tbody+=`<tr><td class="stat-col" style="padding:10px 14px;text-align:left">${stat.label}${tip(stat.key)}</td>`;
    vals.forEach(v=>{
      const fv=!isNaN(v.raw)?stat.fmt(v.raw):'—';
      const cls=pctCls(v.pct,stat.isTempo,stat.isFreq||false);
      const rd=cHistComp==='sub'?`Sub #${v.rank||'—'}`:`#${v.rank||'—'}`;
      if(isD1Conf){
        // D1 column
        tbody+=`<td style="border-left:1px solid var(--border2)"><div class="hist-cell">
          <span class="hist-val">${fv}</span>
          ${v.pct!==null?`<span class="hist-pct ${cls.color}">${Math.round(v.pct*100)}%</span>`:''}
          <span class="hist-rank">${rd}</span>
        </div></td>`;
        // Conf column
        const confCls=pctCls(v.confPct,stat.isTempo,stat.isFreq||false);
        tbody+=`<td><div class="hist-cell">
          ${v.confPct!==null?`<span class="hist-pct ${confCls.color}">${Math.round(v.confPct*100)}%</span>`:''}
          <span class="hist-rank">Conf #${v.confRank||'—'}</span>
        </div></td>`;
      } else {
        tbody+=`<td><div class="hist-cell">
          <span class="hist-val">${fv}</span>
          ${v.pct!==null?`<span class="hist-pct ${cls.color}">${Math.round(v.pct*100)}%</span>`:''}
          <span class="hist-rank">${rd}</span>
        </div></td>`;
      }
    });
    tbody+=`<td>${arrow}</td></tr>`;
  });
  tbody+='</tbody>';

  document.getElementById('hist-table-container').innerHTML=
    `<div class="hist-table-wrap"><table class="hist-table">${thead}${tbody}</table></div>`;
}


