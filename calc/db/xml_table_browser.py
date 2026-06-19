import pandas as pd
import streamlit as st

from calc.db.standards_xml import export_csv


def _clear_filter_keys(prefix: str) -> None:
    for key in list(st.session_state):
        if key.startswith(prefix):
            del st.session_state[key]


def _visible(df: pd.DataFrame) -> pd.DataFrame:
    return df[[col for col in df.columns if not col.startswith("_")]]


def _apply_text_search(df: pd.DataFrame, search: str) -> pd.DataFrame:
    if not search.strip() or df.empty:
        return df
    terms = [term.casefold() for term in search.split() if term.strip()]
    text = _visible(df).fillna("").astype(str).agg(" ".join, axis=1).str.casefold()
    mask = pd.Series(True, index=df.index)
    for term in terms:
        mask &= text.str.contains(term, regex=False)
    return df[mask]


def render_xml_table_browser(
    *,
    title: str,
    caption: str,
    df: pd.DataFrame,
    key: str,
    filter_columns: list[str],
    primary_columns: list[str],
) -> None:
    st.title(title)
    st.caption(caption)

    if df.empty:
        st.warning("No rows were loaded from the XML file.")
        return

    prefix = f"{key}_filter_"
    left, right = st.columns([1, 5])
    with left:
        if st.button("Reset filters", key=f"{prefix}reset", use_container_width=True):
            _clear_filter_keys(prefix)
            st.rerun()
    with right:
        search = st.text_input(
            "Search",
            placeholder="Search all visible columns",
            key=f"{prefix}search",
        )

    filtered = _apply_text_search(df, search)

    available_filters = [col for col in filter_columns if col in df.columns]
    if available_filters:
        cols = st.columns(min(4, len(available_filters)))
        for index, column in enumerate(available_filters):
            options = sorted(
                [str(value) for value in df[column].dropna().unique() if str(value).strip()],
                key=lambda value: (len(value), value),
            )
            with cols[index % len(cols)]:
                selected = st.multiselect(
                    column,
                    options=options,
                    key=f"{prefix}{column}",
                )
            if selected:
                filtered = filtered[filtered[column].astype(str).isin(selected)]

    visible = _visible(filtered)
    st.caption(f"{len(visible):,} / {len(df):,} rows")

    if visible.empty:
        st.warning("No rows match the current filters.")
        return

    st.download_button(
        "Download filtered CSV",
        data=export_csv(filtered),
        file_name=f"{key}.csv",
        mime="text/csv",
        key=f"{key}_download",
    )

    ordered_columns = [col for col in primary_columns if col in visible.columns]
    ordered_columns.extend([col for col in visible.columns if col not in ordered_columns])
    visible = visible[ordered_columns]

    selected = st.dataframe(
        visible,
        hide_index=True,
        use_container_width=True,
        height=560,
        on_select="rerun",
        selection_mode="single-row",
        key=f"{key}_table",
    )

    rows = selected.selection.rows
    if rows:
        selected_row = visible.iloc[rows[0]].replace("", pd.NA).dropna()
        with st.expander("Selected row details", expanded=True):
            st.dataframe(
                selected_row.rename_axis("Property").reset_index(name="Value"),
                hide_index=True,
                use_container_width=True,
            )
