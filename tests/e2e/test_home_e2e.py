from playwright.sync_api import sync_playwright


def test_e2e_home_page(live_server):
    """R4: Playwright carga la raíz y valida el DOM."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(live_server.url)
        assert "Planificador de Turnos" in page.title()
        heading = page.locator("h1")
        assert "Planificador de Turnos" in heading.inner_text()
        browser.close()
