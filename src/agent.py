"""
LLM text-to-SQL agent and automatic Plotly chart selection.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd
import plotly.express as px
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brand palette
# ---------------------------------------------------------------------------
BRAND_COLORS = [
    "#7c8aff", "#a78bfa", "#34d399", "#fbbf24",
    "#38bdf8", "#f472b6", "#818cf8", "#2dd4bf",
]

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a senior data analyst who writes SQLite SQL.

Given the database schema and a user question, return ONE valid SQLite SELECT statement.

Rules:
- ONLY produce SELECT (or WITH ... SELECT) statements.
- Never use DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE, PRAGMA.
- Use the exact table and column names from the schema.
- Prefer aggregations when the question implies "total", "count", "average", "top", "trend".
- Always add a LIMIT (max 500) unless the query is already aggregated to few rows.
- Return ONLY the SQL, no markdown fences, no explanations, no trailing semicolon.

Database schema:
{schema}
"""


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------
def build_llm(api_key: str, model: str, base_url: str | None = None) -> ChatOpenAI:
    """Instantiate a LangChain ChatOpenAI wrapper (OpenAI or compatible)."""
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "api_key": api_key,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def generate_sql(
    llm: ChatOpenAI,
    schema: str,
    question: str,
    history: list[dict] | None = None,
) -> str:
    """Convert a natural language question into SQLite SQL."""
    history = history or []
    history_txt = "\n".join(
        f"{m['role'].capitalize()}: {m['content']}" for m in history[-4:]
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=schema)),
        HumanMessage(
            content=(
                f"Conversation so far:\n{history_txt}\n\n"
                f"User question: {question}"
            )
        ),
    ]
    response = llm.invoke(messages)
    return response.content if isinstance(response.content, str) else str(response.content)


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------
def classify_columns(df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    """Return (numeric_cols, date_cols, categorical_cols)."""
    numeric, dates, cats = [], [], []
    for col in df.columns:
        series = df[col]
        if re.search(r"(^|_)id$", col, re.IGNORECASE):
            cats.append(col)
            continue
        if pd.api.types.is_numeric_dtype(series):
            numeric.append(col)
        elif pd.api.types.is_datetime64_any_dtype(series):
            dates.append(col)
        elif re.search(r"date|time|month|year|day", col, re.IGNORECASE):
            # Try to interpret as datetime. pd.to_datetime raises
            # ValueError/TypeError on unparsable input — we catch only those
            # specific types and log the reason.
            try:
                pd.to_datetime(series)
                dates.append(col)
                continue
            except (ValueError, TypeError) as exc:
                logger.debug("Column %s could not be parsed as datetime: %s", col, exc)
                cats.append(col)
        else:
            cats.append(col)
    return numeric, dates, cats


def auto_chart(df: pd.DataFrame):
    """Pick a sensible Plotly chart from the shape of the result set.

    Returns a Plotly figure or None. Plotly itself can raise a variety of
    exceptions depending on the data — we catch broad exceptions here and
    log them so a bad chart never breaks the whole answer.
    """
    if df is None or df.empty or len(df.columns) < 2 or len(df) < 2:
        return None

    numeric, dates, cats = classify_columns(df)
    if not numeric:
        return None

    for d in dates:
        try:
            df[d] = pd.to_datetime(df[d])
        except (ValueError, TypeError) as exc:
            logger.debug("Failed to coerce column %s to datetime: %s", d, exc)

    common_layout = dict(
        colorway=BRAND_COLORS,
        font=dict(family="Inter, sans-serif", size=12),
        margin=dict(l=40, r=20, t=52, b=40),
        title=dict(font=dict(size=15, weight=600)),
    )

    try:
        if dates:
            fig = px.line(
                df, x=dates[0], y=numeric, markers=True,
                title=f"{', '.join(numeric)} over {dates[0]}",
                color_discrete_sequence=BRAND_COLORS,
            )
            fig.update_layout(**common_layout, hovermode="x unified",
                              legend_title_text="")
            return fig

        if cats and numeric:
            x = cats[0]
            if len(numeric) == 1:
                fig = px.bar(
                    df, x=x, y=numeric[0],
                    title=f"{numeric[0]} by {x}",
                    color_discrete_sequence=BRAND_COLORS,
                )
                fig.update_traces(marker_color=BRAND_COLORS[0])
                fig.update_layout(**common_layout, showlegend=False)
            else:
                melted = df.melt(id_vars=[x], value_vars=numeric,
                                 var_name="metric", value_name="value")
                fig = px.bar(
                    melted, x=x, y="value", color="metric",
                    barmode="group",
                    title=f"Metrics by {x}",
                    color_discrete_sequence=BRAND_COLORS,
                )
                fig.update_layout(**common_layout)
            return fig

        if len(numeric) >= 2:
            fig = px.scatter(
                df, x=numeric[0], y=numeric[1],
                trendline="ols",
                title=f"{numeric[1]} vs {numeric[0]}",
                color_discrete_sequence=BRAND_COLORS,
            )
            fig.update_traces(marker=dict(color=BRAND_COLORS[0], size=8))
            fig.update_layout(**common_layout)
            return fig

        if len(numeric) == 1:
            fig = px.line(df, y=numeric[0], title=numeric[0],
                          color_discrete_sequence=BRAND_COLORS)
            fig.update_traces(line=dict(color=BRAND_COLORS[0]))
            fig.update_layout(**common_layout)
            return fig
    except Exception as exc:  # noqa: BLE001 — Plotly failures are unpredictable
        logger.debug("auto_chart failed: %s", exc)
        return None

    return None
