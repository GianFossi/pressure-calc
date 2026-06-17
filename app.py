import streamlit as st
import streamlit.components.v1 as components
import base64
from pathlib import Path

# ── Page config (must be the very first Streamlit call) ────────────────────────
st.set_page_config(
    page_title="Pressure Vessel Calculator",
    page_icon="🔩",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Background plant image (base64-injected so it works locally + on Cloud) ────
def _bg_image_css() -> str:
    img = Path(__file__).parent / "static" / "bg_plant.jpg"
    if not img.exists():
        return ""
    data = base64.b64encode(img.read_bytes()).decode()
    return (
        ".stApp {"
        f' background-image: url("data:image/jpeg;base64,{data}") !important;'
        " background-size: cover !important;"
        " background-position: center center !important;"
        " background-attachment: fixed !important;"
        " background-repeat: no-repeat !important;"
        "}"
    )

_BG_CSS = _bg_image_css()
if _BG_CSS:
    st.markdown(f"<style>{_BG_CSS}</style>", unsafe_allow_html=True)

# ── Global CSS + persistent top banner ────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ═══════════════════════════════════════════════════════════
       1.  Hide / reset default Streamlit chrome
    ═══════════════════════════════════════════════════════════ */
    header[data-testid="stHeader"]     { display: none !important; }
    #MainMenu                          { display: none !important; }
    footer                             { display: none !important; }
    div[data-testid="stStatusWidget"]  { display: none !important; }

    /* ═══════════════════════════════════════════════════════════
       2.  Fixed top banner  (title + revision + author)
    ═══════════════════════════════════════════════════════════ */
    .pvc-banner {
        position: fixed;
        top: 0; left: 0; right: 0;
        height: 52px;
        background: linear-gradient(90deg, #12213d 0%, #1f6aa5 100%);
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 24px 0 18px;
        z-index: 999999;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
        border-bottom: 1px solid rgba(255, 255, 255, 0.10);
        font-family: "Source Sans Pro", "Helvetica Neue", Arial, sans-serif;
    }
    .pvc-banner-left {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .pvc-banner-icon {
        font-size: 1.35rem;
        line-height: 1;
    }
    .pvc-banner-title {
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.3px;
        white-space: nowrap;
    }
    /* ── Revision badge ── */
    .pvc-banner-rev {
        font-size: 0.68rem;
        font-weight: 500;
        letter-spacing: 0.5px;
        opacity: 0.80;
        background: rgba(255, 255, 255, 0.13);
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 4px;
        padding: 2px 8px;
        white-space: nowrap;
    }
    .pvc-banner-author {
        font-size: 0.76rem;
        opacity: 0.75;
        font-style: italic;
        white-space: nowrap;
    }
    @media (max-width: 640px) {
        .pvc-banner-author { display: none; }
        .pvc-banner-rev    { display: none; }
    }

    /* ═══════════════════════════════════════════════════════════
       3.  Sidebar  — push it below the banner + always-visible
           separator (same approach as Claude's sidebar divider)
    ═══════════════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {
        top: 52px !important;
        height: calc(100vh - 52px) !important;
        /* Solid opaque background so the plant image doesn't bleed through */
        background: #f0f4f9 !important;
        /* Separator: thin line + soft drop-shadow on the right edge */
        border-right: 1px solid rgba(0, 0, 0, 0.14) !important;
        box-shadow: 2px 0 8px -2px rgba(0, 0, 0, 0.10),
                    1px 0 0 0 rgba(0, 0, 0, 0.06) !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 6px !important;
        background: #f0f4f9 !important;
    }

    /* Streamlit's native expand button (when sidebar is collapsed) —
       keep it as a fallback, positioned below our banner */
    [data-testid="collapsedControl"] {
        top: 60px !important;
    }

    /* ═══════════════════════════════════════════════════════════
       3b. Banner sidebar-toggle  « / »  buttons
    ═══════════════════════════════════════════════════════════ */
    .pvc-nav-toggle {
        display: flex;
        align-items: center;
        gap: 3px;
        margin-right: 10px;
        padding-right: 12px;
        border-right: 1px solid rgba(255, 255, 255, 0.18);
    }
    .pvc-toggle-btn {
        background: rgba(255, 255, 255, 0.10);
        border: 1px solid rgba(255, 255, 255, 0.22);
        border-radius: 5px;
        color: #ffffff;
        cursor: pointer;
        font-size: 1.05rem;
        font-weight: 700;
        line-height: 1;
        padding: 3px 9px 4px 9px;
        letter-spacing: 1px;
        display: flex;
        align-items: center;
        transition: background 0.15s ease, border-color 0.15s ease;
        user-select: none;
        -webkit-user-select: none;
    }
    .pvc-toggle-btn:hover {
        background: rgba(255, 255, 255, 0.22);
        border-color: rgba(255, 255, 255, 0.44);
    }
    .pvc-toggle-btn:active {
        background: rgba(255, 255, 255, 0.32);
    }
    /* Both « and » are always visible — clicking either one toggles the sidebar */

    /* Sidebar-hidden state: collapse the pane + let main content fill width */
    body.pv-sb-hidden section[data-testid="stSidebar"] {
        display: none !important;
        width: 0 !important;
        min-width: 0 !important;
    }

    /* ═══════════════════════════════════════════════════════════
       4.  Main content area — push below banner + overlay so
           the plant background remains subtly visible
    ═══════════════════════════════════════════════════════════ */
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-top: 72px !important;
        padding-left: 2rem   !important;
        padding-right: 2rem  !important;
        max-width: 100% !important;
    }
    /* Semi-transparent frosted overlay on the main content pane */
    [data-testid="stMain"] {
        background: rgba(240, 245, 251, 0.86) !important;
        backdrop-filter: blur(1px);
        -webkit-backdrop-filter: blur(1px);
    }

    /* ═══════════════════════════════════════════════════════════
       5.  Sidebar navigation TREE  styling
    ═══════════════════════════════════════════════════════════ */

    [data-testid="stSidebarNavItems"] {
        padding: 4px 0 12px 0 !important;
    }

    [data-testid="stSidebarNavSectionHeader"] {
        padding: 14px 12px 3px 12px !important;
    }
    [data-testid="stSidebarNavSectionHeader"] p {
        font-size: 0.67rem !important;
        font-weight: 800 !important;
        letter-spacing: 1.2px !important;
        text-transform: uppercase !important;
        color: #1f6aa5 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stSidebarNavSectionHeader"] + * {
        border-top: none;
    }

    [data-testid="stSidebarNavItems"] ul {
        padding-left: 0 !important;
        margin: 0 !important;
        list-style: none !important;
        border-left: 2px solid #dce3ed;
        margin-left: 18px !important;
    }
    [data-testid="stSidebarNavItems"] li {
        list-style: none !important;
        position: relative;
    }

    [data-testid="stSidebarNavLink"] {
        display: flex !important;
        align-items: center !important;
        gap: 7px !important;
        padding: 7px 10px 7px 16px !important;
        margin: 1px 6px 1px 0 !important;
        border-radius: 0 6px 6px 0 !important;
        font-size: 0.88rem !important;
        color: #2c3a4e !important;
        text-decoration: none !important;
        position: relative;
        transition: background 0.15s ease, color 0.15s ease;
    }
    [data-testid="stSidebarNavLink"]::before {
        content: "";
        position: absolute;
        left: -14px;
        top: 50%;
        width: 12px;
        height: 2px;
        background: #dce3ed;
        transform: translateY(-50%);
    }
    [data-testid="stSidebarNavLink"]:hover {
        background: rgba(31, 106, 165, 0.09) !important;
        color: #1f6aa5 !important;
    }

    [data-testid="stSidebarNavLink"][aria-current="page"] {
        background: rgba(31, 106, 165, 0.13) !important;
        color: #1255a0 !important;
        font-weight: 600 !important;
        border-right: 3px solid #1f6aa5 !important;
    }
    [data-testid="stSidebarNavLink"][aria-current="page"]::before {
        background: #1f6aa5;
    }

    [data-testid="stSidebarNavLink"] span[data-testid="stSidebarNavLinkIcon"] {
        font-size: 1rem !important;
    }

    [data-testid="stSidebarNavLink"][href*="pipe-dimensions"],
    [data-testid="stSidebarNavLink"][href*="tube-dimensions"] {
        padding-left: 32px !important;
        font-size:  0.83rem !important;
        color: #4a5d72 !important;
        margin-left: 10px !important;
    }
    [data-testid="stSidebarNavLink"][href*="pipe-dimensions"]::before,
    [data-testid="stSidebarNavLink"][href*="tube-dimensions"]::before {
        left: -24px;
        width: 22px;
    }

    /* ── sidebar footer ── */
    .sidebar-footer {
        position: absolute;
        bottom: 12px;
        left: 0;
        right: 0;
        text-align: center;
        font-size: 0.67rem;
        color: #9aa5b4;
        padding: 0 8px;
    }
    </style>

    <!-- Fixed top banner -->
    <div class="pvc-banner">
        <div class="pvc-banner-left">
            <!-- Sidebar toggle buttons (« collapse / » expand) -->
            <div class="pvc-nav-toggle">
                <button class="pvc-toggle-btn pvc-btn-collapse" onclick="pvToggle()" title="Hide navigation tree">&#171;</button>
                <button class="pvc-toggle-btn pvc-btn-expand"   onclick="pvToggle()" title="Show navigation tree">&#187;</button>
            </div>
            <span class="pvc-banner-icon">🔩</span>
            <span class="pvc-banner-title">Pressure Vessel Calculator</span>
            <span class="pvc-banner-rev">Rev.&nbsp;01 &nbsp;·&nbsp; 2026-06-17</span>
        </div>
        <span class="pvc-banner-author">Dott. Ing. Gian-Luca ANFOSSI</span>
    </div>

    """,
    unsafe_allow_html=True,
)

# ── Sidebar toggle JavaScript (injected via iframe — the only way to guarantee
#    script execution in Streamlit; st.markdown scripts are swallowed by React) ──
components.html("""
<script>
(function () {
    var p = window.parent;
    if (!p) return;
    p.pvToggle = function () {
        p.document.body.classList.toggle('pv-sb-hidden');
    };
})();
</script>
""", height=0, scrolling=False)

# ── Disclaimer modal (shown once per session) ─────────────────────────────────
@st.dialog("⚠️  Disclaimer — Legal Notice", width="large")
def _show_disclaimer() -> None:
    st.markdown(
        """
        <div style="line-height:1.7; font-size:0.93rem;">

        <p>
        This tool is for <strong>informational and preliminary estimation purposes only</strong>.
        </p>

        <p>
        This application is an <strong>independent, third-party resource</strong> and is
        <strong>not affiliated with, sponsored, or endorsed</strong> by
        <em>ASME, CEN (EN standards), BSI (British Standards), CODAP,
        AD-2000 Merkblatt</em>, or any other national or international
        standardization body.
        </p>

        <p>
        Calculations are provided <strong>"as is" without warranty</strong>.<br>
        All results must be <strong>validated by a qualified professional engineer</strong>
        in accordance with the latest official code editions.
        </p>

        <p>
        The developer assumes <strong>no liability</strong> for any errors, omissions,
        or consequences resulting from the use of this tool.
        </p>

        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    col_l, col_r = st.columns([4, 1])
    with col_l:
        st.caption("By clicking **I Accept** you acknowledge that you have read and understood the above disclaimer.")
    with col_r:
        if st.button("✔  I Accept", type="primary", use_container_width=True):
            st.session_state["disclaimer_accepted"] = True
            st.rerun()


if not st.session_state.get("disclaimer_accepted", False):
    _show_disclaimer()

# ── Sidebar footer label (version) ────────────────────────────────────────────
st.sidebar.markdown(
    '<div class="sidebar-footer">v 1.0 — 2026</div>',
    unsafe_allow_html=True,
)

# ── Page navigation tree ───────────────────────────────────────────────────────
pg = st.navigation(
    {
        "Home": [
            st.Page("pages/Home.py", title="Home", icon="🏠"),
        ],
        "Calculations": [
            st.Page("pages/01_Virola_Cilindrica.py", title="Cylindrical Shell", icon="🔵"),
        ],
        "Standards": [
            st.Page("pages/Standards.py",       title="Standards",              icon="📋",
                    url_path="standards"),
            st.Page("pages/Standards_Pipes.py", title="Pipe Dimensions B36.10", icon="🔧",
                    url_path="pipe-dimensions"),
            st.Page("pages/Standards_Tubes.py", title="Tube Dimensions BWG",    icon="⭕",
                    url_path="tube-dimensions"),
        ],
    }
)

pg.run()
