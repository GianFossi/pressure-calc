import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calc.codes import asme_viii_1, en_13445



st.title("Virola Cilindrica — Pressione Interna")
st.caption("ASME VIII Div.1 (UG-27) · EN 13445-3 (§ 7.4.2) | Confronto codici")

# ─── INPUT ───────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader("Parametri di ingresso")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**Geometria e pressione**")
        D_i = st.number_input(
            "Diametro interno Dᵢ (mm)", min_value=10.0, value=1000.0,
            step=10.0, format="%.1f"
        )
        P = st.number_input(
            "Pressione di calcolo P (bar)", min_value=0.1, value=10.0,
            step=0.5, format="%.2f"
        )

    with c2:
        st.markdown("**Tensioni ammissibili**")
        S_asme = st.number_input(
            "S — ASME VIII-1 (MPa)", min_value=1.0, value=138.0, step=1.0,
            help="Allowable stress da tabelle ASME IID (es. SA-516-70: 138 MPa a 20°C)"
        )
        link_stress = st.checkbox("Usa f (EN) = S (ASME)", value=True)
        if link_stress:
            f_en = S_asme
            st.info(f"f = {f_en:.1f} MPa")
        else:
            f_en = st.number_input(
                "f — EN 13445-3 (MPa)", min_value=1.0, value=138.0, step=1.0,
                help="Tensione nominale di progetto da EN 13445-2 Tabella B.1"
            )

    with c3:
        st.markdown("**Efficienze giunti saldati**")
        E_asme = st.selectbox(
            "E — ASME (joint efficiency)",
            options=[1.0, 0.85, 0.70],
            format_func=lambda x: {1.0: "1.00 — RT completa (Cat. A)", 0.85: "0.85 — RT parziale", 0.70: "0.70 — Senza RT"}[x],
            help="UW-12: radiografia completa→1.0, parziale→0.85, nessuna→0.70"
        )
        z_en = st.selectbox(
            "z — EN 13445-3 (joint coefficient)",
            options=[1.0, 0.85, 0.70],
            format_func=lambda x: {1.0: "1.00 — Categoria A/B esaminati", 0.85: "0.85 — Categoria C/D", 0.70: "0.70 — Senza esame"}[x],
            help="EN 13445-3 Tabella 6.6.2: dipende da categoria e livello esame CND"
        )

# ─── VERIFICA SPESSORE (opzionale) ───────────────────────────────────────────
with st.expander("Verifica spessore nominale (modalità opzionale)"):
    check_mode = st.toggle("Attiva verifica spessore", value=False)
    if check_mode:
        cv1, cv2, cv3 = st.columns(3)
        with cv1:
            t_nom = st.number_input(
                "Spessore nominale ordinato (mm)", min_value=0.5, value=16.0, step=0.5
            )
        with cv2:
            corr = st.number_input(
                "Sovraspessore di corrosione c (mm)", min_value=0.0, value=1.0, step=0.5,
                help="Allowance totale per corrosione/erosione (uguale per entrambi i codici)"
            )
            mill_pct = st.number_input(
                "Tolleranza laminazione ASME (%)", min_value=0.0, value=12.5, step=0.5,
                help="SA-20/A20: 12.5% per lamiere. Ridotta per tubi: vedi spec. materiale."
            )
        with cv3:
            undertol = st.number_input(
                "Tolleranza negativa EN δ₁ (mm)", min_value=0.0, value=0.3, step=0.1,
                help="Tolleranza di sottospessore assoluta del laminato (EN 13445-3 §6.1.5)"
            )
    else:
        t_nom = corr = mill_pct = undertol = 0.0

# ─── CALCOLI ─────────────────────────────────────────────────────────────────
if check_mode:
    res_asme = asme_viii_1.check(t_nom, corr, mill_pct, P, D_i, S_asme, E_asme)
    res_en   = en_13445.check(t_nom, corr, undertol, P, D_i, f_en, z_en)
else:
    res_asme = asme_viii_1.thickness_internal(P, D_i, S_asme, E_asme)
    res_en   = en_13445.thickness_internal(P, D_i, f_en, z_en)

# ─── RISULTATI ───────────────────────────────────────────────────────────────
st.divider()

if "error" in res_asme or "error" in res_en:
    for label, res in [("ASME VIII-1", res_asme), ("EN 13445-3", res_en)]:
        if "error" in res:
            st.error(f"**{label}:** {res['error']}")
else:
    col_a, col_e = st.columns(2)

    # ── ASME VIII-1 ──────────────────────────────────────────────────────────
    with col_a:
        st.markdown("### ASME VIII Div.1")
        st.caption(f"Riferimento: {res_asme['ref']}")

        base_rows = [
            ("Pressione P",              f"{res_asme['P_MPa']} MPa"),
            ("Raggio interno R",         f"{res_asme['R_mm']} mm"),
            ("Tensione ammissibile S",   f"{S_asme} MPa"),
            ("Efficienza giunto E",      str(E_asme)),
            ("Spessore hoop (c)(1)",     f"{res_asme['t_hoop_mm']} mm"),
            ("Spessore long. (c)(2)",    f"{res_asme['t_long_mm']} mm"),
            ("Spessore minimo richiesto",f"{res_asme['t_min_mm']} mm  ← governa"),
        ]
        st.dataframe(
            pd.DataFrame(base_rows, columns=["Parametro", "Valore"]),
            hide_index=True, use_container_width=True
        )
        st.caption(f"Formula determinante: {res_asme['governing']}")
        st.latex(res_asme["latex_hoop"])

        if check_mode:
            st.markdown("**Verifica spessore**")
            chk_rows = [
                ("Spessore nominale",         f"{res_asme['t_nom_mm']} mm"),
                ("− Tolleranza laminazione",  f"−{res_asme['mill_tol_pct']}% → −{res_asme['t_nom_mm'] * res_asme['mill_tol_pct'] / 100:.2f} mm"),
                ("− Sovraspessore corrosione", f"−{res_asme['corr_mm']} mm"),
                ("= Spessore disponibile",    f"{res_asme['t_avail_mm']} mm"),
                ("Margine (disp. − req.)",    f"{res_asme['margin_mm']:+.3f} mm"),
                ("MAWP",                      f"{res_asme['MAWP_bar']} bar"),
                ("Esito",                     res_asme["status"]),
            ]
            st.dataframe(
                pd.DataFrame(chk_rows, columns=["", "Valore"]),
                hide_index=True, use_container_width=True
            )

    # ── EN 13445-3 ───────────────────────────────────────────────────────────
    with col_e:
        st.markdown("### EN 13445-3")
        st.caption(f"Riferimento: {res_en['ref']}")

        base_rows_en = [
            ("Pressione P",                   f"{res_en['P_MPa']} MPa"),
            ("Diametro interno Dᵢ",           f"{D_i:.1f} mm"),
            ("Tensione di calcolo f",          f"{f_en} MPa"),
            ("Coefficiente giunto z",          str(z_en)),
            ("Spessore analisi minimo richiesto", f"{res_en['e_min_mm']} mm"),
        ]
        st.dataframe(
            pd.DataFrame(base_rows_en, columns=["Parametro", "Valore"]),
            hide_index=True, use_container_width=True
        )
        st.caption(f"Verifica: {res_en['governing']}")
        st.latex(res_en["latex"])

        if check_mode:
            st.markdown("**Verifica spessore**")
            chk_rows_en = [
                ("Spessore nominale",         f"{res_en['e_nom_mm']} mm"),
                ("− Tolleranza negativa δ₁",  f"−{res_en['undertol_mm']} mm"),
                ("− Sovraspessore corrosione", f"−{res_en['corr_mm']} mm"),
                ("= Spessore analisi disponibile", f"{res_en['e_avail_mm']} mm"),
                ("Margine (disp. − req.)",    f"{res_en['margin_mm']:+.3f} mm"),
                ("PS max",                    f"{res_en['PS_max_bar']} bar"),
                ("Esito",                     res_en["status"]),
            ]
            st.dataframe(
                pd.DataFrame(chk_rows_en, columns=["", "Valore"]),
                hide_index=True, use_container_width=True
            )

    # ── CONFRONTO DIRETTO ────────────────────────────────────────────────────
    st.divider()
    st.subheader("Confronto diretto")

    t_req = res_asme["t_min_mm"]
    e_req = res_en["e_min_mm"]
    diff  = round(t_req - e_req, 3)
    pct   = round(abs(diff) / max(t_req, e_req) * 100, 1) if max(t_req, e_req) > 0 else 0.0

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("ASME VIII-1  t_min", f"{t_req} mm")
    mc2.metric("EN 13445-3   e_min", f"{e_req} mm")
    mc3.metric("Δ (ASME − EN)", f"{diff:+.3f} mm", delta_color="off")

    if abs(diff) < 0.01:
        st.success("I due codici convergono allo stesso spessore richiesto.")
    elif diff > 0:
        st.info(f"**ASME VIII-1** è più conservativo del **{pct}%** per questi parametri.")
    else:
        st.info(f"**EN 13445-3** è più conservativo del **{pct}%** per questi parametri.")

    # ── NOTE TECNICHE ─────────────────────────────────────────────────────────
    with st.expander("Note tecniche — Derivazione e confronto formule"):
        st.markdown(r"""
### Formula di membrana (thin-wall)

Entrambe le formule derivano dall'equilibrio di membrana su una virola cilindrica
(Lamé in regime thin-wall, valido per $D_i/e \gtrsim 20$).

**ASME VIII-1 UG-27(c)(1)** — usa il raggio interno $R$:

$$t = \frac{P \cdot R}{S \cdot E - 0.6\,P}$$

**EN 13445-3 §7.4.2 Eq. (7.4-1)** — usa il diametro interno $D_i$:

$$e = \frac{P \cdot D_i}{2\,f \cdot z - P}$$

Riscrivendo la formula EN in termini di raggio $R_i = D_i/2$:

$$e = \frac{P \cdot R_i}{f \cdot z - 0.5\,P}$$

### Differenza tra i codici

| Termine denominatore | ASME | EN 13445 |
|---|---|---|
| Fattore P | $0.6\,P$ | $0.5\,P$ |
| Effetto | Denominatore più piccolo | Denominatore più grande |
| Risultato | **Spessore leggermente maggiore** | Spessore leggermente minore |

Il fattore **0.6** di ASME (vs 0.5 di EN) è una correzione empirica che tiene conto
della distribuzione reale degli sforzi nella parete e produce risultati più vicini alla
soluzione esatta di Lamé per gusci di spessore moderato.

La differenza **tende a zero** per $P \ll f \cdot z$ (gusci sottili a bassa pressione)
e diventa apprezzabile per rapporti $P / (f \cdot z) > 0.05$.

### Spessore ordinato

Allo spessore strutturale si aggiunge sempre il sovraspessore di corrosione $c$:

- **ASME:** $t_{ord} = t_{min} + c$ (poi si verifica rispetto alla tolleranza di laminazione)
- **EN 13445:** $e_{ord} = e + c + \delta_1$ (la tolleranza negativa $\delta_1$ è inclusa nell'ordine)
        """)
