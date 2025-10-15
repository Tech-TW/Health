# app.py
import streamlit as st
import pandas as pd
from utils import init_state, export_csv
from i18n import t, set_lang, get_lang
import db

st.set_page_config(page_title=t("app.title"), page_icon="💚", layout="wide")
init_state()
db.init_db()

# 語言（可保留）
qp = st.query_params
if "lang" in qp: set_lang(qp["lang"])
else: set_lang(get_lang())

# ------------- Auth 區塊 -------------
def logged_in() -> bool:
    return "user" in st.session_state and st.session_state["user"] is not None

with st.sidebar:
    lang_options = [("zh-TW", "繁中"), ("en", "English")]
    idx_map = {"zh-TW":0, "en":1}
    cur = st.session_state.get("lang", "zh-TW")
    chosen = st.selectbox("Language / 語言", options=lang_options, index=idx_map.get(cur,0), format_func=lambda x:x[1])
    set_lang(chosen[0])
    st.query_params["lang"] = chosen[0]

    st.divider()
    st.header("Account")
    if logged_in():
        u = st.session_state["user"]
        st.success(f"Hi, {u['name']} ({u['email']})")
        if st.button("Logout"):
            st.session_state.pop("user", None)
            st.rerun()
    else:
        tab_login, tab_signup = st.tabs(["Login", "Sign up"])
        with tab_login:
            email = st.text_input("Email", key="login_email")
            pwd   = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Login"):
                user = db.get_user_by_email(email)
                if user and db.verify_password(pwd, user["password_hash"]):
                    st.session_state["user"] = {"id": user["id"], "email": user["email"], "name": user["name"]}
                    st.rerun()
                else:
                    st.error("Invalid email or password")
        with tab_signup:
            email2 = st.text_input("Email (sign up)", key="signup_email")
            name2  = st.text_input("Display name", key="signup_name")
            pwd2   = st.text_input("Password (min 6)", type="password", key="signup_pwd")
            if st.button("Create account"):
                if len(pwd2) < 6:
                    st.error("Password too short.")
                else:
                    try:
                        uid = db.create_user(email2, name2 or email2.split("@")[0], pwd2)  # ← 不再報 72 bytes
                        st.success("Account created. Please login.")
                    except Exception as e:
                        st.error(f"Sign up failed: {e}")


st.title("💚 " + t("app.title"))
st.caption(t("app.subtitle"))

if not logged_in():
    st.info("請先在左側完成登入或註冊；登入後即可管理你的血壓紀錄。")
    st.stop()

u = st.session_state["user"]
st.success(f"已登入：{u['name']}")

col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/01_血壓紀錄.py", label="🩺 進入血壓紀錄", use_container_width=True)
with col2:
    st.page_link("pages/90_資料與備份.py", label="📦 資料與備份", use_container_width=True)
