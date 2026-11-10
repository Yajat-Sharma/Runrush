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

    # Baseline threshold: Phase 0 baseline allows up to 45 scripts and 34 styles
    # Phase 1 will tighten these assertions to == 0
    assert len(unnonced_scripts) <= 45, f"New un-nonced scripts introduced! Total: {len(unnonced_scripts)}"
    assert len(unnonced_styles) <= 34, f"New un-nonced styles introduced! Total: {len(unnonced_styles)}"


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

    # Baseline threshold: Phase 0 baseline allows up to 212 on* attributes
    # Phase 2 will eliminate these template-by-template down to 0
    assert len(on_attrs) <= 212, f"New on*= attributes introduced! Total: {len(on_attrs)}"
