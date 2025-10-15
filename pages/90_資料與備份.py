# pages/90_📦_資料與備份.py
import streamlit as st
import pandas as pd
from utils import init_state, export_csv, normalize_bp_df
from i18n import t

st.set_page_config(page_title="📦 Data & Backup", page_icon="📦", layout="wide")
init_state()

st.title("📦 Data & Backup")

st.subheader(t("app.export_all"))
if len(st.session_state.metrics) == 0:
    st.info(t("app.no_data_export"))
else:
    frames = []
    for mname, df in st.session_state.metrics.items():
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

st.divider()
st.subheader("Import from CSV (now supports: Blood Pressure)")
up = st.file_uploader("Choose CSV", type=["csv"])
metric_sel = st.selectbox("Import to module", ["blood_pressure"], index=0)
if up and st.button("Import"):
    try:
        df = pd.read_csv(up)
        if metric_sel == "blood_pressure":
            df = normalize_bp_df(df)
        st.session_state.metrics[metric_sel] = df.sort_values("datetime").reset_index(drop=True)
        st.success(t("common.import_success", n=len(df)))
    except Exception as e:
        st.error(t("common.import_fail", msg=str(e)))

st.divider()
st.subheader("Reset all data (irreversible)")
if st.button("Clear ALL modules", type="secondary"):
    st.session_state.metrics = {}
    st.success(t("common.cleared"))
