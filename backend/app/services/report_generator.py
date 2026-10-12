"""Renders a Markdown/HTML report for a completed (or in-progress) test run,
citing the exact MASVS / MASTG / MASWE IDs behind every result."""
from __future__ import annotations

import uuid
from collections import defaultdict

from jinja2 import Environment, select_autoescape
from sqlalchemy.orm import Session, joinedload

from app import models

MARKDOWN_TEMPLATE = """\
# MASVS Report — {{ app.filename }}

- **Project:** {{ project.name }}
- **Platform:** {{ app.platform.value }}
- **Package:** {{ app.package_name or "n/a" }}
- **Catalog version:** {{ test_run.catalog_version }}
- **Tester:** {{ test_run.tester_name or "n/a" }}
- **Started:** {{ test_run.started_at }}
- **Status:** {{ test_run.status.value }}

## Summary

| Status | Count |
|---|---|
{% for status, count in summary.items() -%}
| {{ status }} | {{ count }} |
{% endfor %}

## Controls by category

{% for category, results in by_category.items() %}
### {{ category }}

{% for r in results %}
#### {{ r.control.code }} — {{ r.control.title }}

- **Status:** {{ r.status.value }} ({{ r.method.value }})
- **MASTG tests:** {{ r.control.mastg_tests | join(", ") }}
- **MASWE:** {{ r.control.maswe_ids | join(", ") }}
- **Description:** {{ r.control.description }}
{% if r.evidence %}- **Evidence:** {{ r.evidence }}{% endif %}
{% if r.notes %}- **Notes:** {{ r.notes }}{% endif %}

{% endfor %}
{% endfor %}

## Findings

{% if findings %}
{% for f in findings %}
### {{ f.title }} ({{ f.severity.value }})

{{ f.description }}

{% if f.evidence %}**Evidence:** {{ f.evidence }}{% endif %}
{% if f.remediation %}**Remediation:** {{ f.remediation }}{% endif %}

{% endfor %}
{% else %}
No findings recorded.
{% endif %}
"""

HTML_WRAPPER = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>MASVS Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  table {{ border-collapse: collapse; }}
  th, td {{ border: 1px solid #ddd; padding: 4px 10px; text-align: left; }}
  h3 {{ border-bottom: 1px solid #eee; padding-bottom: 4px; margin-top: 2rem; }}
  code {{ background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""

_env = Environment(autoescape=select_autoescape(enabled_extensions=()))


def _build_context(db: Session, test_run_id: uuid.UUID) -> dict:
    test_run = (
        db.query(models.TestRun)
        .options(joinedload(models.TestRun.app).joinedload(models.App.project))
        .get(test_run_id)
    )
    if not test_run:
        raise ValueError(f"TestRun {test_run_id} not found")

    results = (
        db.query(models.ControlResult)
        .options(joinedload(models.ControlResult.control))
        .filter(models.ControlResult.test_run_id == test_run_id)
        .join(models.MasvsControl)
        .order_by(models.MasvsControl.category, models.MasvsControl.sort_order)
        .all()
    )
    findings = (
        db.query(models.Finding)
        .filter(models.Finding.test_run_id == test_run_id)
        .order_by(models.Finding.severity.desc())
        .all()
    )

    by_category: dict[str, list] = defaultdict(list)
    summary: dict[str, int] = defaultdict(int)
    for r in results:
        by_category[r.control.category].append(r)
        summary[r.status.value] += 1

    return {
        "test_run": test_run,
        "app": test_run.app,
        "project": test_run.app.project,
        "by_category": dict(by_category),
        "summary": dict(summary),
        "findings": findings,
    }


def render_markdown(db: Session, test_run_id: uuid.UUID) -> str:
    context = _build_context(db, test_run_id)
    template = _env.from_string(MARKDOWN_TEMPLATE)
    return template.render(**context)


def render_html(db: Session, test_run_id: uuid.UUID) -> str:
    # Rendered directly from the same Jinja context into real HTML markup,
    # rather than converting the Markdown output, to keep tables/headings
    # faithful without pulling in an extra markdown-to-HTML dependency.
    context = _build_context(db, test_run_id)
    html_template = _env.from_string(_HTML_TEMPLATE)
    body = html_template.render(**context)
    return HTML_WRAPPER.format(body=body)


_HTML_TEMPLATE = """\
<h1>MASVS Report — {{ app.filename }}</h1>
<ul>
  <li><b>Project:</b> {{ project.name }}</li>
  <li><b>Platform:</b> {{ app.platform.value }}</li>
  <li><b>Package:</b> {{ app.package_name or "n/a" }}</li>
  <li><b>Catalog version:</b> {{ test_run.catalog_version }}</li>
  <li><b>Tester:</b> {{ test_run.tester_name or "n/a" }}</li>
  <li><b>Started:</b> {{ test_run.started_at }}</li>
  <li><b>Status:</b> {{ test_run.status.value }}</li>
</ul>

<h2>Summary</h2>
<table>
<tr><th>Status</th><th>Count</th></tr>
{% for status, count in summary.items() -%}
<tr><td>{{ status }}</td><td>{{ count }}</td></tr>
{% endfor %}
</table>

<h2>Controls by category</h2>
{% for category, results in by_category.items() %}
<h3>{{ category }}</h3>
{% for r in results %}
<h4><code>{{ r.control.code }}</code> — {{ r.control.title }}</h4>
<ul>
  <li><b>Status:</b> {{ r.status.value }} ({{ r.method.value }})</li>
  <li><b>MASTG tests:</b> {{ r.control.mastg_tests | join(", ") }}</li>
  <li><b>MASWE:</b> {{ r.control.maswe_ids | join(", ") }}</li>
  <li><b>Description:</b> {{ r.control.description }}</li>
  {% if r.evidence %}<li><b>Evidence:</b> {{ r.evidence }}</li>{% endif %}
  {% if r.notes %}<li><b>Notes:</b> {{ r.notes }}</li>{% endif %}
</ul>
{% endfor %}
{% endfor %}

<h2>Findings</h2>
{% if findings %}
{% for f in findings %}
<h3>{{ f.title }} ({{ f.severity.value }})</h3>
<p>{{ f.description }}</p>
{% if f.evidence %}<p><b>Evidence:</b> {{ f.evidence }}</p>{% endif %}
{% if f.remediation %}<p><b>Remediation:</b> {{ f.remediation }}</p>{% endif %}
{% endfor %}
{% else %}
<p>No findings recorded.</p>
{% endif %}
"""
