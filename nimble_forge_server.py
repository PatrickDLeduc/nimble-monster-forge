#!/usr/bin/env python3
"""
Nimble Monster Forge — Local Server
Run: python nimble_forge_server.py
Then open: http://localhost:8000
"""

import json
import http.server
import urllib.request
import urllib.error

import os
PORT = int(os.environ.get("PORT", 8000))

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nimble Monster Forge</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap');
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#0f0c07;color:#e8d5b0;font-family:'Crimson Text','Palatino Linotype',serif;min-height:100vh;padding:24px}
  .wrap{max-width:720px;margin:0 auto}
  h1{font-family:'Cinzel',serif;font-size:26px;color:#d4a832;letter-spacing:3px}
  .sub{color:#8a7a5a;font-size:14px;font-style:italic;margin-bottom:28px}
  label.section{color:#a89060;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;display:block;margin-bottom:6px}
  input,select,textarea{background:#2a2418;border:1px solid #5a4a2e;border-radius:4px;color:#e8d5b0;padding:8px 12px;font-size:14px;font-family:'Crimson Text',serif;outline:none;width:100%}
  input:focus,select:focus,textarea:focus{border-color:#8b6914}
  textarea{resize:vertical;min-height:56px}
  .row{display:flex;gap:8px;margin-bottom:6px}.row input{flex:1}.row select{flex:1;cursor:pointer}.row .lvl{width:56px;text-align:center;flex:none}
  .btn-rm{background:none;border:1px solid #5a3a2e;color:#a05a3a;border-radius:4px;width:32px;cursor:pointer;font-size:16px}
  .btn-add{background:none;border:1px dashed #5a4a2e;color:#8a7a5a;padding:5px 14px;border-radius:4px;cursor:pointer;font-size:12px;font-family:'Crimson Text',serif}
  .chips{display:flex;flex-wrap:wrap;gap:4px}
  .chip{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;cursor:pointer;border:1px solid #5a4a2e;color:#8a7a5a;user-select:none;transition:all .15s}
  .chip.on{border-color:#d4a832;background:#3a2f1e;color:#d4a832}
  .group{margin-bottom:18px}
  .btn-forge{width:100%;padding:14px;font-size:16px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;font-family:'Cinzel',serif;background:linear-gradient(135deg,#8b6914,#d4a832,#8b6914);color:#1a1207;border:none;border-radius:4px;cursor:pointer}
  .btn-forge:disabled{background:#2a2418;color:#8a7a5a;cursor:wait}
  .error{margin-top:16px;padding:12px;background:#3a1a1a;border:1px solid #8a3a3a;border-radius:4px;color:#e88;font-size:13px;white-space:pre-wrap;word-break:break-all;max-height:200px;overflow:auto}
  .stat-block{background:linear-gradient(135deg,#1a1207 0%,#2a1f10 50%,#1a1207 100%);border:2px solid #8b6914;border-radius:2px;padding:20px;position:relative;margin-top:28px;overflow:hidden}
  .bar{height:3px;background:linear-gradient(90deg,transparent,#8b6914,#d4a832,#8b6914,transparent);position:absolute;left:0;right:0}.bar.top{top:0}.bar.bot{bottom:0}
  .divider{height:1px;background:linear-gradient(90deg,transparent,#8b6914,transparent);margin:10px 0}
  .gold{color:#d4a832}.muted{color:#a89060}.dim{color:#8a7a5a}
  .stat-name{font-family:'Cinzel',serif;font-size:22px;color:#d4a832;font-weight:700}
  .hp-box{font-size:28px;font-weight:bold;color:#d4a832}
  .armor-badge{background:#8b6914;color:#1a1207;padding:1px 8px;border-radius:2px;font-size:13px;font-weight:bold}
  .red{color:#c44;font-weight:bold;text-transform:uppercase;letter-spacing:1px;font-size:13px}
  .actions{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}
  .btn-at{padding:10px 20px;border-radius:4px;cursor:pointer;font-size:14px;font-weight:bold;font-family:'Cinzel',serif;border:2px solid #3a6a3a;background:#1a2a1e;color:#6cb86c}
  .btn-at.saving{background:#2a2418;color:#8a7a5a;border-color:#5a4a2e;cursor:wait}
  .btn-at.saved{background:#1a2a1a;color:#8f8;border-color:#4a8a2e}
  .btn-at.err{background:#3a1a1a;color:#e88;border-color:#8a3a3a}
  .btn-exp{padding:8px 14px;border-radius:4px;cursor:pointer;font-size:13px;font-family:'Crimson Text',serif;border:1px solid #8b6914;background:#3a2f1e;color:#d4a832}
  .btn-exp.on{background:#2d5a1e;color:#8f8;border-color:#4a8a2e}
  .export-area{width:100%;min-height:140px;max-height:400px;background:#1a1207;border:1px solid #5a4a2e;border-radius:4px;color:#e8d5b0;padding:12px;font-size:13px;font-family:monospace;resize:vertical;outline:none;margin-top:10px}
  .config-panel{background:#1a1207;border:1px solid #5a4a2e;border-radius:6px;padding:20px;margin-bottom:20px}
  .config-panel input{font-family:monospace}
  .hint{font-size:11px;color:#8a7a5a;margin-top:4px}
  .btn-cfg{background:none;border:1px solid #5a4a2e;color:#8a7a5a;padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px;font-family:'Crimson Text',serif}
  .btn-cfg.on{border-color:#3a6a3a;color:#6cb86c}
  .btn-save-cfg{background:linear-gradient(135deg,#8b6914,#d4a832);color:#1a1207;border:none;padding:8px 20px;border-radius:4px;cursor:pointer;font-size:13px;font-weight:bold;font-family:'Cinzel',serif}
  .btn-cancel{background:none;color:#8a7a5a;border:1px solid #5a4a2e;padding:8px 20px;border-radius:4px;cursor:pointer;font-size:13px}
  .top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
  .opts-row{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-end;margin-bottom:18px}.opts-row>div{flex:1;min-width:130px}
  .cb-label{display:flex;align-items:center;gap:8px;cursor:pointer;padding-bottom:8px;font-size:14px}
  .status{margin-top:8px;font-size:13px}.status.ok{color:#6cb86c}.status.err{color:#e88}
</style>
</head>
<body>
<div class="wrap" id="app"></div>
<script>
const CLASSES=["Berserker","Cheat","Commander","Hunter","Mage","Oathsworn","Shadowmancer","Shepherd","Songweaver","Stormshifter","Zephyr"];
const THEMES=["cosmic horror","sword-and-sorcery","dark fairy tale","wilderness","undead","elemental","beast hunt","cult","ancient ruins","pirate","swamp","desert"];
const ENVS=["forest","underground","hill","field","dungeon","marsh","desert","mountain","sky","urban","shadowblight","coastal"];

const SYSTEM_PROMPT=`You are a Nimble RPG monster designer. Create mechanically valid monsters for Nimble v2.0.3.

IMPORTANT OUTPUT RULES:
- Respond with ONLY valid JSON. No markdown, no backticks, no commentary.
- NEVER use double quotes inside string values. Use single quotes instead.
- Keep all string values on a single line. No line breaks inside strings.

MONSTER STAT TABLE (Level | HP None/M/H | DPR | Dice | Save DC):
0.25|12/9/7|3|1d4+1|9  0.33|15/11/8|5|1d6+2|9  0.5|18/15/11|7|1d6+3|10
1|26/20/16|11|2d8+2|10  2|34/27/20|13|2d8+4|11  3|41/33/25|15|2d8+6|11
4|49/39/29|18|2d8+9|12  5|58/46/35|19|2d8+10|12  6|68/54/41|21|2d8+12|13
7|79/63/47|24|3d8+10|13  8|91/73/55|26|3d8+12|14  9|104/83/62|28|4d8+10|14
10|118/94/71|30|4d8+12|15  11|133/106/80|33|5d8+11|15  12|149/119/89|35|5d8+13|16
13|166/132/100|38|6d8+11|16  14|184/147/110|40|6d8+13|17  15|203/162/122|43|7d8+11|17
16|223/178/134|45|7d8+13|18  17|244/195/146|48|8d8+12|18  18|266/213/160|50|8d8+14|19
19|289/231/173|52|9d8+12|19  20|313/250/189|54|9d8+13|20

LEGENDARY TABLE (Party Lvl | HP M/H | Last Stand HP | DC | Small/Big Dmg):
1|50/35|10|10|8/16  2|75/55|20|11|9/18  3|100/75|30|11|10/20  4|125/95|40|12|11/22
5|150/115|50|12|12/24  6|175/135|60|13|13/26  7|200/155|70|13|14/28  8|225/175|80|14|15/30
9|250/195|90|14|16/32  10|275/215|100|15|17/34  12|325/255|120|16|19/38  14|375/295|140|17|21/42
16|425/335|160|18|23/46  18|475/375|180|19|25/50  20|525/415|200|20|27/54

RULES:
- For each special ability, lower HP or damage by 1 row. State which tradeoff.
- Die themes: d4 undead, d6 goblins/small, d8 humans, d10 beasts, d12 giants, d20 mightiest
- Encounter balance: monster levels = hero levels is Hard. 75% is Medium. <50% Easy. 125% Deadly.
- Unarmored: normal damage. Medium(M): dice only, ignore modifiers. Heavy(H): half dice, ignore modifiers.
- Legendary monsters act after EACH hero turn, have Bloodied at half HP, Last Stand at 0 HP.

JSON SCHEMA (respond with EXACTLY this structure):
{"name":"","level":0,"hp":0,"armor":"None","speed":6,"fly":null,"burrow":null,"size":"Medium","dpr":0,"save_dc":0,"attacks":"Attack1. dice+mod. Effect. | Attack2. dice+mod.","trait":"Trait Name. Description.","abilities":"Ability1. Description. | Ability2. Description.","legendary":false,"bloodied":"","last_stand":"","last_stand_hp":null,"saves":"","lore":"","tips":"","encounter":"","balance":"","tags":"tag1, tag2","family":""}`;

let state={heroes:[{name:"",cls:"Berserker",level:3}],theme:[],env:[],diff:"Hard",legendary:false,custom:"",size:"",loading:false,error:null,monster:null,showExport:null,showConfig:false,cfg:JSON.parse(localStorage.getItem("nimble_cfg")||'{"anthropicKey":"","atToken":"","atBase":"","atTable":""}'),atStatus:null,atError:null,atWarnings:null};

function saveCfg(){localStorage.setItem("nimble_cfg",JSON.stringify(state.cfg))}
function totalLvl(){return state.heroes.reduce((s,h)=>s+(parseInt(h.level)||1),0)}
function avgLvl(){return Math.round(totalLvl()/state.heroes.length)}
function hasCfg(){return !!state.cfg.anthropicKey}
function hasAt(){return state.cfg.atToken&&state.cfg.atBase&&state.cfg.atTable}

function parseResponse(text){
  let s=text.replace(/```json\s?|```/g,"").trim();
  let a=s.indexOf("{"),b=s.lastIndexOf("}");
  if(a===-1||b===-1)throw new Error("No JSON in response");
  s=s.slice(a,b+1).replace(/[\x00-\x1f]/g,ch=>(ch==="\n"||ch==="\r"||ch==="\t")?" ":"");
  return JSON.parse(s);
}

function toFields(m){
  let f={};const set=(k,v)=>{if(v!==null&&v!==undefined&&v!=="")f[k]=v};
  set("Name",m.name||"Unnamed");set("Level",m.level);set("HP",m.hp);
  var armorVal=String(m.armor||"None");if(armorVal.toLowerCase().includes("heavy")||armorVal.includes("H"))armorVal="Heavy";else if(armorVal.toLowerCase().includes("med")||armorVal.includes("M"))armorVal="Medium";else armorVal="None";
  set("Armor Type",armorVal);set("Speed",m.speed||6);
  set("Fly Speed",m.fly);set("Burrow Speed",m.burrow);
  set("Size",m.size||"Medium");set("Damage Per Round",m.dpr);
  set("Save DC",m.save_dc);
  set("Attack Description",(m.attacks||"").replace(/\|/g,"\n").trim());
  set("Special Abilities",[m.trait,m.abilities].filter(Boolean).join("\n"));
  set("Monster Family",m.family||"Homebrew");
  if(m.tags){f["Environment Tags"]=m.tags}
  set("Is Legendary",m.legendary||false);
  set("Bloodied Ability",m.bloodied);set("Last Stand Ability",m.last_stand);
  set("Last Stand HP",m.last_stand_hp);set("Advantaged Saves",m.saves);
  set("Source","AI Generated");
  set("Notes",[m.lore,m.tips?"GM: "+m.tips:null,m.encounter?"Encounter: "+m.encounter:null,m.balance?"Balance: "+m.balance:null].filter(Boolean).join("\n\n"));
  return f;
}

async function generate(){
  state.loading=true;state.error=null;state.monster=null;state.atStatus=null;state.atWarnings=null;state.showExport=null;render();
  if(!state.cfg.anthropicKey){state.loading=false;state.error="Set your Anthropic API key in Settings first.";state.showConfig=true;render();return}
  const party=state.heroes.map((h,i)=>`${h.name||"Hero "+(i+1)}: Level ${h.level} ${h.cls}`).join(", ");
  const prompt=`Create a ${state.legendary?"LEGENDARY ":""}monster for: ${party} (${state.heroes.length} heroes, total levels ${totalLvl()}). Difficulty: ${state.diff}. Theme: ${state.theme.join(", ")||"any"}. Environment: ${state.env.join(", ")||"any"}. ${state.size?"Size: "+state.size+".":""} ${state.legendary?"Use Legendary table at party level "+avgLvl()+".":""} ${state.custom}`;
  try{
    const res=await fetch("/api/claude",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({key:state.cfg.anthropicKey,system:SYSTEM_PROMPT,prompt:prompt})
    });
    const data=await res.json();
    if(data.error)throw new Error(data.error);
    state.monster=parseResponse(data.text);
  }catch(e){state.error=e.message}
  state.loading=false;render();
  if(state.monster)document.getElementById("result")?.scrollIntoView({behavior:"smooth"});
}

async function saveToAirtable(){
  if(!hasAt()){state.showConfig=true;render();return}
  state.atStatus="saving";state.atError=null;state.atWarnings=null;render();
  try{
    var fields=toFields(state.monster);
    const res=await fetch("/api/airtable",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({token:state.cfg.atToken,baseId:state.cfg.atBase,tableId:state.cfg.atTable,fields:fields})
    });
    const data=await res.json();
    if(data.error)throw new Error(data.error);
    state.atStatus="saved";
    if(data.warnings&&data.warnings.length>0){state.atWarnings=data.warnings}
  }catch(e){state.atStatus="error";state.atError=e.message}
  render();
}

function esc(s){return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}

function render(){
  const m=state.monster;const app=document.getElementById("app");
  function chips(list,sel,fn){return list.map(v=>`<span class="chip ${sel.includes(v)?'on':''}" onclick="${fn}('${v}')">${v}</span>`).join("")}
  function rchips(list,cur,fn){return list.map(v=>`<span class="chip ${cur===v?'on':''}" onclick="${fn}('${v}')">${v}</span>`).join("")}

  let h=`<div class="top-bar"><h1>⚔ NIMBLE MONSTER FORGE</h1>
    <button class="btn-cfg ${hasCfg()?'on':''}" onclick="state.showConfig=!state.showConfig;render()">${hasCfg()?"● Settings":"⚙ Settings"}</button></div>
    <p class="sub">AI-powered creature design for Nimble RPG</p>`;

  if(state.showConfig){const c=state.cfg;
    h+=`<div class="config-panel"><span class="gold" style="font-family:Cinzel,serif;font-size:14px;font-weight:bold;letter-spacing:1px">API SETTINGS</span>
    <div style="margin-top:16px;margin-bottom:12px"><label class="section">Anthropic API Key</label>
    <input type="password" id="cfgA" value="${esc(c.anthropicKey)}" placeholder="sk-ant-..."><div class="hint">console.anthropic.com/settings/keys</div></div>
    <div style="margin-bottom:12px"><label class="section">Airtable Token</label>
    <input type="password" id="cfgT" value="${esc(c.atToken)}" placeholder="pat..."><div class="hint">airtable.com/create/tokens — needs data.records:write</div></div>
    <div style="margin-bottom:12px"><label class="section">Airtable Base ID</label>
    <input id="cfgB" value="${esc(c.atBase)}" placeholder="appXXXXXXXXXXXXXX"></div>
    <div style="margin-bottom:16px"><label class="section">Airtable Monsters Table ID</label>
    <input id="cfgTbl" value="${esc(c.atTable)}" placeholder="tblXXXXXXXXXXXXXX"><div class="hint">Both IDs from your URL: airtable.com/appXXX/tblXXX/...</div></div>
    <div style="display:flex;gap:8px"><button class="btn-save-cfg" onclick="state.cfg={anthropicKey:document.getElementById('cfgA').value,atToken:document.getElementById('cfgT').value,atBase:document.getElementById('cfgB').value,atTable:document.getElementById('cfgTbl').value};saveCfg();state.showConfig=false;render()">Save</button>
    <button class="btn-cancel" onclick="state.showConfig=false;render()">Cancel</button></div></div>`}

  h+=`<div class="group"><div style="display:flex;justify-content:space-between;margin-bottom:8px">
    <label class="section" style="margin:0">Your Party</label>
    <span class="dim" style="font-size:13px">Total Levels: <b class="gold">${totalLvl()}</b></span></div>`;
  state.heroes.forEach((hr,i)=>{const opts=CLASSES.map(c=>`<option ${c===hr.cls?"selected":""}>${c}</option>`).join("");
    h+=`<div class="row"><input placeholder="Name" value="${esc(hr.name)}" oninput="state.heroes[${i}].name=this.value">
    <select onchange="state.heroes[${i}].cls=this.value">${opts}</select>
    <input class="lvl" type="number" min="1" max="20" value="${hr.level}" onchange="state.heroes[${i}].level=parseInt(this.value)||1">
    ${state.heroes.length>1?`<button class="btn-rm" onclick="state.heroes.splice(${i},1);render()">×</button>`:""}</div>`});
  h+=`<button class="btn-add" onclick="state.heroes.push({name:'',cls:'Berserker',level:${avgLvl()||1}});render()">+ Add Hero</button></div>`;

  h+=`<div class="group"><label class="section">Difficulty</label><div class="chips">${rchips(["Easy","Medium","Hard","Deadly","Very Deadly"],state.diff,"setDiff")}</div></div>`;
  h+=`<div class="group"><label class="section">Theme</label><div class="chips">${chips(THEMES,state.theme,"toggleTheme")}</div></div>`;
  h+=`<div class="group"><label class="section">Environment</label><div class="chips">${chips(ENVS,state.env,"toggleEnv")}</div></div>`;

  const sOpts=["","Tiny","Small","Medium","Large","Huge","Gargantuan"].map(s=>`<option ${s===state.size?"selected":""} value="${s}">${s||"Any"}</option>`).join("");
  h+=`<div class="opts-row"><div><label class="section">Size</label><select onchange="state.size=this.value">${sOpts}</select></div>
  <label class="cb-label" style="color:${state.legendary?'#d4a832':'#8a7a5a'}"><input type="checkbox" ${state.legendary?"checked":""} onchange="state.legendary=this.checked;render()" style="accent-color:#d4a832"> Legendary</label></div>`;

  h+=`<div class="group"><label class="section">Custom Instructions</label><textarea placeholder="e.g. 'A corrupted treant' or 'punishes ranged attackers'" oninput="state.custom=this.value">${esc(state.custom)}</textarea></div>`;
  h+=`<button class="btn-forge" ${state.loading?"disabled":""} onclick="generate()">${state.loading?"Forging...":"⚒ Forge Monster"}</button>`;
  if(state.error)h+=`<div class="error">${esc(state.error)}</div>`;

  if(m){
    const spd=[m.speed,m.fly&&("Fly "+m.fly),m.burrow&&("Burrow "+m.burrow)].filter(Boolean).join(", ");
    const ab=m.armor!=="None"?(m.armor.includes("H")?"H":m.armor.includes("M")?"M":""):"";
    const attacks=(m.attacks||"").split("|").map(s=>s.trim()).filter(Boolean);
    const abilities=(m.abilities||"").split("|").map(s=>s.trim()).filter(Boolean);

    h+=`<div class="stat-block" id="result"><div class="bar top"></div>
    <div style="display:flex;justify-content:space-between;align-items:flex-start"><div>
    <div class="stat-name">${esc(m.name)}</div>
    <div class="muted" style="font-size:12px;margin-top:4px">Lvl ${m.level} • ${m.size} • ${m.armor==="None"?"Unarmored":m.armor} • Speed ${spd} • DC ${m.save_dc}${m.legendary?" • LEGENDARY":""}</div></div>
    <div style="display:flex;align-items:center;gap:6px">${ab?`<span class="armor-badge">${ab}</span>`:""}<span class="hp-box">${m.hp}</span></div></div><div class="divider"></div>`;

    if(m.trait){const p=m.trait.split(".");h+=`<div style="margin-bottom:8px;font-size:14px"><span class="gold" style="font-weight:600">${esc(p[0])}.</span> ${esc(p.slice(1).join(".").trim())}</div>`}
    abilities.forEach(a=>{const p=a.split(".");h+=`<div style="margin-bottom:6px;font-size:14px"><span class="gold" style="font-weight:600">${esc(p[0])}.</span> ${esc(p.slice(1).join(".").trim())}</div>`});
    attacks.forEach(a=>{const p=a.split(".");h+=`<div style="margin-bottom:5px;font-size:14px"><b>• ${esc(p[0])}.</b> ${esc(p.slice(1).join(".").trim())}</div>`});
    if(m.legendary&&m.bloodied)h+=`<div class="divider"></div><div style="margin-bottom:6px;font-size:14px"><span class="red">Bloodied: </span>${esc(m.bloodied)}</div>`;
    if(m.legendary&&m.last_stand)h+=`<div style="margin-bottom:6px;font-size:14px"><span class="red">Last Stand: </span>${esc(m.last_stand)}${m.last_stand_hp?" ("+m.last_stand_hp+" more HP to kill.)":""}</div>`;
    if(m.saves)h+=`<div class="muted" style="font-size:12px;margin-top:6px">Saves: ${esc(m.saves)}</div>`;
    h+=`<div class="divider"></div><div class="muted" style="font-size:13px;font-style:italic">${esc(m.lore||"")}</div>`;
    if(m.tips)h+=`<div class="dim" style="font-size:13px;margin-top:6px"><b class="muted">GM:</b> ${esc(m.tips)}</div>`;
    if(m.encounter)h+=`<div class="dim" style="font-size:13px;margin-top:4px"><b class="muted">Encounter:</b> ${esc(m.encounter)}</div>`;
    if(m.balance)h+=`<div class="dim" style="font-size:13px;margin-top:4px"><b class="muted">Balance:</b> ${esc(m.balance)}</div>`;
    h+=`<div class="bar bot"></div></div>`;

    const atCls=state.atStatus==="saving"?"saving":state.atStatus==="saved"?"saved":state.atStatus==="error"?"err":"";
    const atLbl=state.atStatus==="saving"?"Saving...":state.atStatus==="saved"?"✓ Saved!":state.atStatus==="error"?"✗ Retry":"Save to Airtable";
    h+=`<div class="actions"><button class="btn-at ${atCls}" onclick="saveToAirtable()" ${state.atStatus==="saving"?"disabled":""}>${atLbl}</button>
    <button class="btn-exp ${state.showExport==="statblock"?"on":""}" onclick="state.showExport=state.showExport==='statblock'?null:'statblock';render()">${state.showExport==="statblock"?"▾":"▸"} Stat Block</button>
    <button class="btn-exp ${state.showExport==="json"?"on":""}" onclick="state.showExport=state.showExport==='json'?null:'json';render()">${state.showExport==="json"?"▾":"▸"} JSON</button></div>`;

    if(state.atStatus==="saved"&&!state.atWarnings)h+=`<div class="status ok">Record created in your Monsters table!</div>`;
    if(state.atStatus==="saved"&&state.atWarnings&&state.atWarnings.length>0)h+=`<div class="status" style="color:#d4a832">⚠ Saved with ${state.atWarnings.length} field(s) dropped (logged in Notes):<br><span class="dim" style="font-size:12px">${esc(state.atWarnings.join(" | "))}</span></div>`;
    if(state.atStatus==="error")h+=`<div class="status err">${esc(state.atError||"Unknown error")}</div>`;

    if(state.showExport){let txt="";
      if(state.showExport==="statblock")txt=[m.name+" — Lvl "+m.level+(m.size!=="Medium"?", "+m.size:""),m.trait,m.abilities,(m.attacks||"").split("|").map(a=>"• "+a.trim()).join("\n"),m.legendary&&m.bloodied?"BLOODIED: "+m.bloodied:null,m.legendary&&m.last_stand?"LAST STAND: "+m.last_stand:null,m.hp+(m.armor!=="None"?" "+m.armor:"")].filter(Boolean).join("\n");
      else txt=JSON.stringify(m,null,2);
      h+=`<div style="margin-top:10px"><div class="dim" style="font-size:12px;margin-bottom:4px">Select all + copy:</div><textarea class="export-area" readonly onfocus="this.select()">${esc(txt)}</textarea></div>`}
  }
  app.innerHTML=h;
}

window.setDiff=v=>{state.diff=v;render()};
window.toggleTheme=v=>{state.theme=state.theme.includes(v)?state.theme.filter(x=>x!==v):[...state.theme,v];render()};
window.toggleEnv=v=>{state.env=state.env.includes(v)?state.env.filter(x=>x!==v):[...state.env,v];render()};
render();
</script>
</body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/api/claude":
            self._proxy_claude(body)
        elif self.path == "/api/airtable":
            self._proxy_airtable(body)
        else:
            self._json_response(404, {"error": "Not found"})

    def _proxy_claude(self, body):
        try:
            payload = json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "system": body.get("system", ""),
                "messages": [{"role": "user", "content": body.get("prompt", "")}]
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": body.get("key", ""),
                    "anthropic-version": "2023-06-01"
                }
            )
            with urllib.request.urlopen(req) as res:
                data = json.loads(res.read())
                text = "".join(b.get("text", "") for b in data.get("content", []))
                self._json_response(200, {"text": text})
        except urllib.error.HTTPError as e:
            err = e.read().decode()
            try:
                msg = json.loads(err).get("error", {}).get("message", err)
            except Exception:
                msg = err
            self._json_response(e.code, {"error": msg})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _proxy_airtable(self, body):
        url = f"https://api.airtable.com/v0/{body['baseId']}/{body['tableId']}"
        token = body.get("token", "")
        fields = dict(body.get("fields", {}))
        errors_log = []
        max_retries = 5

        for attempt in range(max_retries):
            try:
                payload = json.dumps({"records": [{"fields": fields}]}).encode()
                req = urllib.request.Request(
                    url, data=payload,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req) as res:
                    data = json.loads(res.read())
                    record_id = data.get("records", [{}])[0].get("id")
                    msg = "Saved successfully"
                    if errors_log:
                        msg += f" (dropped {len(errors_log)} field(s): {', '.join(errors_log)})"
                    self._json_response(200, {"ok": True, "id": record_id, "warnings": errors_log})
                    return
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                try:
                    err_msg = json.loads(err_body).get("error", {}).get("message", err_body)
                except Exception:
                    err_msg = err_body

                # Try to extract the problem field name from the error
                # Common patterns: 'Unknown field name: "X"' or 'Cannot parse value for field X'
                problem_field = None
                import re
                # Match: Unknown field name: "FieldName"
                m = re.search(r'Unknown field name:\s*"([^"]+)"', err_msg)
                if m:
                    problem_field = m.group(1)
                # Match: Cannot parse value for field FieldName
                if not problem_field:
                    m = re.search(r'Cannot parse value for field\s+(\w[\w\s]*\w|\w+)', err_msg)
                    if m:
                        problem_field = m.group(1).strip()
                # Match: Field "FieldName" cannot accept...
                if not problem_field:
                    m = re.search(r'[Ff]ield\s+"([^"]+)"', err_msg)
                    if m:
                        problem_field = m.group(1)

                if problem_field and problem_field in fields:
                    # Save the failed value, remove the field, append to error log
                    failed_value = fields.pop(problem_field)
                    error_entry = f"{problem_field}: {failed_value}"
                    errors_log.append(error_entry)
                    print(f"  Airtable rejected field '{problem_field}', retrying without it (attempt {attempt + 1})")

                    # Append error info to Notes field so nothing is lost
                    notes = fields.get("Notes", "")
                    if notes:
                        notes += "\n\n"
                    notes += "⚠ IMPORT ERRORS (fields that failed to save):\n" + "\n".join(errors_log)
                    fields["Notes"] = notes
                    continue  # Retry without the problem field
                else:
                    # Can't identify the problem field — give up
                    self._json_response(e.code, {"error": err_msg})
                    return
            except Exception as e:
                self._json_response(500, {"error": str(e)})
                return

        # Exhausted retries
        self._json_response(500, {"error": f"Too many field errors. Dropped: {', '.join(errors_log)}"})

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt, *args):
        msg = fmt % args
        if "GET / " in msg or "POST /api" in msg:
            print(f"  {msg}")

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════╗
║       ⚔  NIMBLE MONSTER FORGE  ⚔        ║
║                                          ║
║  Open: http://localhost:{PORT}              ║
║  Stop: Ctrl+C                            ║
╚══════════════════════════════════════════╝
""")
    server = http.server.HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
