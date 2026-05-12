"""E2E tests for the QuantumSafe Optimize frontend flow.

Tests:
- Landing page loads correctly
- Auth modal opens and closes
- Navigation between sections works
- Job submission flow (demo mode)
- Responsive layout at different viewport sizes

Requires: playwright (install with: pip install playwright && playwright install)
"""

import pytest
from playwright.async_api import async_playwright, expect

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
async def browser_context():
    """Launch browser and create context."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        yield context
        await browser.close()


@pytest.fixture
async def page(browser_context):
    """Create a new page for each test."""
    p = await browser_context.new_page()
    yield p
    await p.close()


@pytest.mark.e2e
async def test_landing_page_loads(page):
    """Verify the landing page loads with key elements."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Hero section visible
    await expect(page.locator(".hero")).to_be_visible()
    await expect(page.locator("#hero-title")).to_be_visible()

    # CTA buttons present
    await expect(page.locator("text=Get Started Free")).to_be_visible()
    await expect(page.locator("text=See How It Works")).to_be_visible()

    # Features section
    await expect(page.locator("#features")).to_be_visible()

    # Navigation links
    await expect(page.locator(".nav-links a")).to_have_count(7)


@pytest.mark.e2e
async def test_auth_modal_opens(page):
    """Verify auth modal opens on CTA click."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Click Start Free Trial
    await page.click("text=Start Free Trial")

    # Modal should appear
    await expect(page.locator(".auth-modal.active")).to_be_visible()
    await expect(page.locator("#signupForm")).to_be_visible()

    # Close modal via backdrop
    await page.click(".auth-modal-overlay")
    await expect(page.locator(".auth-modal.active")).not_to_be_visible()


@pytest.mark.e2e
async def test_navigation_scroll(page):
    """Verify smooth scroll to sections on nav click."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Click Algorithms nav link
    await page.click(".nav-links a[href='#algorithms']")
    await page.wait_for_timeout(500)

    # Should be scrolled to algorithms section
    algorithms_section = page.locator("#algorithms")
    bbox = await algorithms_section.bounding_box()
    assert bbox is not None
    assert bbox["y"] < 200  # Near top of viewport


@pytest.mark.e2e
async def test_algorithm_tabs_switch(page):
    """Verify algorithm tabs switch content correctly."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Scroll to algorithms section
    await page.evaluate("document.getElementById('algorithms').scrollIntoView()")
    await page.wait_for_timeout(300)

    # VQE tab click
    await page.click('[data-tab="vqe"]')
    vqe_panel = page.locator("#vqe.active")
    await expect(vqe_panel).to_be_visible()

    # Annealing tab click
    await page.click('[data-tab="annealing"]')
    annealing_panel = page.locator("#annealing.active")
    await expect(annealing_panel).to_be_visible()


@pytest.mark.e2e
async def test_dashboard_loads(page):
    """Verify dashboard loads with sidebar and overview."""
    await page.goto(f"{BASE_URL}/dashboard.html")
    await page.wait_for_load_state("networkidle")

    # Sidebar visible
    await expect(page.locator(".sidebar")).to_be_visible()

    # Top bar
    await expect(page.locator(".topbar")).to_be_visible()

    # Overview section active
    await expect(page.locator("#section-overview.active")).to_be_visible()

    # Stats present
    await expect(page.locator(".stat-card")).to_have_count(4)


@pytest.mark.e2e
async def test_theme_toggle_dashboard(page):
    """Verify dashboard theme toggle works."""
    await page.goto(f"{BASE_URL}/dashboard.html")
    await page.wait_for_load_state("networkidle")

    # Default is dark
    theme = await page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert theme == "dark"

    # Click theme toggle
    await page.click("#theme-toggle")

    # Should switch to light
    theme = await page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert theme == "light"


@pytest.mark.e2e
async def test_mobile_layout_landing(page):
    """Verify landing page mobile layout at 375px width."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Nav links should be hidden
    nav_links = page.locator(".nav-links")
    style = await nav_links.evaluate("el => window.getComputedStyle(el).display")
    assert style == "none"

    # Mobile menu button visible
    await expect(page.locator(".mobile-menu-btn")).to_be_visible()

    # Hero stacks vertically
    hero_container = page.locator(".hero-container")
    flex_dir = await hero_container.evaluate("el => window.getComputedStyle(el).flexDirection")
    assert flex_dir == "column"


@pytest.mark.e2e
async def test_mobile_menu_toggle(page):
    """Verify mobile menu opens and closes."""
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Click mobile menu button
    await page.click(".mobile-menu-btn")

    # Mobile menu should appear
    await expect(page.locator(".mobile-menu")).to_be_visible()

    # Click a nav link to close
    await page.click(".mobile-menu .nav-links a")
    await expect(page.locator(".mobile-menu")).not_to_be_visible()


@pytest.mark.e2e
async def test_landing_theme_toggle(page):
    """Verify landing page theme toggle works."""
    await page.goto(BASE_URL)
    await page.wait_for_load_state("networkidle")

    # Default is dark
    theme = await page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert theme == "dark"

    # Click theme toggle
    await page.click("#landing-theme-toggle")

    # Should switch to light
    theme = await page.evaluate("document.documentElement.getAttribute('data-theme')")
    assert theme == "light"

    # Persist in localStorage
    stored = await page.evaluate("localStorage.getItem('landing-theme')")
    assert stored == "light"
