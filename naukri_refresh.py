"""Naukri task runner: reads tasks.yml and runs each enabled step in order.

Env vars: NAUKRI_EMAIL, NAUKRI_PASSWORD. Optional: HEADLESS=0 (show browser), DRY_RUN=1/0 (overrides tasks.yml).
Never touches CTC / salary fields.
"""
import datetime as dt
import os
import sys
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
ART = ROOT / "artifacts"
ART.mkdir(exist_ok=True)
LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
FORBIDDEN = ("ctc", "salary", "compensation")


def shot(page, name):
    try:
        page.screenshot(path=str(ART / f"{name}.png"), full_page=True)
    except Exception:
        pass


def login(page):
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#usernameField", timeout=30000)
    except Exception:
        shot(page, "login_blocked")
        raise RuntimeError("Login form never appeared (Naukri may be blocking this machine). See login_blocked.png")
    page.fill("#usernameField", os.environ["NAUKRI_EMAIL"])
    page.fill("#passwordField", os.environ["NAUKRI_PASSWORD"])
    page.click("button[type=submit]")
    page.wait_for_url("**/mnjuser/**", timeout=30000)


def open_card(page, edit_sel):
    page.goto(PROFILE_URL, wait_until="networkidle")
    page.locator(edit_sel).first.click(timeout=15000)


def save(page, label, dry):
    shot(page, f"{label}_filled")
    if dry:
        return "DRY RUN: filled, not saved"
    page.get_by_role("button", name="Save").first.click()
    page.wait_for_timeout(2500)
    return "saved"


def t_headline(page, t, dry):
    values = t["values"]
    text = values[dt.date.today().toordinal() % len(values)]
    if len(text) > 250:
        raise ValueError(f"headline is {len(text)} chars, max 250")
    open_card(page, "#lazyResumeHead .edit, .resumeHeadline .edit")
    page.locator("textarea#resumeHeadlineTxt, textarea[name=resumeHeadline]").first.fill(text)
    return save(page, "headline", dry)


def t_summary(page, t, dry):
    text = " ".join(str(t["value"]).split())
    if len(text) > 1000:
        raise ValueError(f"summary is {len(text)} chars, max 1000")
    open_card(page, "#lazyProfileSummary .edit, .profileSummary .edit")
    page.locator("textarea#profileSummaryTxt, textarea[name=profileSummary], .profileSummary textarea").first.fill(text)
    return save(page, "summary", dry)


def t_skills(page, t, dry):
    open_card(page, "#lazyKeySkills .edit, .keySkills .edit")
    box = page.locator("input#keySkillSugg, input[placeholder*='kill' i]").first
    for skill in t["add"]:
        box.fill(skill)
        page.wait_for_timeout(800)
        sug = page.locator("ul.sugCont li, .sugCont li, .Sdrop li").first
        if sug.count():
            sug.click()
        else:
            box.press("Enter")
    return save(page, "skills", dry)


def t_resume(page, t, dry):
    path = ROOT / t.get("file", "resume/resume.pdf")
    if not path.exists():
        raise FileNotFoundError(path)
    page.goto(PROFILE_URL, wait_until="networkidle")
    if dry:
        return f"DRY RUN: would upload {path.name}"
    page.set_input_files("input[type=file]", str(path))
    page.wait_for_timeout(5000)
    return "uploaded"


HANDLERS = {
    "update_headline": t_headline,
    "update_summary": t_summary,
    "update_skills": t_skills,
    "upload_resume": t_resume,
}


def main():
    try:
        cfg = yaml.safe_load((ROOT / "tasks.yml").read_text())
    except yaml.YAMLError as e:
        sys.exit(f"tasks.yml is not valid YAML (check the spaces at line starts): {e}")
    dry = bool(cfg.get("settings", {}).get("dry_run", True))
    if os.getenv("DRY_RUN") in ("0", "1"):
        dry = os.getenv("DRY_RUN") == "1"
    tasks = [t for t in cfg.get("tasks", []) if t.get("enabled", True)]
    print(f"dry_run={dry}, {len(tasks)} task(s)")

    for t in tasks:
        a = t.get("action", "")
        if any(w in a.lower() for w in FORBIDDEN):
            sys.exit(f"Refusing task '{a}': CTC/salary is never touched.")
        if a not in HANDLERS:
            sys.exit(f"Unknown action '{a}'. Allowed: {', '.join(HANDLERS)}")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.getenv("HEADLESS", "1") != "0", args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 800}, locale="en-IN", timezone_id="Asia/Kolkata",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        try:
            login(page)
        except Exception as e:
            print(f"[fail] login: {e}", file=sys.stderr)
            browser.close()
            sys.exit(1)
        for t in tasks:
            a = t["action"]
            try:
                msg = HANDLERS[a](page, t, dry)
                results.append((a, True, msg))
            except Exception as e:
                shot(page, f"{a}_failed")
                results.append((a, False, str(e).splitlines()[0]))
        browser.close()

    print("\n===== SUMMARY =====")
    for a, ok, msg in results:
        print(f"{'OK  ' if ok else 'FAIL'} {a}: {msg}")
    sys.exit(0 if all(ok for _, ok, _ in results) else 1)


if __name__ == "__main__":
    main()
