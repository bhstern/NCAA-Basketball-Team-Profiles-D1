// ── HEAD TO HEAD ──────────────────────────────────────────────────────────────
async function renderH2H(){
  const tA=document.getElementById('h2h-team-a').value;
  const yA=parseInt(document.getElementById('h2h-year-a').value);
  const tB=document.getElementById('h2h-team-b').value;
  const yB=parseInt(document.getElementById('h2h-year-b').value);
  if(!tA||!yA||!tB||!yB)return;
  document.getElementById('h2h-empty').style.display='none';
  document.getElementById('h2h-loading').style.display='flex';
  document.getElementById('h2h-content').style.display='none';
  try{
    await Promise.all([loadYear(yA),loadYear(yB)]);
    const rA=YCACHE[yA].find(d=>d.team_name===tA),rB=YCACHE[yB].find(d=>d.team_name===tB);
    if(!rA||!rB){document.getElementById('h2h-loading').style.display='none';document.getElementById('h2h-empty').style.display='flex';document.getElementById('h2h-empty').textContent='Data not found.';return;}
    document.getElementById('h2h-loading').style.display='none';
    document.getElementById('h2h-content').style.display='block';
    const shotFlat=SHOT_CATS.flatMap(c=>[
      {key:c.rk,label:`${c.name} Rate (Off)`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:true},
      {key:c.fk,label:`${c.name} FG% (Off)`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:false},
      {key:c.drk,label:`${c.name} Rate (Def)`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:true},
      {key:c.dfk,label:`${c.name} FG% (Def)`,fmt:v=>(v*100).toFixed(1)+'%',cat:'Shot Profile',isTempo:false,isFreq:false},
    ]);
    const allStatsAll=[...Object.entries(STAT_CATS).flatMap(([cat,stats])=>stats.map(s=>({...s,cat}))), ...shotFlat];
    const allStats=cH2HCat==='All'?allStatsAll:allStatsAll.filter(s=>s.cat===cH2HCat);
    const sameYear=yA===yB;
    let html=`<div style="font-size:11px;color:var(--text4);font-style:italic;margin-bottom:14px;text-align:center">
      Percentiles reflect each team's standing within their own season (${yLabel(yA)} for ${tA}${sameYear?'':', '+yLabel(yB)+' for '+tB}).
      ${sameYear?'Both teams from the same season.':'Different seasons — use raw values for direct comparison.'}
    </div>
    <div class="h2h-table-wrap"><table class="h2h-table">
      <thead><tr>
        <th class="stat-col">Stat</th>
        <th class="team-col" style="color:var(--accent)">
          <div style="display:flex;align-items:center;justify-content:center;gap:6px">
            <img src="${TDIR}${sf(tA)}.png" style="width:18px;height:18px;object-fit:contain" onerror="this.style.display='none'"/>
            ${tA} <span style="font-size:9px;color:var(--text4)">${yLabel(yA)}</span>
          </div>
        </th>
        <th class="team-col" style="color:var(--yellow)">
          <div style="display:flex;align-items:center;justify-content:center;gap:6px">
            <img src="${TDIR}${sf(tB)}.png" style="width:18px;height:18px;object-fit:contain" onerror="this.style.display='none'"/>
            ${tB} <span style="font-size:9px;color:var(--text4)">${yLabel(yB)}</span>
          </div>
        </th>
        <th style="color:var(--text4);font-size:9px;letter-spacing:0.1em;text-transform:uppercase">Comparison</th>
      </tr></thead><tbody>`;
    let lastCat='';
    allStats.forEach(stat=>{
      const vA=parseFloat(rA[stat.key]),vB=parseFloat(rB[stat.key]);
      if(isNaN(vA)&&isNaN(vB))return;
      if(stat.cat!==lastCat){html+=`<tr class="cat-row"><td colspan="4">${stat.cat}</td></tr>`;lastCat=stat.cat;}
      const pA=parseFloat(rA[stat.key+'_pct']),pB=parseFloat(rB[stat.key+'_pct']);
      const clsA=pctCls(isNaN(pA)?null:pA,stat.isTempo,false);
      const clsB=pctCls(isNaN(pB)?null:pB,stat.isTempo,false);
      // H2H descriptor
      let h2hDesc='',h2hCls='pct-avg';
      const zA=parseFloat(rA[stat.key+'_z']),zB=parseFloat(rB[stat.key+'_z']);
      if(!isNaN(zA)&&!isNaN(zB)){
        const diff=zA-zB;
        const nmA=tA;
        const nmB=tB;
        if(stat.isTempo){
          if(diff>=1.0){h2hDesc=nmA+' Much Faster';h2hCls='pct-fast';}
          else if(diff>=0.5){h2hDesc=nmA+' Faster';h2hCls='pct-good';}
          else if(diff>=-0.5){h2hDesc='Similar Pace';h2hCls='pct-avg';}
          else if(diff>=-1.0){h2hDesc=nmB+' Faster';h2hCls='pct-below';}
          else{h2hDesc=nmB+' Much Faster';h2hCls='pct-slow';}
        } else if(stat.isFreq){
          if(diff>=1.0){h2hDesc=nmA+' Much Higher Freq';h2hCls='pct-elite';}
          else if(diff>=0.5){h2hDesc=nmA+' Higher Freq';h2hCls='pct-good';}
          else if(diff>=-0.5){h2hDesc='Similar Freq';h2hCls='pct-avg';}
          else if(diff>=-1.0){h2hDesc=nmB+' Higher Freq';h2hCls='pct-below';}
          else{h2hDesc=nmB+' Much Higher Freq';h2hCls='pct-poor';}
        } else {
          if(diff>=1.0){h2hDesc=nmA+' Much Better';h2hCls='pct-elite';}
          else if(diff>=0.5){h2hDesc=nmA+' Better';h2hCls='pct-good';}
          else if(diff>=-0.5){h2hDesc='Similar';h2hCls='pct-avg';}
          else if(diff>=-1.0){h2hDesc=nmB+' Better';h2hCls='pct-below';}
          else{h2hDesc=nmB+' Much Better';h2hCls='pct-poor';}
        }
      }
      html+=`<tr>
        <td class="stat-col">${stat.label}${tip(stat.key)}</td>
        <td><div class="h2h-cell">
          <span class="h2h-val ${clsA.color}">${!isNaN(vA)?stat.fmt(vA):'—'}</span>
          ${!isNaN(pA)?`<span class="h2h-pct ${clsA.color}">${Math.round(pA*100)}%</span>`:''}
          <span class="h2h-rank">#${rA[stat.key+'_rank']||'—'}</span>
        </div></td>
        <td><div class="h2h-cell">
          <span class="h2h-val ${clsB.color}">${!isNaN(vB)?stat.fmt(vB):'—'}</span>
          ${!isNaN(pB)?`<span class="h2h-pct ${clsB.color}">${Math.round(pB*100)}%</span>`:''}
          <span class="h2h-rank">#${rB[stat.key+'_rank']||'—'}</span>
        </div></td>
        <td style="text-align:center"><span style="font-size:11px;font-weight:600" class="${h2hCls}">${h2hDesc}</span></td>
      </tr>`;
    });
    html+='</tbody></table></div>';
    document.getElementById('h2h-content').innerHTML=html;
  }catch(e){document.getElementById('h2h-loading').style.display='none';document.getElementById('h2h-empty').style.display='flex';document.getElementById('h2h-empty').textContent='Error loading data.';}
}

// Pre-populate H2H Team A with current selection
function syncH2HTeamA(){
  if(cTeam&&cYear){
    const ta=document.getElementById('h2h-team-a');
    const ya=document.getElementById('h2h-year-a');
    if(ta)ta.value=cTeam;
    if(ya)ya.value=cYear;
  }
}
