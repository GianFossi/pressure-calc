import streamlit as st
import base64
from pathlib import Path

_NAV_W    = 200  # left nav panel width  (px)
_BANNER_H = 52   # top banner height     (px)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Calculator of Pressure Vessel Components",
    page_icon="🔩",
    layout="wide",
)

# ── Background image (base64 so it works on Cloud too) ────────────────────────
def _bg_css() -> str:
    img = Path(__file__).parent / "static" / "bg_plant.jpg"
    if not img.exists():
        return ""
    data = base64.b64encode(img.read_bytes()).decode()
    return (
        ".stApp {"
        f' background-image:url("data:image/jpeg;base64,{data}") !important;'
        " background-size:cover !important;"
        " background-position:center center !important;"
        " background-attachment:fixed !important;"
        " background-repeat:no-repeat !important;"
        "}"
    )

# ── Global CSS + top banner ────────────────────────────────────────────────────
# The nav panel DIV is NOT here — it is appended to document.body via JS
# (st.iframe below) so position:fixed works across all Streamlit versions.
_bg = _bg_css()
st.markdown(
    f"""
    <style>
    {_bg}

    /* ── Streamlit chrome reset ── */
    header[data-testid="stHeader"],
    #MainMenu, footer,
    div[data-testid="stStatusWidget"],
    section[data-testid="stSidebar"],
    [data-testid="collapsedControl"],
    iframe[title="components.html"]          {{ display:none !important; }}

    /* ── Full-page layout ── */
    [data-testid="stApp"] {{
        overflow-x: hidden !important;
    }}
    [data-testid="stMain"] {{
        margin-left: {_NAV_W}px !important;
        width: calc(100vw - {_NAV_W}px) !important;
        max-width: calc(100vw - {_NAV_W}px) !important;
        min-width: 0 !important;
        background: rgba(240,245,251,0.86) !important;
        backdrop-filter: blur(1px);
        -webkit-backdrop-filter: blur(1px);
    }}
    .main .block-container,
    [data-testid="stMainBlockContainer"] {{
        padding-top: {_BANNER_H + 20}px !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
    }}

    /* ── Top banner ── */
    .pvc-banner {{
        position:fixed; top:0; left:0; right:0;
        height:{_BANNER_H}px;
        background:linear-gradient(90deg,#4a4a4a 0%,#e0e0e0 100%);
        color:#fff;
        display:flex; align-items:center; justify-content:space-between;
        padding:0 24px 0 18px;
        z-index:999999;
        box-shadow:0 2px 10px rgba(0,0,0,0.35);
        border-bottom:1px solid rgba(255,255,255,0.10);
        font-family:"Source Sans Pro","Helvetica Neue",Arial,sans-serif;
    }}
    .pvc-banner-left  {{ display:flex; align-items:center; gap:10px; }}
    .pvc-banner-icon  {{ font-size:1.35rem; line-height:1; }}
    .pvc-banner-title {{ font-size:1.05rem; font-weight:700; letter-spacing:0.3px; white-space:nowrap; }}
    .pvc-banner-rev {{
        font-size:0.68rem; font-weight:500; letter-spacing:0.5px; opacity:0.80;
        background:rgba(255,255,255,0.13); border:1px solid rgba(255,255,255,0.22);
        border-radius:4px; padding:2px 8px; white-space:nowrap;
    }}
    .pvc-banner-author {{ font-size:0.76rem; opacity:0.75; font-style:italic; white-space:nowrap; }}
    @media (max-width:640px) {{
        .pvc-banner-author, .pvc-banner-rev {{ display:none; }}
    }}

    /* ── Nav panel (div created by JS below) ── */
    .pvc-nav {{
        position:fixed; top:{_BANNER_H}px; left:0;
        width:{_NAV_W}px; height:calc(100vh - {_BANNER_H}px);
        background:#f0f4f9;
        border-right:1px solid rgba(0,0,0,0.14);
        box-shadow:2px 0 8px -2px rgba(0,0,0,0.10), 1px 0 0 0 rgba(0,0,0,0.06);
        overflow-y:auto;
        font-family:"Source Sans Pro","Helvetica Neue",Arial,sans-serif;
        z-index:99998; box-sizing:border-box;
    }}
    .pvc-nav-group {{
        font-size:0.63rem; font-weight:800; letter-spacing:1.2px;
        text-transform:uppercase; color:#1f6aa5;
        margin:14px 0 2px 14px; padding:0; line-height:1.3;
    }}
    .pvc-nav-branch {{ margin-left:20px; border-left:2px solid #dce3ed; }}
    .pvc-nav-link {{
        display:flex; align-items:center; gap:7px;
        padding:7px 10px 7px 18px; margin:1px 6px 1px 0;
        border-radius:0 6px 6px 0;
        font-size:0.88rem; color:#2c3a4e; text-decoration:none;
        position:relative; transition:background .15s ease, color .15s ease;
    }}
    .pvc-nav-link::before {{
        content:""; position:absolute; left:-14px; top:50%;
        width:12px; height:2px; background:#dce3ed; transform:translateY(-50%);
    }}
    .pvc-nav-link:hover {{ background:rgba(31,106,165,0.09); color:#1f6aa5; }}
    .pvc-nav-link[aria-current="page"] {{
        background:rgba(31,106,165,0.13); color:#1255a0;
        font-weight:600; border-right:3px solid #1f6aa5;
    }}
    .pvc-nav-link[aria-current="page"]::before {{ background:#1f6aa5; }}
    .pvc-nav-footer {{
        position:absolute; bottom:12px; left:0; right:0;
        text-align:center; font-size:0.67rem; color:#9aa5b4; padding:0 8px;
    }}

    </style>

    <div class="pvc-banner">
        <div class="pvc-banner-left">
            <span class="pvc-banner-icon">🔩</span>
            <span class="pvc-banner-title">Pressure Vessel Calculator</span>
            <span class="pvc-banner-rev">v1.1.0&nbsp;·&nbsp;2026-Jun-19</span>
        </div>
        <span class="pvc-banner-author">Dott. Ing. Gian-Luca ANFOSSI
            (&thinsp;<a href="https://www.linkedin.com/in/gian-luca-anfossi-a3797a18"
                        target="_blank" style="color:inherit">LinkedIn</a>&thinsp;&ndash;&thinsp;
                      <a href="https://github.com/GianFossi"
                         target="_blank" style="color:inherit">GitHub</a>&thinsp;)
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Nav panel + active-page highlight (JS → document.body) ────────────────────
st.iframe(r"""
<script>
(function () {
    var p = window.parent;
    if (!p || p === window) return;

    var HTML =
        '<p class="pvc-nav-group">Home</p>'
      + '<div class="pvc-nav-branch">'
      +   '<a class="pvc-nav-link" href="/"                  data-path="/">🏠 Home</a>'
      + '</div>'
      + '<p class="pvc-nav-group">Calculations</p>'
      + '<div class="pvc-nav-branch">'
      +   '<a class="pvc-nav-link" href="/cylindrical-shell" data-path="/cylindrical-shell">🔵 Cylindrical Shell</a>'
      + '</div>'
      + '<p class="pvc-nav-group">Standards</p>'
      + '<div class="pvc-nav-branch">'
      +   '<a class="pvc-nav-link" href="/standards"         data-path="/standards">📋 Standards</a>'
      +   '<a class="pvc-nav-link" href="/pipe-dimensions"   data-path="/pipe-dimensions">🔧 Pipe Dim. B36.10</a>'
      +   '<a class="pvc-nav-link" href="/tube-dimensions"   data-path="/tube-dimensions">⭕ Tube Dim. BWG</a>'
      + '</div>'
      + '<p class="pvc-nav-group">Materials</p>'
      + '<div class="pvc-nav-branch">'
      +   '<a class="pvc-nav-link" href="/materials"         data-path="/materials">📦 Materials DB</a>'
      + '</div>'
      + '<div class="pvc-nav-footer">v1.1.0 — 2026-Jun-19</div>';

    function inject() {
        if (p.document.getElementById('pvc-nav')) return;
        var nav = p.document.createElement('div');
        nav.id = 'pvc-nav';
        nav.className = 'pvc-nav';
        nav.innerHTML = HTML;
        p.document.body.appendChild(nav);
    }

    function mark() {
        var path = p.location.pathname.replace(/\/+$/, '') || '/';
        p.document.querySelectorAll('.pvc-nav-link').forEach(function (a) {
            var dp = (a.dataset.path || '').replace(/\/+$/, '') || '/';
            if (dp === path) { a.setAttribute('aria-current', 'page'); }
            else             { a.removeAttribute('aria-current'); }
        });
    }

    // ── Disclaimer: persist acceptance as cookie + localStorage ───────────────
    if (new URL(p.location.href).searchParams.has('_da')) {
        // Python signalled acceptance — write a 1-year cookie so Python can read
        // it on every future load without needing the query param.
        p.document.cookie = 'pvc_da=1; max-age=31536000; path=/; SameSite=Lax';
        localStorage.setItem('pvc_da', '1');
    }

    // ── Nav clicks: use history API so Streamlit reuses the same session ───────
    // pushState + popstate triggers Streamlit's router without an HTTP reload,
    // keeping session_state alive (and _disclaimer_ok = True) across all pages.
    if (!p._pvcNavReady) {
        p._pvcNavReady = true;
        p.document.addEventListener('click', function (e) {
            var link = e.target.closest('.pvc-nav-link');
            if (!link) return;
            e.preventDefault();
            var dest = link.getAttribute('data-path') || '/';
            p.history.pushState({}, '', dest);
            p.dispatchEvent(new p.PopStateEvent('popstate', { state: {} }));
            setTimeout(mark, 30);
        }, true);
    }

    inject(); mark();
    new p.MutationObserver(function () { inject(); mark(); })
        .observe(p.document.body, { childList: true, subtree: true });
})();
</script>
""", height=0)

# ── Disclaimer — shown once per session on first site access ───────────────────
@st.dialog("⚠️  Disclaimer — Legal Notice", width="large")
def _disclaimer() -> None:
    st.markdown(
        """
        <div style="line-height:1.7;font-size:0.93rem;">
        <p>This tool is for <strong>informational and preliminary estimation purposes only</strong>.</p>
        <p>
        This application is an <strong>independent, third-party resource</strong> and is
        <strong>not affiliated with, sponsored, or endorsed</strong> by
        <em>ASME, CEN (EN standards), BSI (British Standards), CODAP,
        AD-2000 Merkblatt</em>, or any other national or international standardization body.
        </p>
        <p>
        Calculations are provided <strong>"as is" without warranty</strong>.<br>
        All results must be <strong>validated by a qualified professional engineer</strong>
        in accordance with the latest official code editions.
        </p>
        <p>The developer assumes <strong>no liability</strong> for any errors, omissions,
        or consequences arising from use of this tool.</p>
        </div>
        <hr style="margin:0.5rem 0;">
        <p style="font-size:0.78rem;color:#666;margin:0;">
        ℹ️ <strong>Browser storage notice:</strong> your acceptance is saved as a
        cookie and in localStorage so this dialog is not repeated on future visits.
        To reset, clear site data for this page in your browser settings.
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    col_l, col_m, col_r = st.columns([3, 1, 1])
    with col_l:
        st.caption("Read the disclaimer above before choosing.")
    with col_m:
        if st.button("✖  I Decline", type="secondary", use_container_width=True):
            st.session_state["_disclaimer_declined"] = True
            st.rerun()
    with col_r:
        if st.button("✔  I Accept", type="primary", use_container_width=True):
            st.session_state["_disclaimer_ok"] = True
            st.query_params["_da"] = "1"   # JS persists this to localStorage
            st.rerun()

def _previously_accepted() -> bool:
    """True if the user accepted the disclaimer in a previous browser session.

    Checks the 'pvc_da' cookie written by JS after the first acceptance.
    Falls back to the ?_da=1 query param for the first rerun after acceptance.
    """
    # Cookie path — reliable for every new HTTP request / Streamlit session
    try:
        raw = st.context.headers.get("Cookie", "")
        for chunk in raw.split(";"):
            name, _, val = chunk.strip().partition("=")
            if name.strip() == "pvc_da" and val.strip() == "1":
                return True
    except Exception:
        pass
    # Query-param path — set by Python immediately after the user clicks Accept
    return st.query_params.get("_da") == "1"

if _previously_accepted():
    st.session_state["_disclaimer_ok"] = True

if (not st.session_state.get("_disclaimer_ok")
        and not st.session_state.get("_disclaimer_declined")):
    _disclaimer()

# ── Page routing ───────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "Home": [
            st.Page("pages/1_Home/Home.py", title="Home", icon="🏠"),
        ],
        "Calculations": [
            st.Page("pages/2_Calculations/01_Virola_Cilindrica.py", title="Cylindrical Shell", icon="🔵",
                    url_path="cylindrical-shell"),
        ],
        "Standards": [
            st.Page("pages/3_Standards/00_Standards.py",        title="Standards",              icon="📋",
                    url_path="standards"),
            st.Page("pages/3_Standards/01_Standards_Pipes.py",  title="Pipe Dimensions B36.10", icon="🔧",
                    url_path="pipe-dimensions"),
            st.Page("pages/3_Standards/02_Standards_Tubes.py",  title="Tube Dimensions BWG",    icon="⭕",
                    url_path="tube-dimensions"),
        ],
        "Materials": [
            st.Page("pages/4_Materials/00_Materials.py", title="Materials DB", icon="📦",
                    url_path="materials"),
        ],
    },
    position="hidden",
)

if st.session_state.get("_disclaimer_declined"):
    st.markdown(
        """
        <div style="text-align:center;padding:4rem 1rem 2rem;">
            <div style="font-size:4rem;line-height:1;">🚫</div>
            <h1 style="color:#c0392b;font-size:2.4rem;margin:0.4rem 0 0.6rem;">ACCESS DENIED</h1>
            <p style="font-size:1.05rem;color:#555;max-width:480px;margin:0 auto 1.5rem;">
                You have declined the legal disclaimer.<br>
                Access to this tool requires acceptance of the terms of use.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("↩  Review Disclaimer", type="primary", use_container_width=True):
            del st.session_state["_disclaimer_declined"]
            st.rerun()
else:
    pg.run()
