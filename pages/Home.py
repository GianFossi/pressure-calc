import streamlit as st

st.title("🔩 Pressure Vessel Calculator")
st.markdown("Strumento di calcolo per **componenti in pressione** con comparazione tra codici internazionali.")

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Codici di calcolo")
    st.markdown("""
| Codice | Stato |
|--------|-------|
| ASME VIII Div. 1 | ✅ Attivo |
| EN 13445-3 | ✅ Attivo |
| ASME VIII Div. 2 | 🔜 In sviluppo |
| CODAP 2023 | 🔜 Pianificato |
| AD 2000 | 🔜 Pianificato |
""")

with col2:
    st.subheader("Componenti implementati")
    st.markdown("""
| Componente | Carico | Stato |
|------------|--------|-------|
| Virola cilindrica | Pressione interna | ✅ Attivo |
| Virola cilindrica | Pressione esterna | 🔜 Fase 2 |
| Virola cilindrica | Carichi esterni (vento/sisma) | 🔜 Fase 2 |
| Transizione conica | P interna / esterna | 🔜 Fase 3 |
| Fondi saldati (ellittici, torisferici, emisferici) | P interna | 🔜 Fase 3 |
| Bocchellame e rinforzi | P interna | 🔜 Fase 4 |
| Fondi imbullonati (flange) | P interna | 🔜 Fase 5 |
| Piastre tubiere | P interna | 🔜 Fase 5 |
| Supporti (selle, gambe, skirt) | Carichi statici | 🔜 Fase 6 |
""")

st.divider()
st.caption("Versione 0.1 — Fase 1: Virola cilindrica | Pressione interna | ASME VIII-1 + EN 13445-3")
