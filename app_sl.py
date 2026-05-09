from __future__ import annotations

import streamlit as st

import ui as _ui


_ORIGINAL_CONFIGURE_PAGE = _ui.configure_page


def configure_page_with_header_alignment() -> None:
    """Configure the Streamlit page and align the portfolio links with the tab row."""
    _ORIGINAL_CONFIGURE_PAGE()

    st.markdown(
        """
        <style>
        /*
        Photo Sonification header alignment
        -----------------------------------
        In ui.main(), render_portfolio_links() is called just before st.tabs().
        Without the negative bottom margin below, the link row keeps its own
        vertical space and pushes the tabs downward. This makes the personal
        links appear above the tab row instead of visually sharing the same row.
        */

        .portfolio-links {
            display: flex !important;
            justify-content: flex-end !important;
            align-items: center !important;
            gap: 0.45rem !important;
            min-height: 2.45rem !important;
            margin-top: 0 !important;
            margin-bottom: -2.45rem !important;
            padding-top: 0.10rem !important;
            position: relative !important;
            z-index: 20 !important;
            pointer-events: none !important;
        }

        .portfolio-links .portfolio-link {
            pointer-events: auto !important;
        }

        div[data-testid="stTabs"] {
            position: relative !important;
            z-index: 10 !important;
        }

        @media (max-width: 900px) {
            .portfolio-links {
                justify-content: flex-start !important;
                flex-wrap: wrap !important;
                min-height: auto !important;
                margin-bottom: 0.50rem !important;
                padding-top: 0 !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_ui.configure_page = configure_page_with_header_alignment
main = _ui.main


if __name__ == "__main__":
    main()
