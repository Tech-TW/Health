# app.py
import streamlit as st
import pandas as pd
from utils import init_state, export_csv, metric_exists, page_link
from i18n import t, set_lang, get_lang

st.set_page_config(page_title=t("app.title"), page_icon="💚", layout="wide")
init_state()

# URL 語言參數
qp = st.query_params
if "lang" in qp:
    set_lang(qp["lang"])
else:
    set_lang(get_lang())

with st.sidebar:
    lang_options = [("zh-TW", t("common.lang_zh")), ("en", t("common.lang_en"))]
    idx_map = {"zh-TW":0, "en":1}
    cur = st.session_state.get("lang", "zh-TW")
    chosen = st.selectbox(
        t("common.language"),
        options=lang_options,
        index=idx_map.get(cur, 0),
        format_func=lambda x: x[1],
        key="lang_selector"
    )
    if chosen:
        set_lang(chosen[0])
        st.query_params["lang"] = chosen[0]

st.title("💚 " + t("app.title"))
st.caption(t("app.subtitle"))

bp_df = st.session_state.metrics.get("blood_pressure", pd.DataFrame())

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader(t("app.nav_bp"))
    if metric_exists("blood_pressure"):
        latest = bp_df.iloc[-1]
        st.metric(t("bp.latest_reading"),
                  f"{int(latest['systolic'])}/{int(latest['diastolic'])} mmHg",
                  f"Pulse {int(latest['pulse'])} bpm")
        page_link("pages/01_血壓紀錄.py", t("app.goto_bp"))
    else:
        st.write(t("app.no_data_export"))
        page_link("pages/01_血壓紀錄.py", t("app.add_one"))

with col2:
    st.subheader(t("app.nav_weight"))
    st.write("Coming soon")

with col3:
    st.subheader(t("app.nav_glucose"))
    st.write("Coming soon")

st.divider()
st.subheader(t("app.export_all"))
all_metrics = st.session_state.metrics
if len(all_metrics) == 0:
    st.info(t("app.no_data_export"))
else:
    frames = []
    for mname, df in all_metrics.items():
        tmp = df.copy()
        tmp["metric"] = mname
        frames.append(tmp)
    merged = pd.concat(frames, ignore_index=True)
    st.download_button(
        t("common.download_all"),
        data=export_csv(merged),
        file_name="health_hub_all.csv",
        mime="text/csv"
    )
