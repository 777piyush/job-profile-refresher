"""Daily Naukri profile refresh (headline rotation + periodic resume re-upload).

Naukri ranks recently-updated profiles higher in recruiter searches. This script
does the same thing you would do by hand: log in, change the resume headline
(rotating between the variants in config.json), save, and re-upload the resume
every N days.

Env vars: NAUKRI_EMAIL, NAUKRI_PASSWORD
Optional: HEADLESS=0 to watch the browser locally.
"""
import json
import os
import sys
import datetime as dt
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ROOT = Path(__file__).parent
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)
CFG = json.loads((ROOT / "config.json").read_text())

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"


def shot(page, name):
    try:
        page.screenshot(path=str(ART / f"{name}.png"), full_page=True)
    except Exception:
        pass


def login(page):
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.fill("#usernameField", os.environ["NAUKRI_EMAIL"])
    page.fill("#passwordField", os.environ["NAUKRI_PASSWORD"])
    page.click("button[type=submit]")
    page.wait_for_url("**/mnjuser/**", timeout=30000)


def update_headline(page, headline):
    page.goto(PROFILE_URL, wait_until="networkidle")
    # Pencil icon in the "Resume headline" card (selector may change; check screenshot on failure)
    page.locator("#lazyResumeHead .edit, .resumeHeadline .edit").first.click()
    box = page.locator("textarea#resumeHeadlineTxt, textarea[name=resumeHeadline]").first
    box.fill(headline)
    page.get_by_role("button", name="Save").first.click()
    page.wait_for_timeout(2500)


def upload_resume(page, path):
    page.goto(PROFILE_URL, wait_until="networkidle")
    page.set_input_files("input[type=file]", path)
    page.wait_for_timeout(5000)


def main():
    today = dt.date.today()
    headlines = CFG["headlines"]
    headline = headlines[today.toordinal() % len(headlines)]
    # Alternate a trailing marker-free tweak so even a single headline still "changes"
    if len(headlines) == 1 and today.toordinal() % 2:
        headline += " "

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("HEADLESS", "1") != "0")
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        page = ctx.new_page()
        try:
            login(page)
            update_headline(page, headline)
            print(f"[ok] headline updated: {headline}")
            n = CFG["upload_resume_every_n_days"]
            if n and today.toordinal() % n == 0:
                upload_resume(page, str(ROOT / CFG["resume_path"]))
                print("[ok] resume re-uploaded")
            shot(page, "success")
        except (PWTimeout, Exception) as e:
            shot(page, "failure")
            print(f"[fail] {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
