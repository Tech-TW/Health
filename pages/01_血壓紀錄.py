# pages/01_🩺_血壓紀錄.py
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from utils import (
    init_state, TZ, parse_local_datetime, export_csv,
    default_cfg_bp, normalize_bp_df
)
from i18n import t, get_lang

st.set_page_config(page_title=t("bp.page_title"), page_icon="🩺", layout="wide")
init_state()

METRIC = "blood_pressure"
if METRIC not in st.session_state.metrics:
    st.session_state.metrics[METRIC] = pd.DataFrame(
        columns=["datetime","systolic","diastolic","pulse","pp","map",
                 "category","cat_level","period","position","arm","place","meds","note"]
    )

# ---- 側欄：設定 / 匯入匯出 ----
with st.sidebar:
    st.header(t("bp.page_title"))
    cfg = st.session_state.cfg.get(METRIC, default_cfg_bp())
    c1, c2 = st.columns(2)
    with c1:
        cfg["target_sys"] = st.number_input(t("bp.target_sys"), 100, 200, cfg["target_sys"])
    with c2:
        cfg["target_dia"] = st.number_input(t("bp.target_dia"), 50, 140, cfg["target_dia"])
    st.session_state.cfg[METRIC] = cfg

    st.divider()
    st.subheader(t("bp.import_csv"))
    up = st.file_uploader(t("bp.import_csv"), type=["csv"], key="bp_uploader")
    if up is not None:
        try:
            df = pd.read_csv(up)
            new_df = normalize_bp_df(df)
            merged = pd.concat([st.session_state.metrics[METRIC], new_df], ignore_index=True)
            st.session_state.metrics[METRIC] = normalize_bp_df(merged)
            st.success(t("common.import_success", n=len(new_df)))
        except Exception as e:
            st.error(t("common.import_fail", msg=str(e)))

    st.subheader(t("bp.export_csv"))
    st.download_button(
        t("bp.export_csv"),
        data=export_csv(st.session_state.metrics[METRIC]),
        file_name="blood_pressure.csv",
        mime="text/csv"
    )

    st.divider()
    if st.button(t("bp.clear_all"), type="secondary"):
        st.session_state.metrics[METRIC] = st.session_state.metrics[METRIC].iloc[0:0]
        st.success(t("common.cleared"))

# ---- 主區 ----
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
            periods   = t("choices.periods")
            positions = t("choices.positions")
            arms      = t("choices.arms")
            places    = t("choices.places")
            period   = st.selectbox(t("bp.period"), periods, index=0)
            position = st.selectbox(t("bp.position"), positions, index=0)
            arm      = st.selectbox(t("bp.arm"), arms, index=0)
            place    = st.selectbox(t("bp.place"), places, index=0)
            meds     = st.text_input(t("bp.meds"), value="")
            note     = st.text_input(t("bp.note"), value="")
        if st.form_submit_button(t("bp.add_btn")):
            row = pd.DataFrame([{
                "datetime": parse_local_datetime(d, tv),
                "systolic": sys, "diastolic": dia, "pulse": pulse,
                "period": period, "position": position, "arm": arm, "place": place,
                "meds": meds, "note": note
            }])
            new = normalize_bp_df(row)
            merged = pd.concat([st.session_state.metrics[METRIC], new], ignore_index=True)
            st.session_state.metrics[METRIC] = normalize_bp_df(merged)
            st.success(t("common.added"))

df = st.session_state.metrics[METRIC].copy()
if df.empty:
    st.info(t("bp.no_data"))
    st.stop()

# 篩選
st.subheader(t("bp.filter"))
c1, c2, c3, c4 = st.columns(4)
with c1:
    min_date = df["datetime"].min().date(); max_date = df["datetime"].max().date()
    start = st.date_input(t("bp.start"), value=max_date - timedelta(days=30), min_value=min_date, max_value=max_date)
with c2:
    end = st.date_input(t("bp.end"), value=max_date, min_value=min_date, max_value=max_date)
with c3:
    period_pick = st.multiselect(t("bp.period"), sorted(df["period"].dropna().unique().tolist()), default=[])
with c4:
    place_pick = st.multiselect(t("bp.place"), sorted(df["place"].dropna().unique().tolist()), default=[])

mask = (df["datetime"].dt.date >= start) & (df["datetime"].dt.date <= end)
if period_pick: mask &= df["period"].isin(period_pick)
if place_pick:  mask &= df["place"].isin(place_pick)
view = df.loc[mask].copy()

# 指標摘要
st.subheader(t("bp.summary"))
if view.empty:
    st.warning(t("bp.no_view"))
else:
    last7  = view[view["datetime"] >= (view["datetime"].max() - pd.Timedelta(days=7))]
    last30 = view[view["datetime"] >= (view["datetime"].max() - pd.Timedelta(days=30))]

    def hit_rate(sub):
        if len(sub) == 0: return 0.0
        cfg = st.session_state.cfg[METRIC]
        return 100.0 * ((sub["systolic"] < cfg["target_sys"]) & (sub["diastolic"] < cfg["target_dia"])).mean()

    colA, colB, colC = st.columns(3)
    with colA: st.metric(t("bp.hit7"), f"{hit_rate(last7):.1f}%")
    with colB: st.metric(t("bp.hit30"), f"{hit_rate(last30):.1f}%")
    with colC:
        latest = view.iloc[-1]
        st.metric(t("bp.latest_reading"),
                  f"{int(latest['systolic'])}/{int(latest['diastolic'])} mmHg",
                  f"Pulse {int(latest['pulse'])} bpm")

    # 類別分布
    cat_counts = view["category"].value_counts().reset_index()
    cat_counts.columns = ["category","count"]
    cat_chart = alt.Chart(cat_counts).mark_bar().encode(
        x=alt.X("category:N", title=t("bp.cat_chart_title")),
        y=alt.Y("count:Q", title="Count"),
        tooltip=["category","count"]
    )
    st.altair_chart(cat_chart, use_container_width=True)

# 圖表
st.subheader(t("bp.ts_title"))
if not view.empty:
    long = view.melt(id_vars=["datetime","category","cat_level"],
                     value_vars=["systolic","diastolic"],
                     var_name="type", value_name="mmHg")

    rules = pd.DataFrame({
        "label": [t("bp.target_sys"), t("bp.target_dia")],
        "type":  ["systolic", "diastolic"],
        "mmHg":  [st.session_state.cfg[METRIC]["target_sys"],
                  st.session_state.cfg[METRIC]["target_dia"]],
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

    st.subheader(t("bp.hr_title"))
    pulse_chart = alt.Chart(view).mark_line(point=True).encode(
        x=alt.X("datetime:T", title="Time"),
        y=alt.Y("pulse:Q", title="bpm"),
        tooltip=[alt.Tooltip("datetime:T"), alt.Tooltip("pulse:Q")]
    )
    st.altair_chart(pulse_chart.interactive(), use_container_width=True)

# 明細
st.subheader(t("bp.table_title"))
show = view.copy()
try:
    show["日期時間" if get_lang()=="zh-TW" else "Datetime"] = show["datetime"].dt.tz_convert(TZ).dt.strftime("%Y-%m-%d %H:%M")
except Exception:
    show["datetime_str"] = pd.to_datetime(show["datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M")
cols_map = {
    "systolic": t("bp.systolic_short"),
    "diastolic": t("bp.diastolic_short"),
    "pulse": t("bp.pulse_short"),
    "pp": t("bp.pp"),
    "map": t("bp.map"),
    "category": t("bp.category"),
    "period": t("bp.period"),
    "position": t("bp.position"),
    "arm": t("bp.arm"),
    "place": t("bp.place"),
    "meds": t("bp.meds"),
    "note": t("bp.note")
}
disp_cols = [c for c in show.columns if c.endswith("時間") or c.lower().endswith("datetime")]
disp_cols += list(cols_map.keys())
show = show[disp_cols].rename(columns=cols_map)
st.dataframe(show, use_container_width=True, hide_index=True)

st.info(t("bp.tip"))
