"""Tests for Content Security Policy template linting.

Verifies that templates comply with CSP constraints:
- No javascript: pseudo-protocols
- No un-nonced inline <script> or <style> tags (tightened in Phase 1)
- No inline on*= attributes (tightened in Phase 2)
"""

import os
import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

ON_ATTR_RE = re.compile(r'\b(on[a-zA-Z]+)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.IGNORECASE)
SCRIPT_TAG_RE = re.compile(r'<script\b([^>]*)>', re.IGNORECASE)
STYLE_TAG_RE = re.compile(r'<style\b([^>]*)>', re.IGNORECASE)
JS_URL_RE = re.compile(r'\b(href|src|action)\s*=\s*["\']\s*(javascript:[^"\']*)["\']', re.IGNORECASE)


def get_template_files():
    files = []
    for root, _, filenames in os.walk(TEMPLATES_DIR):
        for f in filenames:
            if f.endswith(".html"):
                files.append(Path(root) / f)
    return sorted(files)


def test_no_javascript_pseudo_urls():
    """Assert that no template uses href="javascript:..." or action="javascript:...\"."""
    violations = []
    for template_path in get_template_files():
        content = template_path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(content.splitlines(), 1):
            for m in JS_URL_RE.finditer(line):
                rel_path = template_path.relative_to(TEMPLATES_DIR.parent).as_posix()
                violations.append(f"{rel_path}:{line_no} -> {m.group(0)}")

    assert not violations, "Found javascript: URLs in templates:\n" + "\n".join(violations)


def test_inline_scripts_and_styles_have_nonces():
    """Check that executable inline <script> and <style> tags have nonces.

    Baseline allowlist will be reduced to 0 in Phase 1.
    """
    unnonced_scripts = []
    unnonced_styles = []

    for template_path in get_template_files():
        content = template_path.read_text(encoding="utf-8", errors="replace")
        rel_path = template_path.relative_to(TEMPLATES_DIR.parent).as_posix()

        for m in SCRIPT_TAG_RE.finditer(content):
            attrs = m.group(1)
            is_external = "src=" in attrs
            is_json = "application/json" in attrs
            has_nonce = re.search(r'\bnonce=(["\'])\s*\{\{\s*csp_nonce\(\)\s*\}\}\s*\1', attrs)
            if not is_external and not is_json and not has_nonce:
                line_no = content[:m.start()].count("\n") + 1
                unnonced_scripts.append(f"{rel_path}:{line_no}")

        for m in STYLE_TAG_RE.finditer(content):
            attrs = m.group(1)
            has_nonce = re.search(r'\bnonce=(["\'])\s*\{\{\s*csp_nonce\(\)\s*\}\}\s*\1', attrs)
            if not has_nonce:
                line_no = content[:m.start()].count("\n") + 1
                unnonced_styles.append(f"{rel_path}:{line_no}")

    # Phase 1: All inline scripts and styles must have nonces
    assert not unnonced_scripts, "Found un-nonced scripts:\n" + "\n".join(unnonced_scripts)
    assert not unnonced_styles, "Found un-nonced styles:\n" + "\n".join(unnonced_styles)


def test_on_event_attributes_count():
    """Check that inline on*= attributes do not exceed Phase 0 baseline.

    Baseline allowlist will be reduced to 0 template-by-template in Phase 2.
    """
    on_attrs = []
    for template_path in get_template_files():
        content = template_path.read_text(encoding="utf-8", errors="replace")
        rel_path = template_path.relative_to(TEMPLATES_DIR.parent).as_posix()
        for line_no, line in enumerate(content.splitlines(), 1):
            for m in ON_ATTR_RE.finditer(line):
                on_attrs.append(f"{rel_path}:{line_no} ({m.group(1)})")

    # Phase 2: All inline on*= attributes must be completely eliminated
    assert not on_attrs, f"Found remaining on*= attributes:\n" + "\n".join(on_attrs)


def test_data_share_attribute_is_html_escaped():
    """Regression test: data-share='...|tojson' attributes must pipe through |e
    (HTML-escape) so that apostrophes in run data cannot break the HTML attribute.

    Without |e, a run insight like "Yajat's run" would emit a literal single quote
    inside a single-quoted attribute value, causing a SyntaxError in the browser
    that halts all subsequent JS and breaks navigation.
    """
    index_path = TEMPLATES_DIR / "index.html"
    if not index_path.exists():
        return  # nothing to check in stripped-down test environments

    content = index_path.read_text(encoding="utf-8", errors="replace")

    # Find data-share attributes using tojson but NOT |e (HTML-escape)
    unescaped_re = re.compile(
        r'data-share=[\'"].*?tojson(?!\|e)\s*\}\}[\'"]',
        re.DOTALL,
    )
    matches = unescaped_re.findall(content)
    assert not matches, (
        "Found data-share attribute(s) using |tojson without |e (HTML-escape). "
        "Any apostrophe in run data will break the HTML attribute and cause a JS SyntaxError. "
        "Fix: use |tojson|e instead of |tojson in single-quoted HTML attributes.\n"
        f"Matches: {matches}"
    )