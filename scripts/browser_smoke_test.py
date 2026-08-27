#!/usr/bin/env python3
"""Optional headless-browser smoke test for the standalone dashboard.

The test covers the balanced page shell, content-driven tab heights, expanded layer
reference, commissioner-precinct locator, interactive legend, Quick Decision workflow,
and browser-generated one-page report.

Install Playwright separately:
    pip install playwright
    playwright install chromium

Set CHROMIUM_EXECUTABLE when using a system Chromium binary.
"""
from __future__ import annotations

import os
from pathlib import Path


DEEP_RECT_JS = r"""(selector) => {
  const find = (root) => {
    if (!root) return null;
    const direct = root.querySelector ? root.querySelector(selector) : null;
    if (direct) return direct;
    const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
    for (const el of nodes) {
      if (el.shadowRoot) {
        const found = find(el.shadowRoot);
        if (found) return found;
      }
    }
    return null;
  };
  const el = find(document);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return {left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:r.width, height:r.height};
}"""


def assert_close(value: float, expected: float, tolerance: float = 1.0) -> None:
    assert abs(value - expected) <= tolerance, f"Expected {expected}, received {value}"


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit(
            "Playwright is optional and is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")
    executable = os.environ.get("CHROMIUM_EXECUTABLE")
    launch_kwargs: dict[str, object] = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
    }
    if executable:
        launch_kwargs["executable_path"] = executable

    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.route("https://**", lambda route: route.abort())
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(html, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_function("typeof window.CHEI === 'object'", timeout=60_000)
        page.wait_for_timeout(500)

        # Uniform 1760-pixel page shell at a 1920-pixel viewport.
        selectors = [
            ".dashboard-shell", ".site-header", ".hero", ".overview-band",
            ".main-nav", ".explore-layout", ".site-footer",
        ]
        rects = {selector: page.evaluate(DEEP_RECT_JS, selector) for selector in selectors}
        assert all(rects.values()), f"Missing layout element: {rects}"
        for selector, rect in rects.items():
            assert_close(rect["left"], 80.0)
            assert_close(rect["right"], 1840.0)
            assert_close(rect["width"], 1760.0)
        assert abs(rects[".site-footer"]["top"] - rects[".explore-layout"]["bottom"]) <= 1.0
        assert page.get_by_text("LAYER REFERENCE", exact=True).count() > 0
        assert page.get_by_text("Important limitation", exact=True).count() > 0

        # Data & Methods and Terms of Use use natural content heights and end near the footer.
        nav = page.evaluate_handle("Bokeh.documents[0].get_model_by_name('main_section_nav')")
        page.evaluate("Bokeh.documents[0].get_model_by_name('main_section_nav').active=1")
        page.wait_for_timeout(300)
        methods = page.evaluate(DEEP_RECT_JS, ".methods-page")
        methods_footer = page.evaluate(DEEP_RECT_JS, ".site-footer")
        assert methods and methods_footer
        assert_close(methods["width"], 1704.0)
        assert 20 <= methods_footer["top"] - methods["bottom"] <= 40

        page.evaluate("Bokeh.documents[0].get_model_by_name('main_section_nav').active=2")
        page.wait_for_timeout(300)
        terms = page.evaluate(DEEP_RECT_JS, ".terms-page")
        terms_footer = page.evaluate(DEEP_RECT_JS, ".site-footer")
        assert terms and terms_footer
        assert_close(terms["width"], 1704.0)
        assert 20 <= terms_footer["top"] - terms["bottom"] <= 40

        page.evaluate("Bokeh.documents[0].get_model_by_name('main_section_nav').active=0")
        page.wait_for_timeout(300)

        # Precinct location and optional all-boundaries overlay.
        page.evaluate("Bokeh.documents[0].get_model_by_name('precinct_select').value='2'")
        page.get_by_role("button", name="Find", exact=True).nth(2).click()
        page.wait_for_timeout(250)
        precinct = page.evaluate(
            "Bokeh.documents[0].get_model_by_name('selected_precinct_source').data.PCT_NO[0]"
        )
        assert str(precinct) == "2", f"Unexpected precinct selection: {precinct!r}"
        page.get_by_role(
            "button", name="Show all commissioner precinct boundaries", exact=True
        ).click()
        page.wait_for_timeout(150)
        assert page.evaluate(
            "Bokeh.documents[0].get_model_by_name('show_all_precinct_toggle').active"
        )

        # Single-class legend filter.
        page.locator("button.legend-button[data-legend-key='4']").click()
        page.wait_for_timeout(250)
        matching = page.evaluate("window.__cheiLegendContext.matches.length")
        assert matching > 0, "CHEI legend filter returned no matching tracts"
        page.evaluate("window.CHEI.clearLegendFilter()")

        # Quick Decision workflow.
        page.get_by_role("button", name="Three-factor overlap", exact=True).click()
        page.wait_for_timeout(500)
        layer = page.evaluate(
            "Bokeh.documents[0].get_model_by_name('primary_layer_select').value"
        )
        matching = page.evaluate("window.__cheiLegendContext.matches.length")
        assert layer == "hotspot", f"Unexpected Quick Decision layer: {layer!r}"
        assert matching == 5, f"Expected five all-three-high tracts, received {matching}"

        # Browser-generated one-page commissioner-precinct brief.
        page.evaluate(
            "Bokeh.documents[0].get_model_by_name('report_geography_select').value='precinct'"
        )
        with context.expect_page(timeout=10_000) as popup_info:
            page.evaluate("window.CHEI.generateReport()")
        report = popup_info.value
        report.wait_for_load_state("domcontentloaded")
        assert "Commissioner Precinct 2" in report.locator("h1").inner_text()
        assert report.locator("text=Print / Save as PDF").count() > 0
        report.close()

        nav.dispose()
        browser.close()

    if errors:
        raise SystemExit("Unexpected browser errors:\n" + "\n".join(errors))
    print(
        "Browser smoke test passed: balanced page shell, content-driven sections, "
        "expanded layer reference, precinct locator/overlay, clickable legend, "
        "Quick Decision filter, and one-page report."
    )


if __name__ == "__main__":
    main()
