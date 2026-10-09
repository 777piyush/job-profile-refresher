# job-profile-refresher

Daily automated Naukri profile refresh (headline rotation + resume re-upload).

## Setup
1. Create a **private** GitHub repo (the resume has your phone/email) and push this folder.
2. Repo -> Settings -> Secrets and variables -> Actions -> add `NAUKRI_EMAIL` and `NAUKRI_PASSWORD`.
3. Actions tab -> "Naukri daily refresh" -> Run workflow. Check the logs and the `screenshots` artifact.
4. It then runs daily at 9:00 AM IST.

## Local run (more reliable than GitHub Actions)
    pip install -r requirements.txt && playwright install chromium
    export NAUKRI_EMAIL=you@example.com NAUKRI_PASSWORD=...
    HEADLESS=0 python naukri_refresh.py
Schedule it with cron (`30 9 * * * cd /path && python naukri_refresh.py`) or Windows Task Scheduler.

## Known limits
- Selectors are unverified against the live site; fix them in `naukri_refresh.py` if a run fails.
- GitHub's datacenter IPs can trigger Naukri captcha/OTP. If so, run locally from your home network.
- GitHub pauses scheduled workflows after ~60 days without repo activity; push a small commit occasionally.
- Edit `config.json` to change headline variants and resume upload frequency.
- Automation may violate Naukri's terms of use. Keep it to one light refresh per day.
