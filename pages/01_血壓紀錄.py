# pages/01_血壓紀錄.py
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from utils import (
    init_state, TZ, export_csv, default_cfg_bp, enrich_bp
)
from i18n import t, get_lang
import db

st.set_page_config(page_title=t("bp.page_title"), page_icon="🩺", layout="wide")
init_state()
db.init_db()

def require_login():
    if "user" not in st.session_state or st.session_state["user"] is None:
        st.error("請先回首頁登入。")
        st.stop()
require_login()
USER_ID = st.session_state["user"]["id"]

# 側欄：設定/匯出
with st.sidebar:
    st.header("⚙️ 設定")
    cfg = st.session_state.cfg.get("blood_pressure", default_cfg_bp())
    c1, c2 = st.columns(2)
    with c1:
        cfg["target_sys"] = st.number_input(t("bp.target_sys"), 100, 200, cfg["target_sys"])
    with c2:
        cfg["target_dia"] = st.number_input(t("bp.target_dia"), 50, 140, cfg["target_dia"])
    st.session_state.cfg["blood_pressure"] = cfg

    st.divider()
    st.subheader(t("bp.export_csv"))
    if st.button("Export my BP CSV"):
        df_all = db.list_bp(USER_ID)
        st.download_button(
            label=t("bp.export_csv"),
            data=export_csv(df_all),
            file_name="blood_pressure.csv",
            mime="text/csv"
        )

st.title(t("bp.page_title"))
st.caption(t("bp.disclaimer"))

# 新增紀錄
with st.expander(t("bp.add_panel"), expanded=True):
    with st.form("add_bp", clear_on_submit=True):
        left, right = st.columns([2,3])
        with left:
            d = st.date_input(t("bp.date"), value=datetime.now(TZ).date())
            tv = st.time_input(t("bp.time"), value=datetime.now(TZ).time().replace(microsecond=0))
            sys  = st.number_input(t("bp.systolic"), 60, 260, 120)
            dia  = st.number_input(t("bp.diastolic"), 40, 160, 80)
            pulse= st.number_input(t("bp.pulse"), 30, 200, 70)
        with right:
            meds = st.text_input(t("bp.meds"), value="")
            note = st.text_input(t("bp.note"), value="")
        if st.form_submit_button(t("bp.add_btn")):
            db.add_bp(USER_ID, {
                "datetime": datetime.combine(d, tv).strftime("%Y-%m-%d %H:%M:%S"),
                "systolic": sys, "diastolic": dia, "pulse": pulse,
                "meds": meds, "note": note
            })
            st.success("Added!")

# 取資料（僅此用戶）
raw_df = db.list_bp(USER_ID)
if raw_df.empty:
    st.info(t("bp.no_data"))
    st.stop()
df = enrich_bp(raw_df)

# 篩選（僅日期）
st.subheader(t("bp.filter"))
df_dt = pd.to_datetime(df["datetime"], errors="coerce")
min_date = df_dt.dropna().min().date()
max_date = df_dt.dropna().max().date()
default_start = max(min_date, max_date - timedelta(days=30))

c1, c2 = st.columns(2)
with c1:
    start = st.date_input(t("bp.start"), value=default_start, min_value=min_date, max_value=max_date)
with c2:
    end = st.date_input(t("bp.end"), value=max_date, min_value=min_date, max_value=max_date)

mask = (df_dt.dt.date >= start) & (df_dt.dt.date <= end)
view = df.loc[mask].copy()
if view.empty:
    st.warning(t("bp.no_view"))
    st.stop()

# 摘要
st.subheader(t("bp.summary"))
last7  = view[view["datetime"] >= (view["datetime"].max() - pd.Timedelta(days=7))]
last30 = view[view["datetime"] >= (view["datetime"].max() - pd.Timedelta(days=30))]
def hit_rate(sub):
    if len(sub) == 0: return 0.0
    cfg = st.session_state.cfg["blood_pressure"]
    return 100.0 * ((sub["systolic"] < cfg["target_sys"]) & (sub["diastolic"] < cfg["target_dia"])).mean()
cA, cB, cC = st.columns(3)
with cA: st.metric(t("bp.hit7"), f"{hit_rate(last7):.1f}%")
with cB: st.metric(t("bp.hit30"), f"{hit_rate(last30):.1f}%")
with cC:
    latest = view.iloc[-1]
    st.metric(t("bp.latest_reading"), f"{int(latest['systolic'])}/{int(latest['diastolic'])} mmHg", f"Pulse {int(latest['pulse'])} bpm")

# 分布與圖表
cat_counts = view["category"].value_counts().reset_index()
cat_counts.columns = ["category","count"]
st.altair_chart(
    alt.Chart(cat_counts).mark_bar().encode(
        x=alt.X("category:N", title=t("bp.cat_chart_title")),
        y=alt.Y("count:Q", title="Count"),
        tooltip=["category","count"]
    ),
    use_container_width=True
)

st.subheader(t("bp.ts_title"))
long = view.melt(id_vars=["datetime","category","cat_level"], value_vars=["systolic","diastolic"], var_name="type", value_name="mmHg")
rules = pd.DataFrame({
    "label": [t("bp.target_sys"), t("bp.target_dia")],
    "type":  ["systolic", "diastolic"],
    "mmHg":  [st.session_state.cfg["blood_pressure"]["target_sys"], st.session_state.cfg["blood_pressure"]["target_dia"]],
})
line = alt.Chart(long).mark_line(point=True).encode(
    x=alt.X("datetime:T", title="Time"),
    y=alt.Y("mmHg:Q", title="mmHg"),
    color=alt.Color("type:N", title="Type"),
    tooltip=[alt.Tooltip("datetime:T", title="Time"),
             alt.Tooltip("type:N", title="Type"),
             alt.Tooltip("mmHg:Q", title="mmHg"),
             "category"]
)
rule = alt.Chart(rules).mark_rule(strokeDash=[4,4]).encode(y="mmHg:Q", color=alt.Color("type:N", legend=None))
st.altair_chart((line + rule).interactive(), use_container_width=True)

st.subheader(t("bp.hr_title"))
st.altair_chart(
    alt.Chart(view).mark_line(point=True).encode(
        x=alt.X("datetime:T", title="Time"),
        y=alt.Y("pulse:Q", title="bpm"),
        tooltip=[alt.Tooltip("datetime:T"), alt.Tooltip("pulse:Q")]
    ).interactive(),
    use_container_width=True
)

# 明細 + 編輯/刪除（僅自己資料）
st.subheader("📝 編輯 / 刪除")
edit_df = view[["id","datetime","systolic","diastolic","pulse","meds","note"]].copy()
edit_df["datetime"] = pd.to_datetime(edit_df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
edited = st.data_editor(
    edit_df, num_rows="fixed", hide_index=True, use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "datetime": st.column_config.TextColumn("Datetime (YYYY-MM-DD HH:MM:SS)"),
        "systolic": st.column_config.NumberColumn("Systolic", step=1),
        "diastolic": st.column_config.NumberColumn("Diastolic", step=1),
        "pulse": st.column_config.NumberColumn("Pulse", step=1),
        "meds": st.column_config.TextColumn("Medication"),
        "note": st.column_config.TextColumn("Note"),
    },
    key="editor_bp"
)

c1, c2 = st.columns(2)
with c1:
    if st.button("儲存表格變更", type="primary"):
        merged = edited.merge(edit_df, on="id", suffixes=("", "_old"))
        changed = merged[
            (merged["datetime"] != merged["datetime_old"]) |
            (merged["systolic"]  != merged["systolic_old"]) |
            (merged["diastolic"] != merged["diastolic_old"]) |
            (merged["pulse"]     != merged["pulse_old"]) |
            (merged["meds"]      != merged["meds_old"]) |
            (merged["note"]      != merged["note_old"])
        ]
        for _, r in changed.iterrows():
            db.update_bp(USER_ID, int(r["id"]), {
                "datetime": str(r["datetime"]),
                "systolic": float(r["systolic"]),
                "diastolic": float(r["diastolic"]),
                "pulse": float(r["pulse"]),
                "meds": r["meds"] or "",
                "note": r["note"] or "",
            })
        st.success("已儲存變更。")
with c2:
    to_del = st.multiselect("勾選欲刪除的列（ID）", options=edited["id"].tolist())
    if st.button("刪除勾選列") and to_del:
        db.delete_bp(USER_ID, [int(x) for x in to_del])
        st.success(f"已刪除 {len(to_del)} 筆。")
