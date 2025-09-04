import streamlit as st

CSS = """
<style>
/* Tarjetas y botones */
.block-card {background: #0f172a; border: 1px solid #1f2937; padding: 16px; border-radius: 16px; box-shadow: 0 2px 12px rgba(0,0,0,.15);}
.badge {display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; background:#111827; border:1px solid #374151;}
.badge.green{background:#064e3b;border-color:#065f46;color:#d1fae5}
.badge.amber{background:#78350f;border-color:#92400e;color:#fde68a}
.badge.red{background:#7f1d1d;border-color:#991b1b;color:#fecaca}
.table-note {opacity:.8; font-size:12px; margin-top:6px}
input, textarea, select { border-radius: 10px !important; }
</style>
"""

def load_base_css():
    st.markdown(CSS, unsafe_allow_html=True)

def badge(text: str, color: str = ""):
    st.markdown(f'<span class="badge {color}">{text}</span>', unsafe_allow_html=True)
