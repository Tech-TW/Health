# pages/01_血壓紀錄.py
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
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

# ── 安全：文字淨化與長度限制
def sanitize_text(s: str | None, max_len=120) -> str:
    if not s: return ""
    s = str(s).strip()[:max_len]
    low = s.lower()
    banned = ["<script", "</", "javascript:", "data:", "vbscript:", "onerror", "onload", "http://", "https://"]
    if any(b in low for b in banned):
        return "[redacted]"
    return s

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
    # 直接提供下載按鈕（不經 st.button），檔名包含時間戳
    df_all = db.list_bp(USER_ID)
    if not df_all.empty:
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        st.download_button(
            label=t("bp.export_csv"),
            data=df_all.to_csv(index=False).encode("utf-8"),
            file_name=f"blood_pressure_{ts}.csv",
            mime="text/csv",
            use_container_width=True
        )

st.title(t("bp.page_title"))
st.caption(t("bp.disclaimer"))

# 新增紀錄（日期、時間、SYS、DIA、Pulse、服藥、備註）
with st.expander(t("bp.add_panel"), expanded=True):
    with st.form("add_bp", clear_on_submit=True):
        left, right = st.columns([2,3])
        with left:
            local_now = datetime.now(TZ)
            d = st.date_input(t("bp.date"), value=local_now.date())
            tv = st.time_input(t("bp.time"), value=local_now.time().replace(microsecond=0))
            sys  = st.number_input(t("bp.systolic"), 60, 260, 120)
            dia  = st.number_input(t("bp.diastolic"), 40, 160, 80)
            pulse= st.number_input(t("bp.pulse"), 30, 220, 70)
        with right:
            meds = sanitize_text(st.text_input(t("bp.meds"), value=""), max_len=50)
            note = sanitize_text(st.text_input(t("bp.note"), value=""), max_len=120)

        if st.form_submit_button(t("bp.add_btn")):
            # 轉 UTC ISO8601（儲存一律 UTC）
            local_dt = TZ.localize(datetime.combine(d, tv)) if getattr(TZ, 'localize', None) else datetime.combine(d, tv).astimezone(TZ)
            utc_dt = local_dt.astimezone(pd.Timestamp.utcnow().tz)
            dt_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            db.add_bp(USER_ID, {
                "datetime": dt_iso,
                "systolic": float(sys), "diastolic": float(dia), "pulse": float(pulse),
                "meds": meds, "note": note
            })
            st.success("Added!")
            st.rerun()  # 立刻刷新

# 取資料（僅此用戶）
raw_df = db.list_bp(USER_ID)
if raw_df.empty:
    st.info(t("bp.no_data"))
    st.stop()

# 將 datetime 解析為帶時區的 Timestamp（UTC → 本地顯示時再轉）
df = raw_df.copy()
df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
df = enrich_bp(df)  # 你原有的衍生欄位（pp、map、category 等）

# —— 篩選（允許任意日期；預設起日 = 資料最早日期） ——
st.subheader(t("bp.filter"))
df_dt = df["datetime"].dt.tz_convert(TZ)
min_date = df_dt.dropna().min().date()
max_date = df_dt.dropna().max().date()
default_start = min_date

c1, c2 = st.columns(2)
with c1:
    start = st.date_input(t("bp.start"), value=default_start)
with c2:
    end = st.date_input(t("bp.end"), value=max_date)

if start > end:
    start, end = end, start

mask = (df_dt.dt.date >= start) & (df_dt.dt.date <= end)
view = df.loc[mask].copy()
if view.empty:
    st.warning(t("bp.no_view"))
    st.stop()

# 指標摘要
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

# 類別分布
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

# 收縮/舒張壓時間序列 + 目標線
st.subheader(t("bp.ts_title"))
long = view.melt(
    id_vars=["datetime","category","cat_level"],
    value_vars=["systolic","diastolic"],
    var_name="type", value_name="mmHg"
)
rules = pd.DataFrame({
    "label": [t("bp.target_sys"), t("bp.target_dia")],
    "type":  ["systolic", "diastolic"],
    "mmHg":  [st.session_state.cfg["blood_pressure"]["target_sys"],
              st.session_state.cfg["blood_pressure"]["target_dia"]],
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
rule = alt.Chart(rules).mark_rule(strokeDash=[4,4]).encode(
    y="mmHg:Q",
    color=alt.Color("type:N", legend=None),
    tooltip=["label","mmHg"]
)
st.altair_chart((line + rule).interactive(), use_container_width=True)

# 心跳
st.subheader(t("bp.hr_title"))
st.altair_chart(
    alt.Chart(view).mark_line(point=True).encode(
        x=alt.X("datetime:T", title="Time"),
        y=alt.Y("pulse:Q", title="bpm"),
        tooltip=[alt.Tooltip("datetime:T"), alt.Tooltip("pulse:Q")]
    ).interactive(),
    use_container_width=True
)

# 明細表（本地時區顯示）
st.subheader(t("bp.table_title"))
disp = view.copy()
label_dt = "日期時間" if get_lang()=="zh-TW" else "Datetime"
disp[label_dt] = disp["datetime"].dt.tz_convert(TZ).dt.strftime("%Y-%m-%d %H:%M")
disp = disp[["id", label_dt, "systolic", "diastolic", "pulse", "pp", "map", "category", "meds", "note"]]
st.dataframe(
    disp.rename(columns={
        "systolic": t("bp.systolic_short"),
        "diastolic": t("bp.diastolic_short"),
        "pulse": t("bp.pulse_short"),
        "pp": t("bp.pp"),
        "map": t("bp.map"),
        "category": t("bp.category"),
        "meds": t("bp.meds"),
        "note": t("bp.note"),
    }),
    use_container_width=True, hide_index=True
)

# 編輯/刪除
st.subheader("📝 編輯 / 刪除")
edit_df = view[["id","datetime","systolic","diastolic","pulse","meds","note"]].copy()
# 編輯用字串（本地時區可視需求轉換；此處維持 ISO UTC 字串以避免混亂）
edit_df["datetime"] = pd.to_datetime(edit_df["datetime"], utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
edited = st.data_editor(
    edit_df, num_rows="fixed", hide_index=True, use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "datetime": st.column_config.TextColumn("Datetime (YYYY-MM-DD HH:MM:SS, UTC)"),
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
            # 重新淨化
            meds_upd = sanitize_text(r["meds"] or "", max_len=50)
            note_upd = sanitize_text(r["note"] or "", max_len=120)
            # 轉回 ISO UTC
            try:
                dt_utc = pd.to_datetime(r["datetime"], utc=True, errors="coerce")
                dt_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(dt_utc) else None
            except Exception:
                dt_iso = None
            fields = {}
            if dt_iso: fields["datetime"] = dt_iso
            fields["systolic"]  = float(r["systolic"])
            fields["diastolic"] = float(r["diastolic"])
            fields["pulse"]     = float(r["pulse"])
            fields["meds"]      = meds_upd
            fields["note"]      = note_upd
            db.update_bp(USER_ID, int(r["id"]), fields)
        st.success("已儲存變更。")
with c2:
    to_del = st.multiselect("勾選欲刪除的列（ID）", options=edited["id"].tolist())
    if st.button("刪除勾選列") and to_del:
        db.delete_bp(USER_ID, [int(x) for x in to_del])
        st.success(f"已刪除 {len(to_del)} 筆。")
