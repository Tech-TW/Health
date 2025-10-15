# app.py
import streamlit as st

# ── 若 import 失敗，直接在頁面顯示詳細錯誤（方便排查）
try:
    from i18n import t, set_lang, get_lang
except Exception as e:
    import traceback
    st.error("匯入 i18n 失敗，請確認 i18n.py 是否存在且無語法錯誤。")
    st.code(traceback.format_exc())
    raise

try:
    from utils import init_state  # 本頁只需初始化與語言；其他計算在子頁使用
except Exception as e:
    import traceback
    st.error("匯入 utils 失敗，請確認 utils.py 是否在專案根目錄，且 requirements 已安裝齊全。")
    st.code(traceback.format_exc())
    raise

try:
    import db  # 使用 SQLite + Argon2 登入
except Exception as e:
    import traceback
    st.error("匯入 db 失敗，請確認 db.py 是否在專案根目錄，且無語法錯誤。")
    st.code(traceback.format_exc())
    raise


# ---------------- 基本設定 ----------------
st.set_page_config(page_title=t("app.title"), page_icon="💚", layout="wide")
init_state()
db.init_db()  # 確保 DB schema 存在


# ---------------- 語言處理（URL 參數 & 側欄選擇） ----------------
qp = st.query_params
if "lang" in qp:
    set_lang(qp["lang"])
else:
    set_lang(get_lang())

with st.sidebar:
    lang_options = [("zh-TW", t("common.lang_zh")), ("en", t("common.lang_en"))]
    idx_map = {"zh-TW": 0, "en": 1}
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


# ---------------- 登入狀態工具 ----------------
def logged_in() -> bool:
    return "user" in st.session_state and st.session_state["user"] is not None


# ---------------- 側邊欄：帳號登入/註冊 ----------------
with st.sidebar:
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

        # ---- Login ----
        with tab_login:
            email = st.text_input("Email", key="login_email")
            pwd = st.text_input("Password", type="password", key="login_pwd")
            if st.button("Login"):
                user = db.get_user_by_email(email)
                if user and db.verify_password(pwd, user["password_hash"]):
                    # 自動升級舊雜湊到 Argon2（如果需要）
                    db.maybe_upgrade_password(user["id"], pwd, user["password_hash"])
                    st.session_state["user"] = {
                        "id": user["id"], "email": user["email"], "name": user["name"]
                    }
                    st.rerun()
                else:
                    st.error("Invalid email or password")

        # ---- Sign up ----
        with tab_signup:
            email2 = st.text_input("Email (sign up)", key="signup_email")
            name2 = st.text_input("Display name", key="signup_name")
            pwd2 = st.text_input("Password (min 6)", type="password", key="signup_pwd")
            if st.button("Create account"):
                if len(pwd2) < 6:
                    st.error("Password too short.")
                else:
                    try:
                        uid = db.create_user(email2, name2 or email2.split("@")[0], pwd2)  # Argon2，無 72 bytes 限制
                        st.success("Account created. Please login.")
                    except Exception as e:
                        st.error(f"Sign up failed: {e}")


# ---------------- 首頁內容 ----------------
st.title("💚 " + t("app.title"))
st.caption(t("app.subtitle"))

if not logged_in():
    st.info("請先在左側完成登入或註冊；登入後即可管理你的血壓紀錄。")
    st.stop()

u = st.session_state["user"]
st.success(f"已登入：{u['name']}")

# 主要導覽
col1, col2 = st.columns(2)
with col1:
    st.page_link("pages/01_血壓紀錄.py", label="🩺 進入血壓紀錄", use_container_width=True)
with col2:
    st.page_link("pages/90_資料與備份.py", label="📦 資料與備份", use_container_width=True)

st.divider()
st.markdown(
    """
- 新增/編輯/刪除血壓：請進入「🩺 血壓紀錄」頁  
- 匯入/匯出：請到「📦 資料與備份」頁  
- 多使用者：各帳號只看得到自己的資料
"""
)
