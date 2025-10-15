# pages/90_資料與備份.py
import streamlit as st
import pandas as pd
from utils import export_csv
import db

st.set_page_config(page_title="📦 Data & Backup", page_icon="📦", layout="wide")
db.init_db()

def require_login():
    if "user" not in st.session_state or st.session_state["user"] is None:
        st.error("請先回首頁登入。")
        st.stop()
require_login()
USER_ID = st.session_state["user"]["id"]

st.title("📦 Data & Backup")

st.subheader("Export my data")
df_all = db.list_bp(USER_ID)
st.download_button("Download BP CSV", data=export_csv(df_all), file_name="blood_pressure.csv", mime="text/csv")

st.divider()
st.subheader("Import CSV (columns: datetime or date+time, systolic, diastolic, pulse, meds, note)")
up = st.file_uploader("Choose CSV", type=["csv"])
if up and st.button("Import"):
    try:
        raw = pd.read_csv(up)
        # 自動對應欄位（與 01_頁面相同邏輯）
        candidate_cols = {c.lower(): c for c in raw.columns}
        def pick(*names):
            for n in names:
                if n in candidate_cols: return candidate_cols[n]
            return None
        out = pd.DataFrame()
        if pick("datetime","日期時間"):
            out["datetime"] = pd.to_datetime(raw[pick("datetime","日期時間")], errors="coerce")
        else:
            dcol, tcol = pick("date","日期"), pick("time","時間")
            out["datetime"] = pd.to_datetime(raw[dcol] + " " + raw[tcol], errors="coerce") if dcol and tcol else pd.NaT
        out["systolic"]  = pd.to_numeric(raw.get(pick("systolic","收縮壓","sys"), pd.NA), errors="coerce")
        out["diastolic"] = pd.to_numeric(raw.get(pick("diastolic","舒張壓","dia"), pd.NA), errors="coerce")
        out["pulse"]     = pd.to_numeric(raw.get(pick("pulse","心跳","hr","脈搏"), pd.NA), errors="coerce")
        out["meds"]      = raw.get(pick("meds","服藥"), "")
        out["note"]      = raw.get(pick("note","備註"), "")
        out = out.dropna(subset=["datetime","systolic","diastolic","pulse"])
        for _, r in out.iterrows():
            db.add_bp(USER_ID, {
                "datetime": pd.to_datetime(r["datetime"]).strftime("%Y-%m-%d %H:%M:%S"),
                "systolic": float(r["systolic"]),
                "diastolic": float(r["diastolic"]),
                "pulse": float(r["pulse"]),
                "meds": str(r.get("meds","")) if pd.notna(r.get("meds","")) else "",
                "note": str(r.get("note","")) if pd.notna(r.get("note","")) else "",
            })
        st.success(f"Imported {len(out)} rows.")
    except Exception as e:
        st.error(f"Import failed: {e}")

st.divider()
st.subheader("Reset my data (irreversible)")
if st.button("Delete ALL my BP records", type="secondary"):
    ids = db.list_bp(USER_ID)["id"].tolist()
    db.delete_bp(USER_ID, ids)
    st.success("Deleted.")
