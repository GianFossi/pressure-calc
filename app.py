import streamlit as st

# ── Page config (must be the very first Streamlit call) ────────────────────────
st.set_page_config(
    page_title="Pressure Vessel Calculator",
    page_icon="🔩",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    /* remove the orange/blue "running" top bar flash */
    div[data-testid="stStatusWidget"]  { display: none !important; }

    /* ═══════════════════════════════════════════════════════════
       2.  Fixed top banner  (title + author)
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
    .pvc-banner-author {
        font-size: 0.76rem;
        opacity: 0.75;
        font-style: italic;
        white-space: nowrap;
    }
    @media (max-width: 640px) {
        .pvc-banner-author { display: none; }
    }

    /* ═══════════════════════════════════════════════════════════
       3.  Sidebar  — push it below the banner
    ═══════════════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {
        top: 52px !important;
        height: calc(100vh - 52px) !important;
        border-right: 1px solid #dde2ea;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 6px !important;
        background: #f7f9fc !important;
    }

    /* Sidebar collapse / expand arrow — keep it visible below banner */
    [data-testid="collapsedControl"] {
        top: 60px !important;
    }

    /* ═══════════════════════════════════════════════════════════
       4.  Main content area — push below banner
    ═══════════════════════════════════════════════════════════ */
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-top: 72px !important;
        padding-left: 2rem   !important;
        padding-right: 2rem  !important;
        max-width: 100% !important;
    }

    /* ═══════════════════════════════════════════════════════════
       5.  Sidebar navigation TREE  styling
    ═══════════════════════════════════════════════════════════ */

    /* ── overall nav container ── */
    [data-testid="stSidebarNavItems"] {
        padding: 4px 0 12px 0 !important;
    }

    /* ── section / group header  (e.g. "CALCULATIONS") ── */
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
    /* separator line above each group (except first) */
    [data-testid="stSidebarNavSectionHeader"] + * {
        border-top: none;
    }

    /* ── tree branch vertical connector on the left ── */
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

    /* ── individual page link ── */
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
    /* horizontal tree connector */
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

    /* ── active / selected page ── */
    [data-testid="stSidebarNavLink"][aria-current="page"] {
        background: rgba(31, 106, 165, 0.13) !important;
        color: #1255a0 !important;
        font-weight: 600 !important;
        border-right: 3px solid #1f6aa5 !important;
    }
    [data-testid="stSidebarNavLink"][aria-current="page"]::before {
        background: #1f6aa5;
    }

    /* ── link text / icon spacing ── */
    [data-testid="stSidebarNavLink"] span[data-testid="stSidebarNavLinkIcon"] {
        font-size: 1rem !important;
    }

    /* ── Pipe Dimensions & Tube Dimensions: child nodes of Standards ── */
    [data-testid="stSidebarNavLink"][href*="pipe-dimensions"],
    [data-testid="stSidebarNavLink"][href*="tube-dimensions"] {
        padding-left: 32px !important;   /* deeper indent than siblings (16 px) */
        font-size:  0.83rem !important;
        color: #4a5d72 !important;
        margin-left: 10px !important;
    }
    /* longer horizontal branch — connects visually from Standards' vertical line */
    [data-testid="stSidebarNavLink"][href*="pipe-dimensions"]::before,
    [data-testid="stSidebarNavLink"][href*="tube-dimensions"]::before {
        left: -24px;
        width: 22px;
    }

    /* ── sidebar footer  (version label, etc.) ── */
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
            <span class="pvc-banner-icon">🔩</span>
            <span class="pvc-banner-title">Pressure Vessel Calculator</span>
        </div>
        <span class="pvc-banner-author">Dott. Ing. Gian-Luca ANFOSSI</span>
    </div>
    """,
    unsafe_allow_html=True,
)

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
