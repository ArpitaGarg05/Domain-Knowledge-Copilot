from html import escape
from typing import Optional

import streamlit as st


STITCH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
  --dk-bg: #051424;
  --dk-lowest: #010f1f;
  --dk-low: #0d1c2d;
  --dk-surface: #122131;
  --dk-high: #1c2b3c;
  --dk-highest: #273647;
  --dk-text: #d4e4fa;
  --dk-muted: #c7c4d8;
  --dk-outline: #918fa1;
  --dk-border: #464555;
  --dk-primary: #c3c0ff;
  --dk-primary-strong: #4f46e5;
  --dk-success: #4edea3;
  --dk-warning: #ffb695;
  --dk-error: #ffb4ab;
}

html, body, [class*="css"], .stApp {
  font-family: "Geist", sans-serif;
  color: var(--dk-text);
}

.stApp {
  background:
    radial-gradient(circle at 72% 12%, rgba(79,70,229,.10), transparent 28rem),
    radial-gradient(circle at 90% 88%, rgba(0,165,114,.055), transparent 30rem),
    linear-gradient(rgba(39,54,71,.14) 1px, transparent 1px),
    linear-gradient(90deg, rgba(39,54,71,.14) 1px, transparent 1px),
    var(--dk-bg);
  background-size: auto, auto, 50px 50px, 50px 50px, auto;
}

[data-testid="stHeader"], #MainMenu, footer { display: none !important; }
[data-testid="stAppViewContainer"] > .main { background: transparent; }
.main .block-container {
  max-width: 1440px;
  padding: 2rem 2rem 6rem;
}

section[data-testid="stSidebar"] {
  width: 280px !important;
  background: rgba(1,15,31,.88);
  border-right: 1px solid rgba(70,69,85,.72);
  backdrop-filter: blur(20px);
}
section[data-testid="stSidebar"] > div { padding: 1.25rem 1rem; }
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] { display: none; }
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] { gap: .3rem; }
section[data-testid="stSidebar"] .stRadio label {
  min-height: 44px;
  padding: .7rem .85rem;
  border-radius: 8px;
  border: 1px solid transparent;
  color: rgba(199,196,216,.72);
  transition: all .18s ease;
}
section[data-testid="stSidebar"] .stRadio label:hover {
  color: var(--dk-text);
  background: rgba(28,43,60,.72);
}
section[data-testid="stSidebar"] .stRadio label:has(input:checked) {
  color: var(--dk-primary);
  background: var(--dk-high);
  border-color: rgba(195,192,255,.18);
  box-shadow: inset 2px 0 0 var(--dk-primary);
}
section[data-testid="stSidebar"] .stRadio label > div:first-child { display: none; }

h1, h2, h3, h4 { color: var(--dk-text); letter-spacing: -.015em; }
p { color: var(--dk-muted); }

.stTextInput label, .stTextArea label, .stSelectbox label,
.stFileUploader label, .stToggle label, .stRadio > label {
  font-family: "JetBrains Mono", monospace !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  letter-spacing: .06em !important;
  text-transform: uppercase;
  color: var(--dk-muted) !important;
}

.stTextInput input, .stTextArea textarea,
.stSelectbox [data-baseweb="select"] > div {
  color: var(--dk-text) !important;
  background: var(--dk-lowest) !important;
  border-color: var(--dk-border) !important;
  border-radius: 8px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus,
.stSelectbox [data-baseweb="select"] > div:focus-within {
  border-color: var(--dk-primary) !important;
  box-shadow: 0 0 0 3px rgba(195,192,255,.12) !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
  color: rgba(145,143,161,.56) !important;
}

.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
  min-height: 40px;
  border-radius: 8px;
  border: 1px solid var(--dk-border);
  background: var(--dk-low);
  color: var(--dk-text);
  font-weight: 600;
  transition: all .18s ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: rgba(195,192,255,.72);
  color: var(--dk-primary);
  background: var(--dk-high);
  box-shadow: 0 0 18px rgba(195,192,255,.10);
}
.stButton > button:active, .stFormSubmitButton > button:active {
  transform: scale(.98);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  color: #fff;
  background: var(--dk-primary-strong);
  border-color: var(--dk-primary-strong);
  box-shadow: 0 10px 30px rgba(79,70,229,.18);
}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
  color: #fff;
  background: #5b52ec;
  border-color: var(--dk-primary);
  box-shadow: 0 0 24px rgba(79,70,229,.35);
}

[data-testid="stFileUploaderDropzone"] {
  min-height: 175px;
  background: rgba(13,28,45,.64) !important;
  border: 1px dashed rgba(145,143,161,.65) !important;
  border-radius: 12px !important;
  transition: all .2s ease;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--dk-primary) !important;
  background: rgba(79,70,229,.08) !important;
  box-shadow: 0 0 28px rgba(195,192,255,.08);
}

.stTabs [data-baseweb="tab-list"] {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  background: rgba(1,15,31,.72);
  border: 1px solid rgba(70,69,85,.62);
  border-radius: 10px;
  padding: 4px;
}
.stTabs [data-baseweb="tab"] {
  justify-content: center;
  border-radius: 7px;
  color: var(--dk-muted);
  font-weight: 600;
}
.stTabs [aria-selected="true"] {
  color: var(--dk-primary) !important;
  background: var(--dk-high) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none; }

.stSegmentedControl [data-testid="stWidgetLabel"] { display:none; }
.stSegmentedControl [data-baseweb="button-group"] {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  width:100%;
  gap:6px;
  padding:4px;
  border:1px solid rgba(70,69,85,.62);
  border-radius:10px;
  background:rgba(1,15,31,.72);
}
.stSegmentedControl button {
  width:100%;
  justify-content:center;
  border:0 !important;
  border-radius:7px !important;
  background:transparent !important;
  color:var(--dk-muted) !important;
}
.stSegmentedControl button[aria-pressed="true"] {
  color:var(--dk-primary) !important;
  background:var(--dk-high) !important;
  box-shadow:inset 0 0 0 1px rgba(195,192,255,.14) !important;
}

[data-testid="stChatMessage"] {
  max-width: 900px;
  margin: 0 auto .65rem;
  padding: 1rem 1.1rem;
  background: rgba(18,33,49,.72);
  border: 1px solid rgba(70,69,85,.62);
  border-radius: 12px;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
  background: linear-gradient(135deg, rgba(18,33,49,.92), rgba(28,43,60,.72));
  border-color: rgba(195,192,255,.25);
}
[data-testid="stChatInput"] {
  max-width: 900px;
  margin: auto;
}
[data-testid="stChatInput"] > div {
  background: rgba(13,28,45,.92) !important;
  border: 1px solid rgba(145,143,161,.68) !important;
  border-radius: 16px !important;
  backdrop-filter: blur(20px);
  box-shadow: 0 16px 45px rgba(1,15,31,.38);
}

.streamlit-expanderHeader {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  color: var(--dk-primary) !important;
}
[data-testid="stExpander"] {
  border: 1px solid rgba(70,69,85,.76) !important;
  border-left: 3px solid var(--dk-primary) !important;
  border-radius: 9px !important;
  background: rgba(1,15,31,.58);
}

.dk-brand { padding: .2rem .25rem 1rem; }
.dk-brand__title {
  color: var(--dk-primary);
  font-size: 25px;
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -.03em;
}
.dk-brand__sub {
  margin-top: .45rem;
  font: 500 10px/1.4 "JetBrains Mono", monospace;
  color: rgba(199,196,216,.55);
  letter-spacing: .1em;
  text-transform: uppercase;
}
.dk-sidebar-label {
  margin: 1rem .25rem .45rem;
  color: rgba(145,143,161,.75);
  font: 600 10px/1.4 "JetBrains Mono", monospace;
  letter-spacing: .1em;
  text-transform: uppercase;
}
.dk-user {
  margin-top: 1rem;
  padding: .85rem;
  display: flex;
  gap: .7rem;
  align-items: center;
  border: 1px solid rgba(70,69,85,.58);
  border-radius: 10px;
  background: rgba(13,28,45,.72);
}
.dk-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  display: grid; place-items: center;
  background: linear-gradient(135deg, var(--dk-primary-strong), #00a572);
  color: white; font-weight: 700;
}
.dk-user strong { display:block; color:var(--dk-text); font-size:12px; }
.dk-user span { display:block; color:var(--dk-outline); font-size:10px; }

.dk-page-header {
  margin: .5rem 0 1.6rem;
  animation: dk-enter .35s ease both;
}
.dk-eyebrow, .dk-label {
  font: 600 11px/1.4 "JetBrains Mono", monospace;
  color: var(--dk-primary);
  letter-spacing: .10em;
  text-transform: uppercase;
}
.dk-page-header h1 {
  margin: .35rem 0 .35rem;
  font-size: clamp(30px, 4vw, 40px);
  line-height: 1.12;
}
.dk-page-header p {
  max-width: 720px;
  margin: 0;
  font-size: 16px;
  color: rgba(199,196,216,.78);
}

.dk-metric-grid {
  display:grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  gap: 12px;
  margin: 0 0 1.5rem;
}
.dk-metric-grid--2 { grid-template-columns: repeat(2, minmax(0,1fr)); }
.dk-metric {
  min-height: 116px;
  padding: 1rem;
  border: 1px solid rgba(70,69,85,.72);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(18,33,49,.96), rgba(13,28,45,.76));
  box-shadow: inset 0 1px 0 rgba(212,228,250,.035);
}
.dk-metric__label {
  font: 600 10px/1.4 "JetBrains Mono", monospace;
  color: var(--dk-outline);
  letter-spacing: .08em;
  text-transform: uppercase;
}
.dk-metric__value {
  margin: .48rem 0 .25rem;
  color: var(--dk-text);
  font: 700 26px/1 "JetBrains Mono", monospace;
}
.dk-metric__meta { color: rgba(199,196,216,.62); font-size: 12px; }
.dk-metric--primary .dk-metric__value { color: var(--dk-primary); }
.dk-metric--success .dk-metric__value { color: var(--dk-success); }

.dk-section-title {
  display:flex; align-items:end; justify-content:space-between; gap:1rem;
  margin: 1.4rem 0 .75rem;
}
.dk-section-title h2 { margin:0; font-size: 22px; }
.dk-section-title span {
  font: 500 10px/1.4 "JetBrains Mono", monospace;
  color: var(--dk-outline); letter-spacing:.08em; text-transform:uppercase;
}

.dk-corpus-card, .dk-document, .dk-history-card, .dk-source-head {
  border: 1px solid rgba(70,69,85,.72);
  background: linear-gradient(135deg, rgba(18,33,49,.92), rgba(13,28,45,.72));
  box-shadow: inset 0 1px 0 rgba(212,228,250,.035);
}
.dk-corpus-card {
  min-height: 178px;
  padding: 1rem;
  border-radius: 12px;
}
.dk-corpus-card__top {
  display:flex; justify-content:space-between; gap:1rem; align-items:flex-start;
}
.dk-corpus-card h3 { margin:.5rem 0 .35rem; font-size:20px; }
.dk-corpus-card p {
  min-height: 42px; margin:0 0 .8rem;
  color:rgba(199,196,216,.68); font-size:13px;
}
.dk-corpus-card__footer {
  display:flex; justify-content:space-between; align-items:center;
  padding-top:.75rem; border-top:1px solid rgba(70,69,85,.44);
  font:500 10px/1.4 "JetBrains Mono",monospace; color:var(--dk-outline);
}

.dk-status {
  display:inline-flex; align-items:center; gap:6px;
  padding: 4px 8px; border-radius:999px;
  background:rgba(78,222,163,.08);
  border:1px solid rgba(78,222,163,.22);
  color:var(--dk-success);
  font:600 9px/1.2 "JetBrains Mono",monospace;
  letter-spacing:.06em; text-transform:uppercase;
}
.dk-status::before {
  content:""; width:6px; height:6px; border-radius:50%;
  background:currentColor; box-shadow:0 0 10px currentColor;
}
.dk-status--partial { color:var(--dk-warning); background:rgba(255,182,149,.08); border-color:rgba(255,182,149,.24); }
.dk-status--empty { color:var(--dk-outline); background:rgba(145,143,161,.07); border-color:rgba(145,143,161,.20); }

.dk-document {
  display:grid;
  grid-template-columns: minmax(0, 1fr) repeat(4, minmax(78px, auto));
  align-items:center; gap:1rem;
  padding: .95rem 1rem;
  border-radius:10px;
  margin-bottom:8px;
}
.dk-document__name {
  display:flex;
  gap:.75rem;
  align-items:center;
  min-width:0;
  overflow:hidden;
}
.dk-document__name > div:last-child { min-width:0; overflow:hidden; }
.dk-file-icon {
  width:38px; height:38px; flex:0 0 38px;
  display:grid; place-items:center; border-radius:8px;
  color:var(--dk-primary);
  background:rgba(79,70,229,.16);
  border:1px solid rgba(195,192,255,.18);
  font:700 11px "JetBrains Mono",monospace;
}
.dk-document strong {
  display:block;
  max-width:100%;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  color:var(--dk-text); font:600 12px/1.4 "JetBrains Mono",monospace;
}
.dk-document small {
  display:block;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  color:var(--dk-outline);
  font-size:11px;
}
.dk-doc-stat label {
  display:block; color:var(--dk-outline);
  font:600 9px/1.3 "JetBrains Mono",monospace;
  letter-spacing:.06em; text-transform:uppercase;
}
.dk-doc-stat span { color:var(--dk-muted); font:500 12px/1.5 "JetBrains Mono",monospace; }

.dk-empty {
  padding:2.4rem 1.25rem; text-align:center;
  border:1px dashed rgba(145,143,161,.58); border-radius:12px;
  background:rgba(13,28,45,.46);
}
.dk-empty__icon {
  width:52px; height:52px; margin:0 auto .85rem;
  display:grid; place-items:center; border-radius:50%;
  background:var(--dk-high); color:var(--dk-primary);
  font:700 18px "JetBrains Mono",monospace;
}
.dk-empty h3 { margin:0 0 .3rem; font-size:18px; }
.dk-empty p { margin:0; color:rgba(199,196,216,.62); font-size:13px; }

.dk-source-head {
  display:flex; gap:.75rem; align-items:flex-start;
  padding:.75rem .85rem; margin:.35rem 0 .45rem;
  border-left:3px solid var(--dk-primary); border-radius:8px;
}
.dk-source-index {
  color:var(--dk-primary); font:700 11px/1.4 "JetBrains Mono",monospace;
}
.dk-source-copy { min-width:0; flex:1; }
.dk-source-copy strong {
  display:block; color:var(--dk-text);
  font:600 11px/1.4 "JetBrains Mono",monospace;
  overflow:hidden; white-space:nowrap; text-overflow:ellipsis;
}
.dk-source-copy p {
  margin:.3rem 0 0; color:rgba(199,196,216,.66);
  font-size:12px; line-height:1.5;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
}
.dk-page-chip {
  flex:0 0 auto; padding:4px 7px; border-radius:6px;
  background:rgba(195,192,255,.10); color:var(--dk-primary);
  border:1px solid rgba(195,192,255,.20);
  font:600 9px/1.2 "JetBrains Mono",monospace;
}
.dk-source-text {
  padding:.75rem; border-radius:8px; background:var(--dk-lowest);
  color:var(--dk-muted); font:400 12px/1.7 "JetBrains Mono",monospace;
}

.dk-history-card {
  padding:1rem; border-radius:11px; margin-bottom:8px;
}
.dk-history-card__top {
  display:flex; align-items:center; gap:.65rem; margin-bottom:.55rem;
}
.dk-history-card h3 { margin:0; flex:1; font-size:16px; }
.dk-history-card time {
  color:var(--dk-outline); font:500 10px "JetBrains Mono",monospace;
}
.dk-history-card p { margin:0; color:rgba(199,196,216,.68); font-size:13px; }
.dk-chip {
  display:inline-block; padding:4px 7px; border-radius:6px;
  color:var(--dk-primary); background:rgba(79,70,229,.12);
  border:1px solid rgba(195,192,255,.18);
  font:600 9px/1.2 "JetBrains Mono",monospace; text-transform:uppercase;
}

.dk-comparison-hero {
  margin: .4rem 0 1rem;
  padding: 1.15rem;
  border: 1px solid rgba(195,192,255,.20);
  border-radius: 14px;
  background:
    radial-gradient(circle at 85% 20%, rgba(79,70,229,.18), transparent 18rem),
    linear-gradient(145deg, rgba(18,33,49,.96), rgba(1,15,31,.72));
  box-shadow: 0 18px 48px rgba(1,15,31,.24), inset 0 1px 0 rgba(212,228,250,.045);
}
.dk-comparison-hero h2 {
  margin: .55rem 0 .4rem;
  font-size: clamp(22px, 3vw, 30px);
}
.dk-comparison-hero p {
  max-width: 980px;
  margin: 0;
  color: rgba(212,228,250,.78);
  font-size: 14px;
  line-height: 1.7;
}
.dk-comparison-docs {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:10px;
  margin: 0 0 1rem;
}
.dk-comparison-doc-pill {
  min-width:0;
  padding:.8rem .9rem;
  border:1px solid rgba(70,69,85,.72);
  border-radius:10px;
  background:rgba(13,28,45,.72);
}
.dk-comparison-doc-pill strong {
  display:block;
  overflow:hidden;
  white-space:nowrap;
  text-overflow:ellipsis;
  color:var(--dk-text);
  font:600 12px/1.4 "JetBrains Mono",monospace;
}
.dk-comparison-doc-pill span {
  display:block;
  margin-top:.25rem;
  color:var(--dk-outline);
  font-size:11px;
}
.dk-comparison-list {
  margin:.2rem 0 1rem;
  padding:0;
  display:grid;
  gap:.55rem;
  list-style:none;
}
.dk-comparison-list li {
  position:relative;
  padding:.7rem .8rem .7rem 2rem;
  border:1px solid rgba(70,69,85,.62);
  border-radius:9px;
  background:rgba(1,15,31,.48);
  color:rgba(212,228,250,.84);
  font-size:13px;
  line-height:1.55;
}
.dk-comparison-list li::before {
  content:"";
  position:absolute;
  left:.8rem;
  top:1.1rem;
  width:7px;
  height:7px;
  border-radius:50%;
  background:var(--dk-primary);
  box-shadow:0 0 12px rgba(195,192,255,.42);
}
.dk-evidence-timeline {
  display:grid;
  gap:.7rem;
  margin:.45rem 0 .3rem;
}
.dk-evidence-card {
  display:grid;
  grid-template-columns:10px minmax(0,1fr);
  gap:.65rem;
  align-items:stretch;
}
.dk-evidence-card__rail {
  width:2px;
  min-height:100%;
  margin:auto;
  border-radius:999px;
  background:linear-gradient(var(--dk-primary), var(--dk-success));
  box-shadow:0 0 18px rgba(195,192,255,.24);
}
.dk-evidence-card__body {
  min-width:0;
  padding:.75rem .85rem;
  border:1px solid rgba(70,69,85,.68);
  border-radius:10px;
  background:linear-gradient(135deg, rgba(1,15,31,.70), rgba(13,28,45,.62));
}
.dk-evidence-card__top {
  display:flex;
  justify-content:space-between;
  gap:.8rem;
  align-items:center;
}
.dk-evidence-card__top strong {
  min-width:0;
  overflow:hidden;
  white-space:nowrap;
  text-overflow:ellipsis;
  color:var(--dk-text);
  font:600 12px/1.4 "JetBrains Mono",monospace;
}
.dk-evidence-card__top span {
  flex:0 0 auto;
  color:var(--dk-success);
  font:600 10px/1.3 "JetBrains Mono",monospace;
}
.dk-evidence-meta {
  margin:.25rem 0 .55rem;
  color:var(--dk-outline);
  font:500 10px/1.5 "JetBrains Mono",monospace;
}
.dk-evidence-card details {
  color:rgba(212,228,250,.78);
  font-size:12px;
  line-height:1.65;
}
.dk-evidence-card summary {
  cursor:pointer;
  color:var(--dk-primary);
  font:600 11px/1.4 "JetBrains Mono",monospace;
}
.dk-evidence-card p {
  margin:.6rem 0 0;
  color:rgba(199,196,216,.82);
}
.dk-evidence-card mark {
  color:var(--dk-text);
  background:rgba(195,192,255,.18);
  border-radius:4px;
  padding:0 .15rem;
}
.dk-evidence-statement {
  margin:.7rem 0 .4rem;
  padding:.65rem .75rem;
  border:1px solid rgba(195,192,255,.16);
  border-radius:9px;
  background:rgba(79,70,229,.08);
  color:var(--dk-text);
  font-weight:600;
}
.dk-comparison-doc-card {
  min-width:0;
  padding:.9rem;
  margin:.2rem 0 .55rem;
  border:1px solid rgba(70,69,85,.72);
  border-radius:11px;
  background:linear-gradient(135deg, rgba(18,33,49,.90), rgba(13,28,45,.66));
}
.dk-comparison-doc-card h3 {
  margin:.45rem 0 0;
  overflow:hidden;
  white-space:nowrap;
  text-overflow:ellipsis;
  font-size:15px;
}
.dk-recommendation {
  padding:1rem;
  border:1px solid rgba(78,222,163,.20);
  border-left:3px solid var(--dk-success);
  border-radius:11px;
  background:linear-gradient(135deg, rgba(78,222,163,.08), rgba(13,28,45,.78));
  color:rgba(212,228,250,.88);
  font-size:14px;
  line-height:1.7;
}
.dk-comparison-ask-shell {
  margin:0 0 .85rem;
  padding:.85rem 1rem;
  border:1px solid rgba(195,192,255,.16);
  border-radius:11px;
  background:rgba(1,15,31,.44);
  color:rgba(199,196,216,.72);
  font-size:13px;
  line-height:1.6;
}

.dk-auth-shell {
  width:min(100%, 480px); margin:6vh auto 0;
  text-align:center; animation:dk-enter .4s ease both;
}
.dk-auth-loading {
  width:min(100%,460px);
  margin:22vh auto 0;
  text-align:center;
  animation:dk-enter .3s ease both;
}
.dk-auth-loading__mark {
  width:54px;
  height:54px;
  margin:0 auto 1rem;
  border-radius:14px;
  display:grid;
  place-items:center;
  color:var(--dk-primary);
  background:rgba(79,70,229,.14);
  border:1px solid rgba(195,192,255,.28);
  box-shadow:0 0 34px rgba(79,70,229,.18);
  font:700 22px "JetBrains Mono",monospace;
  animation:dk-pulse 1.4s ease-in-out infinite;
}
.dk-auth-loading h2 { margin:0 0 .45rem; font-size:22px; }
.dk-auth-loading p {
  margin:0;
  color:var(--dk-outline);
  font:500 10px/1.6 "JetBrains Mono",monospace;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.dk-auth-loading__bar {
  width:180px;
  height:3px;
  margin:1rem auto 0;
  overflow:hidden;
  border-radius:999px;
  background:var(--dk-highest);
}
.dk-auth-loading__bar::after {
  content:"";
  display:block;
  width:45%;
  height:100%;
  background:linear-gradient(90deg,var(--dk-success),var(--dk-primary));
  animation:dk-scan 1s ease-in-out infinite alternate;
}
.st-key-auth_show_signup button,
.st-key-auth_show_login button {
  min-height:auto !important;
  padding:.35rem !important;
  border:0 !important;
  background:transparent !important;
  box-shadow:none !important;
  color:var(--dk-muted) !important;
  font-size:13px !important;
}
.st-key-auth_show_signup button:hover,
.st-key-auth_show_login button:hover { color:var(--dk-primary) !important; }
.st-key-auth_show_signup button p,
.st-key-auth_show_login button p { color:inherit !important; }
.dk-auth-shell h1 { margin:0; color:var(--dk-primary); font-size:36px; }
.dk-auth-shell p {
  font:600 10px/1.5 "JetBrains Mono",monospace;
  color:var(--dk-muted); letter-spacing:.1em; text-transform:uppercase;
}
.dk-auth-marker { display:none; }
.st-key-auth_card {
  padding:1.55rem;
  margin-top:1.4rem;
  border:1px solid rgba(70,69,85,.78);
  border-radius:14px;
  background:linear-gradient(145deg,rgba(18,33,49,.96),rgba(13,28,45,.90));
  box-shadow:0 30px 80px rgba(1,15,31,.35), inset 0 1px 0 rgba(212,228,250,.04);
}
.dk-system-strip {
  width:min(100%,900px); margin:1.2rem auto 0; padding:.65rem .85rem;
  display:flex; justify-content:space-between; gap:1rem;
  border-top:1px solid rgba(70,69,85,.38);
  color:var(--dk-outline); font:500 9px/1.4 "JetBrains Mono",monospace;
  letter-spacing:.08em; text-transform:uppercase;
}
.dk-system-strip b { color:var(--dk-success); font-weight:500; }

@keyframes dk-enter {
  from { opacity:0; transform:translateY(8px); }
  to { opacity:1; transform:translateY(0); }
}
@keyframes dk-pulse {
  0%,100% { opacity:.7; } 50% { opacity:1; }
}
@keyframes dk-scan {
  from { transform:translateX(-105%); }
  to { transform:translateX(225%); }
}

@media (max-width: 1100px) {
  .dk-metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .dk-document { grid-template-columns:minmax(220px,1fr) repeat(2,minmax(80px,auto)); }
  .dk-document .dk-doc-stat:nth-last-child(-n+2) { display:none; }
}
@media (max-width: 900px) {
  .main .block-container { padding:1rem 1rem 5rem; }
  .dk-document { grid-template-columns:1fr auto; }
  .dk-document .dk-doc-stat { display:none; }
  .dk-comparison-docs { grid-template-columns:1fr; }
}
@media (max-width: 600px) {
  .dk-metric-grid { grid-template-columns:1fr; }
  .dk-metric-grid--2 { grid-template-columns:1fr; }
  .dk-page-header h1 { font-size:28px; }
  .dk-system-strip { display:none; }
  .st-key-auth_card { padding:1rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration:.01ms !important;
    animation-iteration-count:1 !important;
    transition-duration:.01ms !important;
  }
}
</style>
"""


def inject_styles() -> None:
    st.markdown(STITCH_CSS, unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <header class="dk-page-header">
          <div class="dk-eyebrow">{escape(eyebrow)}</div>
          <h1>{escape(title)}</h1>
          <p>{escape(description)}</p>
        </header>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, meta: str = "") -> None:
    st.markdown(
        f"""
        <div class="dk-section-title">
          <h2>{escape(title)}</h2>
          <span>{escape(meta)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_grid(metrics: list[tuple[str, str, str, Optional[str]]]) -> None:
    cards = []
    for label, value, meta, accent in metrics:
        modifier = f" dk-metric--{escape(accent)}" if accent else ""
        cards.append(
            f'<div class="dk-metric{modifier}">'
            f'<div class="dk-metric__label">{escape(label)}</div>'
            f'<div class="dk-metric__value">{escape(value)}</div>'
            f'<div class="dk-metric__meta">{escape(meta)}</div>'
            "</div>"
        )
    grid_class = f"dk-metric-grid dk-metric-grid--{min(len(metrics), 4)}"
    st.markdown(
        f'<div class="{grid_class}">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    normalized = status.lower()
    modifier = "" if normalized in {"indexed", "active", "connected"} else f" dk-status--{normalized}"
    return f'<span class="dk-status{modifier}">{escape(status)}</span>'


def empty_state(title: str, message: str, icon: str = "+") -> None:
    st.markdown(
        f"""
        <div class="dk-empty">
          <div class="dk-empty__icon">{escape(icon)}</div>
          <h3>{escape(title)}</h3>
          <p>{escape(message)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
