"""Real-browser coverage for the editable Teloce-Py HTML Studio build."""

from __future__ import annotations

from pathlib import Path
import os
import re

import pytest


BASE_URL = os.environ.get("VEL_STUDIO_TEST_URL", "http://127.0.0.1:5179").rstrip("/")


def _url(path: str) -> str:
    return f"{BASE_URL}/{path.lstrip('/')}"


@pytest.fixture(scope="module")
def chromium_browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


def _launch(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: errors.append(f"console: {message.text}") if message.type == "error" else None,
    )
    try:
        reset = page.request.post(
            _url("/api/project/open"),
            data={"name": "starter-site"},
            timeout=5000,
        )
        assert reset.ok, reset.text()
        for attempt in range(2):
            try:
                page.goto(_url("/"), wait_until="commit", timeout=20000)
                page.locator("#code-editor").wait_for(state="visible", timeout=20000)
                page.locator(".monaco-editor").wait_for(state="visible", timeout=20000)
                page.locator("#preview-frame").wait_for(state="visible", timeout=20000)
                page.wait_for_function("() => Boolean(window.VelStudioEditor && window.VelStudioShell)", timeout=15000)
                page.frame_locator("#preview-frame").get_by_role("heading", name="Hello, creator!").wait_for(state="visible", timeout=15000)
                break
            except Exception:
                if attempt == 1:
                    raise
                errors.clear()
                page.reload(wait_until="commit", timeout=20000)
        workbench_box = page.locator(".workbench").bounding_box()
        assert workbench_box and workbench_box["height"] >= 500, workbench_box
        return context, page, errors
    except Exception:
        context.close()
        raise


def test_editor_files_preview_and_learning_flow(chromium_browser, tmp_path: Path) -> None:
    context, page, errors = _launch(chromium_browser)
    try:
        page.screenshot(path=str(tmp_path / "html-studio-editor.png"), full_page=True)

        page.get_by_role("button", name="How to use HTML Studio").click()
        page.get_by_role("heading", name="Make a website in five steps").wait_for(state="visible", timeout=5000)
        for label in ("Choose a file", "Type a small change", "Run your project", "Look at Preview", "Save your work"):
            page.get_by_text(label, exact=True).wait_for(state="visible", timeout=3000)
        page.get_by_role("button", name="Got it", exact=True).click()
        for label in ("Files", "Preview", "Output"):
            page.locator(".workspace-actions .labeled-button").filter(has_text=label).wait_for(state="visible", timeout=3000)

        explorer = page.locator("aside.explorer")
        explorer.locator("button.tree-row").first.wait_for(state="visible", timeout=12000)
        for filename in ("index.html", "styles.css", "colors.css", "app.js", "game.js", "about.html"):
            assert explorer.locator(f'button.tree-row[title="{filename}"]').is_visible()
        for filename in ("styles.css", "colors.css", "app.js", "game.js", "about.html"):
            explorer.locator(f'button.tree-row[title="{filename}"]').click()
            page.locator(".statusbar").get_by_text(f"Editing {filename}").wait_for(state="visible", timeout=12000)

        tabs = page.locator("nav[aria-label='Open files']")
        assert tabs.locator('button.tab', has_text="about.html").is_visible()
        tabs.locator('button.tab', has_text="styles.css").click()
        tabs.locator('button.tab', has_text="game.js").click()
        page.locator(".statusbar").get_by_text("Editing game.js").wait_for(state="visible", timeout=5000)

        search = page.get_by_label("Search project")
        search.fill("creator")
        page.locator(".search-result").first.wait_for(state="visible", timeout=15000)
        matching_result = page.locator(".search-result").filter(has_text="index.html").first
        assert matching_result.is_visible()
        matching_result.click()
        page.locator(".statusbar").get_by_text("Opened index.html:").wait_for(state="visible", timeout=12000)

        preview = page.frame_locator("#preview-frame")
        preview.get_by_role("heading", name="Hello, creator!").wait_for(state="visible", timeout=10000)
        preview.get_by_role("button", name="Try a button").click()
        preview.get_by_text("It works! JavaScript heard your click.").wait_for(
            state="visible", timeout=5000
        )
        preview.get_by_role("button", name="Surprise me").click()
        preview.get_by_text("Surprise! You changed the page with JavaScript.").wait_for(
            state="visible", timeout=5000
        )
        page.get_by_role("button", name="Run project").click()
        page.locator(".statusbar").get_by_text("Preview running").wait_for(state="visible", timeout=5000)

        page.get_by_role("button", name="Learn", exact=True).click()
        page.locator(".learn-hero h1").wait_for(state="visible", timeout=5000)
        page.get_by_text(re.compile(r"\d+ hours \d+ minutes of guided practice"), exact=False).wait_for(state="visible", timeout=5000)
        page.get_by_label("Search learning").fill("Three")
        page.locator(".search-panel").get_by_text("Three.js Docs", exact=True).wait_for(state="visible", timeout=5000)
        assert page.locator(".search-panel").get_by_text("MDN Learn Web Development", exact=True).count() == 0

        page.get_by_role("button", name="Play", exact=True).click()
        page.locator(".challenge-top h1").wait_for(state="visible", timeout=5000)
        page.get_by_text("Create a valid HTML document", exact=False).wait_for(state="visible", timeout=5000)
        page.get_by_role("button", name="Show hint 1 / 3").click()
        page.get_by_text("Concept clue:", exact=False).wait_for(state="visible", timeout=5000)
        page.get_by_role("button", name=re.compile(r"^Open code")).click()
        page.locator(".editor-page").wait_for(state="visible", timeout=15000)
        page.locator(".monaco-editor").wait_for(state="visible", timeout=30000)
        page.locator(".statusbar").get_by_text("Editing index.html").wait_for(state="visible", timeout=30000)
        page.get_by_role("button", name="Play", exact=True).click()
        page.get_by_role("button", name="Check challenge", exact=True).click()
        page.wait_for_function(
            "() => { const text = document.querySelector('.feedback')?.textContent || ''; return text.includes('Almost there.') || text.includes('Challenge 1 passed.'); }",
            timeout=10000,
        )
        feedback = page.locator(".feedback").inner_text()
        assert "Almost there." in feedback or "Challenge 1 passed." in feedback

        page.get_by_role("button", name="More", exact=True).click()
        page.get_by_role("heading", name="Editor preferences").wait_for(state="visible", timeout=5000)
        autosave = page.locator("button.setting-row").filter(has_text="Autosave recovery snapshots")
        assert autosave.get_by_text("On", exact=True).is_visible()
        autosave.click()
        assert autosave.get_by_text("Off", exact=True).is_visible()

        page.get_by_role("button", name="Code", exact=True).click()
        assert not errors, errors
    finally:
        context.close()


def test_editor_is_usable_on_a_small_screen(chromium_browser) -> None:
    context = chromium_browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(_url("/"), wait_until="commit", timeout=15000)
        page.locator(".monaco-editor").wait_for(state="visible", timeout=12000)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        page.get_by_role("button", name="Learn", exact=True).click()
        page.locator(".learn-hero h1").wait_for(state="visible", timeout=5000)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert not errors, errors
    finally:
        context.close()


def test_learning_catalog_and_real_validator(chromium_browser) -> None:
    context = chromium_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(_url("/"), wait_until="commit", timeout=15000)
        page.locator(".monaco-editor").wait_for(state="visible", timeout=15000)
        assert page.evaluate("() => window.HTMLStudioLearning.challenges.length") == 50
        assert page.evaluate("() => window.HTMLStudioLearning.challenges.every(item => item.hints.length === 3 && Object.keys(item.starterFiles).includes('index.html'))")
        assert page.evaluate("() => window.HTMLStudioLearning.challenges.every(item => item.lesson.example && item.lesson.keyIdea && item.lesson.steps.length === 3 && item.lesson.test && item.lesson.fix && item.lesson.reflect && item.lesson.vocabulary.length >= 3 && item.lesson.guidedPractice.length >= 5 && item.lesson.experiments.length >= 3 && item.lesson.selfCheck.length >= 3 && item.lesson.stretch)")
        assert page.evaluate("() => window.HTMLStudioLearning.duration.minutes >= 300 && window.HTMLStudioLearning.duration.label.includes('hours')")
        assert page.evaluate("() => window.HTMLStudioLearning.projects.length >= 6")
        page.get_by_role("button", name="Learn", exact=True).click()
        page.locator(".learn-hero h1").wait_for(state="visible", timeout=5000)
        page.locator(".hero-primary").click()
        page.locator(".monaco-editor").wait_for(state="visible", timeout=15000)
        page.locator(".statusbar").get_by_text("Editing index.html").wait_for(state="visible", timeout=12000)
        page.evaluate("""async () => {
          await window.VelStudioWorkspace.write('index.html', '<!doctype html><html><head><title>Lesson</title></head><body><h1>Hello, Web!</h1></body></html>');
        }""")
        page.get_by_role("button", name="Play", exact=True).click()
        page.locator(".challenge-top h1").wait_for(state="visible", timeout=5000)
        page.get_by_text("WORDS TO KNOW", exact=True).wait_for(state="visible", timeout=5000)
        page.get_by_text("GUIDED WORKSHOP", exact=True).wait_for(state="visible", timeout=5000)
        page.get_by_text("EXPERIMENTS", exact=True).wait_for(state="visible", timeout=5000)
        page.get_by_text("SELF-CHECK", exact=True).wait_for(state="visible", timeout=5000)
        page.get_by_text("STRETCH TASK", exact=True).wait_for(state="visible", timeout=5000)
        page.get_by_role("button", name="Check challenge", exact=True).click()
        page.get_by_text("Challenge 1 passed.", exact=False).wait_for(state="visible", timeout=8000)
        assert page.evaluate("() => window.HTMLStudioLearning.getState().completedChallenges.includes(1)")
        page.locator(".check-card").get_by_role("button", name="Next challenge →", exact=True).click()
        page.get_by_text("Lesson 2 of 50", exact=True).wait_for(state="visible", timeout=5000)
        assert page.get_by_role("button", name="← Previous", exact=True).is_enabled()
        page.get_by_role("button", name="← Previous", exact=True).click()
        page.get_by_text("Lesson 1 of 50", exact=True).wait_for(state="visible", timeout=5000)
        assert not errors, errors
    finally:
        try:
            page.evaluate("() => window.VelStudioWorkspace.openProject('starter-site')")
        except Exception:
            pass
        context.close()


def test_lesson_room_scrolls_and_has_beginner_navigation(chromium_browser) -> None:
    context = chromium_browser.new_context(viewport={"width": 1270, "height": 590})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(_url("/"), wait_until="commit", timeout=15000)
        page.locator(".monaco-editor").wait_for(state="visible", timeout=15000)
        page.get_by_role("button", name="Learn", exact=True).click()
        page.locator(".learn-hero h1").wait_for(state="visible", timeout=5000)
        page.get_by_role("button", name="Open challenge room", exact=True).click()
        page.locator(".challenge-top h1").wait_for(state="visible", timeout=5000)
        page.get_by_role("navigation", name="Lesson navigation").wait_for(state="visible", timeout=5000)
        assert page.get_by_role("button", name="← Back to lessons", exact=True).is_visible()
        assert page.get_by_role("button", name="Next →", exact=True).is_disabled()
        scroll = page.locator(".challenge-page")
        metrics = scroll.evaluate("element => ({ top: element.scrollTop, height: element.scrollHeight, client: element.clientHeight })")
        assert metrics["height"] > metrics["client"]
        scroll.evaluate("element => element.scrollTop = element.scrollHeight")
        assert scroll.evaluate("element => element.scrollTop > 0")
        page.get_by_text("STRETCH TASK", exact=True).wait_for(state="visible", timeout=5000)
        page.locator(".challenge-nav").scroll_into_view_if_needed()
        page.get_by_role("button", name="← Back to lessons", exact=True).click()
        page.locator(".learn-hero h1").wait_for(state="visible", timeout=5000)
        assert not errors, errors
    finally:
        context.close()


def test_local_editor_keeps_files_editable_without_external_editor_cdn(chromium_browser) -> None:
    context = chromium_browser.new_context(viewport={"width": 1100, "height": 760})
    page = context.new_page()
    try:
        page.goto(_url("/"), wait_until="commit", timeout=15000)
        page.locator(".monaco-editor").wait_for(state="visible", timeout=12000)
        assert page.locator(".monaco-editor").is_visible()
        assert not page.locator("script[src*='cdn.jsdelivr.net']").count()
        assert page.locator("script[src*='/static/vendor/monaco/']").count() >= 1
    finally:
        context.close()


def test_editor_preview_splitter_is_keyboard_and_pointer_resizable(chromium_browser) -> None:
    context = chromium_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    try:
        page.goto(_url("/"), wait_until="commit", timeout=15000)
        page.locator(".monaco-editor").wait_for(state="visible", timeout=15000)
        page.locator(".split-divider").wait_for(state="visible", timeout=5000)
        page.wait_for_timeout(300)
        divider = page.locator(".split-divider")
        before = page.locator(".code-column").bounding_box()
        divider.focus()
        page.keyboard.press("ArrowRight")
        after_keyboard = page.locator(".code-column").bounding_box()
        assert before and after_keyboard and after_keyboard["width"] > before["width"]
        box = divider.bounding_box()
        assert box
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 200)
        page.mouse.down()
        page.mouse.move(box["x"] - 100, box["y"] + 200, steps=5)
        page.mouse.up()
        after_pointer = page.locator(".code-column").bounding_box()
        assert after_pointer and after_pointer["width"] < after_keyboard["width"]
        page.keyboard.press("Control+Shift+F")
        assert page.get_by_label("Search project").evaluate("element => document.activeElement === element")
    finally:
        context.close()


def test_challenge_room_uses_the_real_preview_renderer(chromium_browser) -> None:
    context, page, errors = _launch(chromium_browser)
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.get_by_role("button", name="Play", exact=True).click()
        page.locator(".challenge-page").wait_for(state="visible", timeout=5000)
        page.get_by_role("button", name="Run preview", exact=True).click()
        frame = page.locator("#challenge-preview-frame")
        frame.wait_for(state="visible", timeout=20000)
        page.frame_locator("#challenge-preview-frame").get_by_role(
            "heading", name="Hello, creator!"
        ).wait_for(state="visible", timeout=15000)
        page.get_by_role("button", name="Run preview", exact=True).click()
        page.frame_locator("#challenge-preview-frame").get_by_role(
            "heading", name="Hello, creator!"
        ).wait_for(state="visible", timeout=10000)
        assert not errors, errors
    finally:
        context.close()


def test_neon_settings_and_editor_celebration_are_real(chromium_browser) -> None:
    context, page, errors = _launch(chromium_browser)
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.get_by_role("button", name="More", exact=True).click()
        page.get_by_role("heading", name="Editor preferences").wait_for(state="visible", timeout=5000)
        page.locator(".settings-page select").first.select_option("neon-light")
        assert page.evaluate("document.documentElement.dataset.htmlStudioTheme") == "neon-light"
        assert page.evaluate("localStorage.getItem('html-studio-settings').includes('neon-light')")
        page.get_by_role("button", name="Code", exact=True).click()
        page.locator(".monaco-editor").wait_for(state="visible", timeout=15000)
        assert page.evaluate("window.VelStudioEditor.theme()") == "html-studio-neon-light"
        page.get_by_role("button", name="Run project").click()
        page.locator(".celebration-layer").wait_for(state="visible", timeout=5000)
        assert page.locator(".banana-spark").count() == 18
        assert not errors, errors
    finally:
        context.close()
