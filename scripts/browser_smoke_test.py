#!/usr/bin/env python3
"""Optional headless-browser smoke test for the standalone dashboard.

This test is not required to run the dashboard. Install Playwright separately:
    pip install playwright
    playwright install chromium

Set CHROMIUM_EXECUTABLE when using a system Chromium binary.
"""
from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit(
            "Playwright is optional and is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    root = Path(__file__).resolve().parents[1]
    html_path = root / "index.html"
    html = html_path.read_text(encoding="utf-8")
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
        context = browser.new_context(viewport={"width": 1600, "height": 900})
        page = context.new_page()
        page.route("https://**", lambda route: route.abort())
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(html, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_function("typeof window.CHEI === 'object'", timeout=60_000)
        page.wait_for_timeout(500)

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

        browser.close()

    if errors:
        raise SystemExit("Unexpected browser errors:\n" + "\n".join(errors))
    print(
        "Browser smoke test passed: precinct locator/overlay, clickable legend, "
        "Quick Decision filter, and one-page report."
    )


if __name__ == "__main__":
    main()
