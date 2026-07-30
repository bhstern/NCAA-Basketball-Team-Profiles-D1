/* ============================================================================
   shotcourt.js — shared shot-chart engine for the Shot Charts tab.

   The court geometry (buildCourtSVG + the C constants) and the two color
   functions (pctColor, diffColor) are lifted VERBATIM from the reference
   prototypes. Do NOT "tidy" the paths: every zone fill reuses the shared
   boundary strings (PATH_THREE_LINE, pathRim) so adjacent zones meet exactly
   with no gap/overlap at any opacity, and every boundary is stroked so two
   same-colored zones still read apart. Regenerating the paths independently
   loses both. Geometry is real NCAA men's proportions; the rim dome is 7 ft.

   The ONLY change vs the prototype engine: block() honors an optional
   o.showLabels===false to support the tab's "show labels" toggle. When
   showLabels is true/undefined the output is identical, and no geometry
   path is touched — so the §15 court acceptance check is unaffected.
   ========================================================================== */

const SC_esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

/* ---------- color: FG percentile (0..1) -> red..green ---------- */
const SC_STOPS=[[0,[192,57,43]],[0.25,[230,126,34]],[0.5,[241,196,15]],[0.75,[130,183,75]],[1,[39,174,96]]];
function scPctColor(p){
  if(p==null||isNaN(p))return '#555';
  p=Math.max(0,Math.min(1,p));
  for(let i=1;i<SC_STOPS.length;i++){
    if(p<=SC_STOPS[i][0]){
      const[a,ca]=SC_STOPS[i-1],[b,cb]=SC_STOPS[i],t=(p-a)/(b-a);
      const c=ca.map((v,j)=>Math.round(v+(cb[j]-v)*t));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return 'rgb(39,174,96)';
}

/* ---------- color: raw point difference (this minus other), fixed ±10-pt ---------- */
function scDiffColor(d){
  if(d==null||isNaN(d))return '#555';
  const t=Math.max(-1,Math.min(1,d/10));
  const red=[192,57,43],slate=[120,128,150],green=[39,174,96],
    lerp=(a,b,u)=>a.map((v,j)=>Math.round(v+(b[j]-v)*u));
  const c=t<0?lerp(slate,red,-t):lerp(slate,green,t);
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/* ---------- court geometry (1ft = 10u, NCAA men's) ---------- */
const SC_C={W:500,BASE_Y:370,TOP_Y:0,BASKET_X:250,BASKET_Y:317.5,R3:221.46,CORNER_X:30,CORNER_BREAK_Y:292.11,
  LANE_L:190,LANE_R:310,FT_Y:180,FT_R:60,REST_R:40,RIM_R_RH:7.5,BB_Y:330,BB_L:220,BB_R:280};
const SC_VBW=524, SC_VBH=394, SC_RIMR=70, SC_OPA=0.85,
  SC_LINE='#e6edf7',
  SC_MONO='SFMono-Regular,Menlo,Consolas,monospace',
  SC_FONT='-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif';
const SC_PATH_COURT=`M 0 ${SC_C.TOP_Y} L ${SC_C.W} ${SC_C.TOP_Y} L ${SC_C.W} ${SC_C.BASE_Y} L 0 ${SC_C.BASE_Y} Z`;
const SC_PATH_THREE_LINE=`M ${SC_C.CORNER_X} ${SC_C.BASE_Y} L ${SC_C.CORNER_X} ${SC_C.CORNER_BREAK_Y} A ${SC_C.R3} ${SC_C.R3} 0 1 1 ${SC_C.W-SC_C.CORNER_X} ${SC_C.CORNER_BREAK_Y} L ${SC_C.W-SC_C.CORNER_X} ${SC_C.BASE_Y} Z`;
const scPathRim=r=>`M ${SC_C.BASKET_X-r} ${SC_C.BASKET_Y} A ${r} ${r} 0 0 1 ${SC_C.BASKET_X+r} ${SC_C.BASKET_Y} L ${SC_C.BASKET_X+r} ${SC_C.BASE_Y} L ${SC_C.BASKET_X-r} ${SC_C.BASE_Y} Z`;
const scStrokeRim=r=>`M ${SC_C.BASKET_X-r} ${SC_C.BASE_Y} L ${SC_C.BASKET_X-r} ${SC_C.BASKET_Y} A ${r} ${r} 0 0 1 ${SC_C.BASKET_X+r} ${SC_C.BASKET_Y} L ${SC_C.BASKET_X+r} ${SC_C.BASE_Y}`;
const SC_ANCHOR={three:{x:405,y:52,name:'3PT'},mid:{x:130,y:172,name:'Midrange'},rim:{x:250,y:255,name:'Rim'}};
const SC_TITLE_MAXW=470, SC_TITLE_ADV=0.62;   // usable title width from x=14; conservative per-char advance (em)
/* font size that keeps `title` on one line within the court; floored for readability */
function scTitleFontSize(title){
  if(!title) return 21;
  return (title.length*21*SC_TITLE_ADV > SC_TITLE_MAXW)
    ? Math.max(14, Math.round(SC_TITLE_MAXW/(title.length*SC_TITLE_ADV)))
    : 21;
}
const scPcf=x=>x==null?'—':Math.round(x*100)+'%';
const scOrdPct=x=>{if(x==null)return '—';const n=Math.round(x*100),v=n%100,d=n%10;
  const suf=(v>=11&&v<=13)?'th':(d===1?'st':d===2?'nd':d===3?'rd':'th');return `${n}${suf} pct`;};

/* o = { zones:{rim,mid,three} each {color,r,rp,fg,fgp, dRate,dFg}, showPct, showLabels, title, subtitle, basisNote, diffMetric }
   r/fg are 0..1 values; rp/fgp are 0..1 percentiles (population mode only).
   dRate/dFg are signed point differences vs the other chart (diff mode only);
   diffMetric ('fg'|'rate') tells the label which delta to print next to that metric.
   basisNote: optional string stamped bottom-left so an exported image always
   states the population it is colored against (controller decides when to pass it).
   colorNote: optional string stamped bottom-right stating which metric drives the color. */
function buildCourtSVG(o){
  const rimPath=scPathRim(SC_RIMR),ZT=SC_PATH_COURT+' '+SC_PATH_THREE_LINE,ZM=SC_PATH_THREE_LINE+' '+rimPath;
  const fz=(d,f)=>`<path fill-rule="evenodd" fill="${f}" fill-opacity="${SC_OPA}" d="${d}"/>`;
  const block=z=>{
    if(o.showLabels===false) return '';
    const a=SC_ANCHOR[z],zd=o.zones[z];
    const dm=o.diffMetric;                                   // 'fg' | 'rate' | undefined (diff mode only)
    const dStr=d=> (d==null||isNaN(d))?'':` (${d>0?'+':''}${Math.round(d)})`;
    const ms=o.metricsShown;                                 // 'rate' | 'fg' | undefined (both)
    const stack=o.stackPct;                                  // profile: split "value (pct)" onto two lines
    const rBase=`Rate: ${scPcf(zd.r)}`, fBase=`FG: ${scPcf(zd.fg)}`;
    const rPct=o.showPct?`(${scOrdPct(zd.rp)})`:'', fPct=o.showPct?`(${scOrdPct(zd.fgp)})`:'';
    const rTxt=rBase+(rPct?` ${rPct}`:'')+(dm==='rate'?dStr(zd.dRate):'');
    const fTxt=fBase+(fPct?` ${fPct}`:'')+(dm==='fg'?dStr(zd.dFg):'');
    const showR = ms!=='fg', showF = ms!=='rate';
    const lines=[];
    if(stack){                                               // value and percentile on separate lines
      if(showR){ lines.push(rBase+(dm==='rate'?dStr(zd.dRate):'')); if(rPct) lines.push(rPct); }
      if(showF){ lines.push(fBase+(dm==='fg'?dStr(zd.dFg):'')); if(fPct) lines.push(fPct); }
    } else {
      if(showR) lines.push(rTxt);
      if(showF) lines.push(fTxt);
    }
    if(zd.vol) lines.push(zd.vol);                           // volume on its own line
    const zf=o.zoneFont||15, nf=Math.round(zf*1.2);
    let g=`<g text-anchor="middle" font-family="${SC_MONO}" fill="${SC_LINE}" paint-order="stroke" stroke="rgba(8,13,26,0.72)" stroke-width="4" stroke-linejoin="round">
      <text x="${a.x}" y="${a.y}" font-size="${nf}" font-weight="700">${a.name}</text>`;
    lines.forEach((t,i)=>{ const y=a.y+nf+4+i*(zf+4);
      g+=`<text x="${a.x}" y="${y}" font-size="${(i===lines.length-1&&zd.vol)?zf-1:zf}">${t}</text>`; });
    return g+'</g>';};
  const tb=()=>{const t=o.title,s=o.subtitle;if(!t&&!s)return '';
    // shrink the title font so multi-name titles don't run off the court; clamp as a hard backstop.
    // o.titleSize lets the controller force one shared size across both compare charts.
    let tfs=21, tLen='';
    if(t){
      tfs = o.titleSize || scTitleFontSize(t);
      if(t.length*tfs*SC_TITLE_ADV > SC_TITLE_MAXW) tLen=` textLength="${SC_TITLE_MAXW}" lengthAdjust="spacingAndGlyphs"`;
    }
    let g=`<g paint-order="stroke" stroke="rgba(8,13,26,0.72)" stroke-width="4" stroke-linejoin="round" font-family="${SC_FONT}" text-anchor="start">`;
    if(t)g+=`<text x="14" y="33" font-size="${tfs}" font-weight="700" fill="#f3f7fd"${tLen}>${SC_esc(t)}</text>`;
    if(s)g+=`<text x="14" y="${t?55:33}" font-size="13" font-weight="500" fill="#c4d2ea">${SC_esc(s)}</text>`;return g+'</g>';};
  const bn=()=>{ if(!o.basisNote) return '';
    return `<g paint-order="stroke" stroke="rgba(8,13,26,0.72)" stroke-width="4" stroke-linejoin="round" font-family="${SC_FONT}" text-anchor="start"><text x="14" y="363" font-size="13" font-weight="600" fill="#c4d2ea">${SC_esc(o.basisNote)}</text></g>`;};
  const cn=()=>{ if(!o.colorNote) return '';
    return `<g paint-order="stroke" stroke="rgba(8,13,26,0.72)" stroke-width="4" stroke-linejoin="round" font-family="${SC_FONT}" text-anchor="end"><text x="498" y="363" font-size="13" font-weight="600" fill="#c4d2ea">${SC_esc(o.colorNote)}</text></g>`;};
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="-12 -12 ${SC_VBW} ${SC_VBH}">
    ${fz(ZT,o.zones.three.color)}${fz(ZM,o.zones.mid.color)}
    <path fill="${o.zones.rim.color}" fill-opacity="${SC_OPA}" d="${rimPath}"/>
    <g fill="none" stroke="${SC_LINE}" stroke-width="2" stroke-linejoin="round">
      <line x1="0" y1="${SC_C.BASE_Y}" x2="${SC_C.W}" y2="${SC_C.BASE_Y}"/><line x1="0" y1="${SC_C.BASE_Y}" x2="0" y2="${SC_C.TOP_Y}"/><line x1="${SC_C.W}" y1="${SC_C.BASE_Y}" x2="${SC_C.W}" y2="${SC_C.TOP_Y}"/>
      <path d="M ${SC_C.CORNER_X} ${SC_C.BASE_Y} L ${SC_C.CORNER_X} ${SC_C.CORNER_BREAK_Y} A ${SC_C.R3} ${SC_C.R3} 0 1 1 ${SC_C.W-SC_C.CORNER_X} ${SC_C.CORNER_BREAK_Y} L ${SC_C.W-SC_C.CORNER_X} ${SC_C.BASE_Y}"/>
      <path d="${scStrokeRim(SC_RIMR)}"/>
      <path d="M ${SC_C.LANE_L} ${SC_C.BASE_Y} L ${SC_C.LANE_L} ${SC_C.FT_Y} L ${SC_C.LANE_R} ${SC_C.FT_Y} L ${SC_C.LANE_R} ${SC_C.BASE_Y}"/>
      <path d="M ${SC_C.LANE_L} ${SC_C.FT_Y} A ${SC_C.FT_R} ${SC_C.FT_R} 0 0 1 ${SC_C.LANE_R} ${SC_C.FT_Y}"/>
      <path stroke-dasharray="6 5" d="M ${SC_C.LANE_L} ${SC_C.FT_Y} A ${SC_C.FT_R} ${SC_C.FT_R} 0 0 0 ${SC_C.LANE_R} ${SC_C.FT_Y}"/>
      <path stroke-dasharray="6 5" d="M ${SC_C.BASKET_X-SC_C.REST_R} ${SC_C.BASKET_Y} A ${SC_C.REST_R} ${SC_C.REST_R} 0 0 1 ${SC_C.BASKET_X+SC_C.REST_R} ${SC_C.BASKET_Y}"/>
      <circle cx="${SC_C.BASKET_X}" cy="${SC_C.BASKET_Y}" r="${SC_C.RIM_R_RH}"/><line x1="${SC_C.BB_L}" y1="${SC_C.BB_Y}" x2="${SC_C.BB_R}" y2="${SC_C.BB_Y}"/>
    </g>${tb()}${block('three')}${block('mid')}${block('rim')}${bn()}${cn()}</svg>`;
}

/* ---------- PNG export (single + paired), background filled #0f1729 first ---------- */
function scExportPNG(svgEl, filename){
  if(!svgEl) return;
  const clone=svgEl.cloneNode(true);
  clone.setAttribute('width',SC_VBW); clone.setAttribute('height',SC_VBH);
  const xml=new XMLSerializer().serializeToString(clone);
  const url='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(xml)));
  const img=new Image();
  img.onload=()=>{
    const s=2, cv=document.createElement('canvas'); cv.width=SC_VBW*s; cv.height=SC_VBH*s;
    const ctx=cv.getContext('2d');
    ctx.fillStyle='#0f1729'; ctx.fillRect(0,0,cv.width,cv.height);
    ctx.drawImage(img,0,0,cv.width,cv.height);
    const a=document.createElement('a'); a.download=filename; a.href=cv.toDataURL('image/png'); a.click();
  };
  img.src=url;
}

function scExportPair(svgA, svgB, filename, stacked){
  if(!svgA||!svgB) return;
  const mk=el=>{const c=el.cloneNode(true);c.setAttribute('width',SC_VBW);c.setAttribute('height',SC_VBH);
    return 'data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(new XMLSerializer().serializeToString(c))));};
  const ia=new Image(),ib=new Image();let n=0;const g=24,s=2;
  const done=()=>{if(++n<2)return;
    const cv=document.createElement('canvas');
    if(stacked){ cv.width=SC_VBW*s; cv.height=(SC_VBH*2+g)*s; }
    else { cv.width=(SC_VBW*2+g)*s; cv.height=SC_VBH*s; }
    const ctx=cv.getContext('2d');ctx.fillStyle='#0f1729';ctx.fillRect(0,0,cv.width,cv.height);
    if(stacked){ ctx.drawImage(ia,0,0,SC_VBW*s,SC_VBH*s); ctx.drawImage(ib,0,(SC_VBH+g)*s,SC_VBW*s,SC_VBH*s); }
    else { ctx.drawImage(ia,0,0,SC_VBW*s,SC_VBH*s); ctx.drawImage(ib,(SC_VBW+g)*s,0,SC_VBW*s,SC_VBH*s); }
    const dl=document.createElement('a');dl.download=filename;dl.href=cv.toDataURL('image/png');dl.click();};
  ia.onload=done;ib.onload=done;ia.src=mk(svgA);ib.src=mk(svgB);
}

/* ---------- safe filename from a title ---------- */
function scSlugName(title, fallback){
  return ((title||fallback).replace(/[^a-z0-9]+/gi,'_').replace(/^_|_$/g,'')||fallback)+'.png';
}
