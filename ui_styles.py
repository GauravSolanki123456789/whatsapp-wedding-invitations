"""Shared CSS for desktop and mobile."""

from __future__ import annotations

import streamlit as st


def inject_app_styles() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Fraunces:wght@600&display=swap');

          :root {
            --brand: #b76e79;
            --brand-dark: #9e5560;
            --ink: #2c2416;
            --ink-soft: #6b5b52;
            --surface: #ffffff;
            --muted: #faf6f3;
            --border: rgba(183, 110, 121, 0.22);
            --radius: 14px;
            --success: #2d6a4f;
            --warn: #9a6b00;
          }

          html, body, [class*="css"] { -webkit-font-smoothing: antialiased; }

          .block-container {
            padding-top: 0.5rem;
            padding-bottom: 5rem;
            max-width: 680px;
          }

          h1, h2, h3, .hero-title, .section-title {
            font-family: 'Fraunces', Georgia, serif !important;
          }

          p, label, .stMarkdown, .stCaption, input, textarea, button {
            font-family: 'DM Sans', sans-serif !important;
          }

          #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }

          .app-shell {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 0.85rem 0.9rem;
            margin-bottom: 0.65rem;
          }

          .hero-title {
            font-size: clamp(1.2rem, 4.5vw, 1.55rem);
            color: #5c3d42;
            margin: 0 0 0.2rem 0;
            line-height: 1.2;
          }

          .hero-subtitle {
            color: var(--ink-soft);
            font-size: 0.86rem;
            margin: 0;
            line-height: 1.4;
          }

          .section-title {
            font-size: 1rem;
            color: #5c3d42;
            margin: 0 0 0.5rem 0;
            font-weight: 600;
          }

          .stat-pill {
            display: inline-block;
            background: var(--muted);
            color: #5c3d42;
            border-radius: 999px;
            padding: 0.3rem 0.65rem;
            font-size: 0.78rem;
            font-weight: 600;
            margin: 0 0.25rem 0.25rem 0;
          }

          .stat-pill--ok { background: #e8f5ee; color: var(--success); }
          .stat-pill--warn { background: #fde8e8; color: #8b2e2e; }

          .notice-box {
            border-radius: 10px;
            padding: 0.65rem 0.75rem;
            margin: 0.4rem 0;
            font-size: 0.84rem;
            line-height: 1.45;
          }

          .tip-box { background: #f0faf3; border-left: 3px solid #3d9970; color: #2d4a38; }
          .warning-box { background: #fff8e8; border-left: 3px solid #d4a017; color: #5c4a1a; }
          .info-box { background: #f5f0fa; border-left: 3px solid var(--brand); color: #4a3848; }

          .sender-card-wrap {
            background: linear-gradient(165deg, #f4faf6 0%, #e8f2ec 100%);
            border: 1px solid rgba(45, 106, 79, 0.18);
            border-radius: var(--radius);
            padding: 0.7rem 0.8rem;
            margin: 0.35rem 0 0.65rem 0;
          }

          .sender-card-title {
            font-weight: 700;
            color: #2d4a38;
            font-size: 0.92rem;
            margin: 0 0 0.25rem 0;
          }

          .sender-card-hint {
            color: var(--ink-soft);
            font-size: 0.78rem;
            line-height: 1.4;
            margin: 0;
          }

          .focus-card {
            background: linear-gradient(160deg, #fff9f5 0%, #f8ece6 100%);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1rem 0.85rem;
            text-align: center;
            margin: 0.5rem 0;
          }

          .focus-card--wait { background: #fff8e8; border-color: #e8d48a; }
          .focus-card--ok { background: #eef8f2; border-color: #9fd4b0; }
          .focus-card--used { background: #fdeeee; border-color: #e8a0a0; }

          .focus-guest-number {
            font-size: clamp(1.15rem, 5vw, 1.45rem);
            font-weight: 700;
            color: #5c3d42;
            margin: 0.25rem 0;
            word-break: break-all;
          }

          .focus-meta { color: var(--ink-soft); font-size: 0.85rem; margin: 0; }

          .scan-hint { font-size: 0.82rem; }
          .scan-handout-card { margin-top: 0.25rem; }

          iframe[title="streamlit_components_v1.html"] {
            border-radius: 14px;
            border: 1px solid var(--border);
          }

          .step-list {
            text-align: left;
            margin: 0.5rem 0 0;
            padding-left: 1rem;
            color: var(--ink-soft);
            font-size: 0.82rem;
            line-height: 1.5;
          }

          div[data-testid="stSidebar"] {
            background: var(--muted);
            border-right: 1px solid var(--border);
          }

          div[data-testid="stTabs"] button {
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            padding: 0.4rem 0.55rem !important;
          }

          div[data-testid="stRadio"] > div {
            flex-wrap: wrap;
            gap: 0.2rem;
          }

          div[data-testid="stRadio"] label {
            background: var(--muted);
            border-radius: 10px;
            padding: 0.35rem 0.55rem !important;
            margin: 0.1rem !important;
            font-weight: 600 !important;
            font-size: 0.78rem !important;
            min-height: 2.5rem;
            align-items: center;
          }

          div[data-testid="stRadio"] label[data-checked="true"],
          div[data-testid="stRadio"] label:has(input:checked) {
            background: #f8ece6;
            border: 1px solid var(--brand);
          }

          div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: var(--radius) !important;
            border-color: var(--border) !important;
            padding: 0.45rem 0.55rem !important;
          }

          .stButton > button {
            border-radius: 11px !important;
            min-height: 2.75rem;
            font-weight: 600;
          }

          .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, var(--brand), var(--brand-dark)) !important;
            border: none !important;
            color: #fff !important;
          }

          a[data-testid="stLinkButton"] {
            border-radius: 11px !important;
            min-height: 2.85rem !important;
            font-weight: 700 !important;
          }

          [data-testid="stMetric"] {
            background: var(--muted);
            border-radius: 10px;
            padding: 0.35rem 0.5rem;
          }

          @media (max-width: 768px) {
            .block-container {
              padding-left: 0.5rem;
              padding-right: 0.5rem;
              padding-bottom: 5.5rem;
              max-width: 100%;
            }

            div[data-testid="column"] {
              width: 100% !important;
              flex: 1 1 100% !important;
              min-width: 100% !important;
            }

            div[data-testid="stRadio"] > div {
              width: 100%;
            }

            div[data-testid="stRadio"] label {
              flex: 1 1 45%;
              justify-content: center;
            }

            .sender-card-wrap {
              padding: 0.65rem 0.7rem;
            }

            div[data-testid="stTabs"] [data-baseweb="tab-list"] {
              gap: 0.15rem;
              overflow-x: auto;
              flex-wrap: nowrap;
              -webkit-overflow-scrolling: touch;
            }

            div[data-testid="stTabs"] button {
              white-space: nowrap;
              flex-shrink: 0;
            }

            .stButton > button { min-height: 3rem; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
