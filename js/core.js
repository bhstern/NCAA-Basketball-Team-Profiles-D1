const TDIR='logos/teams/', CDIR='logos/conferences/';
let INDEX={}, YCACHE={}, cTeam=null, cYear=null, cYearData=null, cRow=null;
let cView='d1', cHistCat='Overview', cHistComp='d1conf', cTopN=0, cCompTeams=[], cCustomMode=false, cTab='profile'; let cTrendWindow=1;

function isPower(row){return row&&row.power_mid==='Power';}
function jsq(s){return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'");}  // safe inside onclick="fn('...')" when value has apostrophes
function yLabel(y){return y===2026?'2025-26':`${y-1}-${String(y).slice(2)}`;}
function sf(n){return n.replace(/ /g,'_').replace(/\./g,'').replace(/'/g,'').replace(/&/g,'').replace(/\//g,'_');}

const TIPS={
  // ── Team Strength ──────────────────────────────────────────────────────────
  adj_em:'Adjusted Efficiency Margin — offensive minus defensive efficiency, adjusted for opponent strength. The most reliable single measure of overall team quality.',
  barthag:'Estimated probability of beating an average D1 team on a neutral court.',
  elite_sos_rate:'Share of games an elite team would be expected to lose against this schedule. Higher = tougher schedule faced.',
  talent:'Composite talent rating based on recruiting rankings of the roster.',
  // ── Roster ─────────────────────────────────────────────────────────────────
  'exp.':'Composite roster experience, weighted by minutes played.',
  'avg_hgt.':'Average height of the rotation, weighted by minutes.',
  'eff._hgt.':'Effective height — accounts for positional value of height, weighted by minutes.',
  // ── Tempo ──────────────────────────────────────────────────────────────────
  'adj._t':'Adjusted tempo — possessions per 40 minutes, adjusted for opponent pace.',
  raw_t:'Raw tempo — actual possessions per 40 minutes, unadjusted.',
  // ── PPP System ─────────────────────────────────────────────────────────────
  ppp_diff:'PPP Differential — actual offensive PPP minus defensive PPP. How many points per possession this team outscores opponents.',
  xPPP_diff:'The difference between expected offensive and defensive PPP — based on each team\'s shot distribution compared against league-average FG% by shot type and season.',
  residual_diff:'Residual Differential — Performance Over Expectation. How much a team outperforms shot quality on both ends combined.',
  ppp_off_full:'Actual points scored per possession — estimated from shot distribution and FG%, calculated independently (not from Torvik).',
  xPPP_off:'Expected points per possession on offense — shot profile frequencies multiplied by league-average FG% by shot type and season.',
  ppp_residual_off:'How much this team scores above what their shot selection would predict — driven by shotmaking, ball security, free throw generation, offensive rebounding, transition, spacing, creation, and talent. Positive = outperforming what the shot profile predicts.',
  ppp_def_full:'Actual points allowed per possession — estimated independently (not from Torvik).',
  xPPP_def:'Expected PPP allowed on defense — opponent shot profile frequencies multiplied by league-average FG% by shot type and season.',
  ppp_residual_def:'How much this team holds opponents below their expected efficiency — driven by contesting shots, forcing turnovers, defensive rebounding, limiting free throws, scheme, and athleticism. Higher = holding opponents further below their expected efficiency.',
  // ── Offense ────────────────────────────────────────────────────────────────
  adj_oe:'Adjusted Offensive Efficiency — points scored per 100 possessions, adjusted for opponent defense.',
  efg_rate_off:'Effective Field Goal % on offense — accounts for 3-pointers being worth more than 2s.',
  tov_rate_off:'Turnover rate on offense — turnovers per possession. Lower is better.',
  orb_rate_off:'Percentage of missed shots where this team secured the offensive rebound. Higher = more second-chance opportunities.',
  ft_rate_off:'Free throw rate on offense — free throw attempts per field goal attempt.',
  ft_pct_off:'Free throw percentage on offense.',
  ast_pct_off:'Percentage of made field goals that were assisted on offense. Higher = more ball movement.',
  blk_pct_off:'Percentage of offensive field goal attempts that were blocked by the opponent.',
  // ── Defense ────────────────────────────────────────────────────────────────
  adj_de:'Adjusted Defensive Efficiency — points allowed per 100 possessions, adjusted for opponent offense.',
  efg_rate_def:'Effective Field Goal % allowed on defense — accounts for 3-pointers being worth more than 2s.',
  tov_rate_def:'Turnovers forced on defense — opponent turnovers per possession.',
  orb_rate_def:'Percentage of opponent missed shots secured by this team. Higher = limits opponent second-chance opportunities.',
  ft_rate_def:'Free throw attempts allowed per field goal attempt on defense.',
  ast_pct_def:'Percentage of opponent made field goals that were assisted. Lower = forcing tougher, less structured shots.',
  blk_pct_def:'Percentage of opponent field goal attempts blocked by this team.',
  // ── Shot Profile — Rim ─────────────────────────────────────────────────────
  off_rim_rate_total:'All shot attempts at the rim — dunks plus close two-point attempts (layups, floaters, putbacks) — as a share of total FGA. Reflects overall paint presence.',
  off_rim_fg:'Weighted FG% at the rim on offense (dunks + close 2s). Higher = better finishing at the rim.',
  def_rim_rate_total:'All opponent rim attempts allowed — dunks plus close two-point attempts — as a share of total FGA. Reflects how much opponents attack the paint.',
  def_rim_fg:'Weighted FG% allowed at the rim on defense (dunks + close 2s). Lower = better rim protection. High percentile = elite rim defense.',
  off_dunks_rate_total:'Dunk attempts as a share of total FGA. Typically the highest-percentage shot in basketball.',
  off_dunks_fg:'FG% on dunk attempts on offense.',
  def_dunks_rate_total:'Opponent dunk attempts as a share of total FGA allowed.',
  def_dunks_fg:'FG% allowed on opponent dunk attempts.',
  off_close_twos_rate_total:'Non-dunk rim attempts — layups, floaters, and putbacks — as a share of total FGA. Excludes dunks.',
  off_close_twos_fg:'FG% on non-dunk rim attempts (layups, floaters, putbacks).',
  def_close_twos_rate_total:'Opponent non-dunk rim attempts allowed — layups, floaters, and putbacks — as a share of total FGA.',
  def_close_twos_fg:'FG% allowed on opponent non-dunk rim attempts.',
  // ── Shot Profile — Midrange ────────────────────────────────────────────────
  off_long_twos_rate_total:'Midrange attempt rate — long two-point shots, all two-point attempts not taken at the rim — as a share of total FGA.',
  off_long_twos_fg:'FG% on midrange shots (long 2s).',
  def_long_twos_rate_total:'Opponent midrange attempt rate allowed — long two-point shots not at the rim.',
  def_long_twos_fg:'FG% allowed on opponent midrange shots.',
  // ── Shot Profile — Threes ──────────────────────────────────────────────────
  off_threes_rate_total:'Three-point attempt rate — share of total FGA that are 3-point attempts.',
  off_threes_fg:'FG% on three-point attempts on offense.',
  def_threes_rate_total:'Opponent three-point attempt rate allowed — share of opponent FGA that are 3-point attempts.',
  def_threes_fg:'FG% allowed on opponent three-point attempts.',
};

const STAT_CATS={
  Overview:[
    {key:'adj_em',label:'Adj. Efficiency Margin',fmt:v=>(v>0?'+':'')+v.toFixed(1)},
    {key:'ppp_diff',label:'PPP Differential',fmt:v=>(v>0?'+':'')+v.toFixed(3)},
    {key:'xPPP_diff',label:'Expected PPP Diff',fmt:v=>(v>0?'+':'')+v.toFixed(3)},
    {key:'residual_diff',label:'Residual Differential',fmt:v=>(v>0?'+':'')+v.toFixed(3)},
    {key:'barthag',label:'Barthag',fmt:v=>v.toFixed(3)},
    {key:'elite_sos_rate',label:'Elite SOS Rating',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'talent',label:'Talent Rating',fmt:v=>v.toFixed(1)},
    {key:'exp.',label:'Experience',fmt:v=>v.toFixed(2)},
    {key:'avg_hgt.',label:'Avg Height',fmt:v=>v.toFixed(1)+'"'},
    {key:'eff._hgt.',label:'Effective Height',fmt:v=>v.toFixed(1)+'"'},
    {key:'adj._t',label:'Adjusted Tempo',fmt:v=>v.toFixed(1),isTempo:true},
    {key:'raw_t',label:'Raw Tempo',fmt:v=>v.toFixed(1),isTempo:true},
  ],
  Offense:[
    {key:'adj_oe',label:'Adj. Off. Efficiency',fmt:v=>v.toFixed(1)},
    {key:'efg_rate_off',label:'eFG% (Off)',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'tov_rate_off',label:'Turnover Rate',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'orb_rate_off',label:'Off. Rebound Rate',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'ft_rate_off',label:'FT Rate',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'ft_pct_off',label:'FT%',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'ppp_off_full',label:'Points Per Possession',fmt:v=>v.toFixed(3)},
    {key:'xPPP_off',label:'Expected PPP',fmt:v=>v.toFixed(3)},
    {key:'ppp_residual_off',label:'PPP Residual',fmt:v=>(v>0?'+':'')+v.toFixed(3)},
    {key:'ast_pct_off',label:'Assist Rate',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'blk_pct_off',label:'Block % (Blocked)',fmt:v=>(v*100).toFixed(1)+'%'},
  ],
  Defense:[
    {key:'adj_de',label:'Adj. Def. Efficiency',fmt:v=>v.toFixed(1)},
    {key:'efg_rate_def',label:'eFG% Allowed',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'tov_rate_def',label:'Turnovers Forced',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'orb_rate_def',label:'Def. Rebound Rate',fmt:v=>((1-v)*100).toFixed(1)+'%'},
    {key:'ft_rate_def',label:'FT Rate Allowed',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'ppp_def_full',label:'Points Per Poss Allowed',fmt:v=>v.toFixed(3)},
    {key:'xPPP_def',label:'Expected PPP Allowed',fmt:v=>v.toFixed(3)},
    {key:'ppp_residual_def',label:'PPP Residual (Def)',fmt:v=>(v>0?'+':'')+v.toFixed(3)},
    {key:'ast_pct_def',label:'Opp. Assist Rate',fmt:v=>(v*100).toFixed(1)+'%'},
    {key:'blk_pct_def',label:'Block %',fmt:v=>(v*100).toFixed(1)+'%'},
  ],
};

const SHOT_CATS=[
  {name:'Rim',rk:'off_rim_rate_total',fk:'off_rim_fg',drk:'def_rim_rate_total',dfk:'def_rim_fg',offRateGood:true,expandable:true,
   children:[
     {name:'Dunks',rk:'off_dunks_rate_total',fk:'off_dunks_fg',drk:'def_dunks_rate_total',dfk:'def_dunks_fg'},
     {name:'Close 2s',rk:'off_close_twos_rate_total',fk:'off_close_twos_fg',drk:'def_close_twos_rate_total',dfk:'def_close_twos_fg'},
   ]},
  {name:'Midrange',rk:'off_long_twos_rate_total',fk:'off_long_twos_fg',drk:'def_long_twos_rate_total',dfk:'def_long_twos_fg',offRateGood:false,expandable:false},
  {name:'3-Pointers',rk:'off_threes_rate_total',fk:'off_threes_fg',drk:'def_threes_rate_total',dfk:'def_threes_fg',offRateGood:true,expandable:false},
];
let expandedShotRows=new Set();
let cH2HCat='Overview';
let cConfCat='Overview';


const SUMMARY_KEYS=['efg_rate_off','tov_rate_off','orb_rate_off','ft_rate_off','ft_pct_off','efg_rate_def','tov_rate_def','orb_rate_def','ft_rate_def','ast_pct_def','ast_pct_off'];
const SUMMARY_LABELS={
  efg_rate_off:'eFG% Off',tov_rate_off:'Ball Security',orb_rate_off:'Off. Rebounding',ft_rate_off:'FT Rate',ft_pct_off:'FT%',
  efg_rate_def:'eFG% Defense',tov_rate_def:'Forcing Turnovers',orb_rate_def:'Def. Rebounding',ft_rate_def:'FT Rate Allowed',ast_pct_def:'Opp. Assist Rate',
  ppp_off_full:'Scoring Efficiency',ppp_def_full:'Defensive Efficiency',
  ppp_residual_off:'PPP Residual (Off)',ppp_residual_def:'PPP Residual (Def)',residual_diff:'Residual Differential',
  blk_pct_def:'Blocking Shots',blk_pct_off:'Avoiding Blocks',ast_pct_off:'Ball Movement',
};

const PAGE_DESCS={
  profile:(t,y)=>`Team profile shows how ${t} ranks across all D1 programs in ${yLabel(y)}, with a full roster breakdown by rotation tier. Toggle between All D1 percentiles, Conference rank, and power/mid-major comparison below.`,
  conference:(t,y,c)=>`Conference context shows where ${t} stands within the ${c} in ${yLabel(y)}. Click teams in the standings to compare, or use the top N selector.`,
  historical:(t,y)=>`Historical trends show ${t}'s trajectory over the selected range. Filter by stat category and compare against All D1, conference rank, or power/mid-major peers.`,
  h2h:()=>`Head to Head lets you compare any two teams from any two seasons. Percentiles reflect each team's standing within their own season.`,
  about:()=>`Learn about the creator of this tool and the methodology behind it.`,
};
