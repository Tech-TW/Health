# app.py
import streamlit as st
import traceback

# ── DEBUG：僅在 secrets 設 True 時才顯示 traceback
DEBUG = bool(st.secrets.get("DEBUG", False))

# ── 若 import 失敗：對用戶顯示通用錯誤；除非 DEBUG 才顯示細節
try:
    from i18n import t, set_lang, get_lang
except Exception:
    st.error("系統載入失敗，請稍後再試。")
    if DEBUG:
        st.code(traceback.format_exc())
    raise

try:
    from utils import init_state  # 僅初始化與語言
except Exception:
    st.error("系統載入失敗，請稍後再試。")
    if DEBUG:
        st.code(traceback.format_exc())
    raise

try:
    import db  # SQLite + Argon2
except Exception:
    st.error("系統載入失敗，請稍後再試。")
    if DEBUG:
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

# ---------------- 簡易登入速率限制 ----------------
from datetime import datetime, timedelta

def _rl_key(email: str) -> str:
    return f"rl::{(email or '').strip().lower()}"

def check_rate_limit(email: str) -> bool:
    """回傳 True 表示允許嘗試；False 表示被鎖定"""
    now = datetime.utcnow()
    rl = st.session_state.get(_rl_key(email), {"count": 0, "until": None})
    until = rl.get("until")
    if until and now < until:
        return False
    return True

def register_fail(email: str, max_fail=5, window_min=5, lock_min=15):
    now = datetime.utcnow()
    key = _rl_key(email)
    rl = st.session_state.get(key, {"count": 0, "first": now, "until": None})
    until = rl.get("until")
    # 若解鎖時間已過，重置
    if until and now >= until:
        rl = {"count": 0, "first": now, "until": None}
    # 視窗重置
    first = rl.get("first", now)
    if now - first > timedelta(minutes=window_min):
        rl = {"count": 0, "first": now, "until": None}
    rl["count"] = rl.get("count", 0) + 1
    if rl["count"] >= max_fail:
        rl["until"] = now + timedelta(minutes=lock_min)
        rl["count"] = 0
        rl["first"] = now
    st.session_state[key] = rl

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
                if not check_rate_limit(email):
                    st.error("嘗試過多，請稍後再試。")
                else:
                    user = db.get_user_by_email(email)
                    ok = False
                    if user and db.verify_password(pwd, user["password_hash"]):
                        ok = True
                    if ok:
                        # 自動升級舊雜湊到 Argon2（如果需要）
                        db.maybe_upgrade_password(user["id"], pwd, user["password_hash"])
                        st.session_state["user"] = {
                            "id": user["id"], "email": user["email"], "name": user["name"]
                        }
                        st.rerun()
                    else:
                        # 統一訊息，避免帳號枚舉
                        st.error("Email 或密碼錯誤。")
                        register_fail(email)

        # ---- Sign up ----
        with tab_signup:
            email2 = st.text_input("Email (sign up)", key="signup_email")
            name2 = st.text_input("Display name", key="signup_name")
            pwd2 = st.text_input("Password (min 10, 強度需達標)", type="password", key="signup_pwd")
            if st.button("Create account"):
                # 密碼政策：≥10 且至少三類：大、小、數字、符號
                import re
                def strong(p: str) -> bool:
                    if len(p) < 10: return False
                    classes = sum(bool(re.search(r, p)) for r in [r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"])
                    return classes >= 3
                if not strong(pwd2):
                    st.error("密碼強度不足（至少 10 碼，含大小寫/數字/符號三類）。")
                else:
                    try:
                        uid = db.create_user(email2, name2 or email2.split("@")[0], pwd2)
                        st.success("Account created. Please login.")
                    except Exception:
                        # 不回傳具體錯誤，避免 email 枚舉
                        st.error("Sign up failed. Please check your info or try again later.")

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
