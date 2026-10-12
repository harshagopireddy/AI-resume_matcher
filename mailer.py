"""Email notifications (shortlist / interview invitations).

Sends real mail via SMTP when credentials are configured in config.py (or via
environment variables). When they are not configured, the message is written
to the console and stored in the `email_log` table so it can still be reviewed.
"""
import json
import os
import smtplib
import ssl
from email.message import EmailMessage

import config


def load_saved():
    """Return the runtime SMTP settings saved from the admin UI (or {})."""
    try:
        with open(config.MAIL_SETTINGS_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    with open(config.MAIL_SETTINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    try:
        os.chmod(config.MAIL_SETTINGS_PATH, 0o600)
    except OSError:
        pass


def effective():
    """Merge config defaults with any saved runtime settings."""
    saved = load_saved()
    return {
        "host": saved.get("host") or config.SMTP_HOST,
        "port": int(saved.get("port") or config.SMTP_PORT),
        "user": saved.get("user") or config.SMTP_USER,
        "password": saved.get("password") or config.SMTP_PASSWORD,
        "from": saved.get("from") or config.SMTP_FROM,
        "from_name": saved.get("from_name") or config.SMTP_FROM_NAME,
        "tls": saved.get("tls") if isinstance(saved.get("tls"), bool) else config.SMTP_TLS,
    }


def email_configured() -> bool:
    s = effective()
    return bool(s["host"] and s["user"] and s["password"])


def send_email(to_email: str, subject: str, text: str, html: str = None):
    """Send an email. Returns (sent: bool, detail: str)."""
    if not to_email:
        return False, "no recipient email"
    if not email_configured():
        return False, "email not configured"

    s = effective()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{s['from_name']} <{s['from'] or s['user']}>"
    msg["To"] = to_email
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        if s["tls"]:
            with smtplib.SMTP(s["host"], s["port"], timeout=25) as sv:
                sv.ehlo()
                sv.starttls(context=ssl.create_default_context())
                sv.ehlo()
                sv.login(s["user"], s["password"])
                sv.send_message(msg)
        else:
            with smtplib.SMTP_SSL(s["host"], s["port"], timeout=25) as sv:
                sv.login(s["user"], s["password"])
                sv.send_message(msg)
        return True, "sent"
    except Exception as exc:  # noqa: BLE001 - surface any SMTP failure
        return False, str(exc)


def build_shortlist_email(candidate, job_title, company_name, hr_name,
                          location, website=None, employment_type="Full-time"):
    """Return (subject, text, html) for a professional interview invitation."""
    hr_name = hr_name or "The HR Team"
    company_name = company_name or "our company"
    location = location or "To be confirmed"
    subject = f"Interview Invitation — {job_title} at {company_name}"

    text = f"""Dear {candidate},

Congratulations! We have reviewed your resume and you have been SHORTLISTED
for the position of {job_title} at {company_name}.

You are cordially invited to attend an interview. The details are below:

    Position        : {job_title}
    Company         : {company_name}
    Employment type : {employment_type}
    Interview venue : {location}
    Contact (HR)    : {hr_name}
{("    Website         : " + website) if website else ""}

Please reply to this email to confirm your availability. Kindly carry an
updated copy of your resume and any relevant portfolio or documents on the
day of the interview.

We look forward to meeting you.

Warm regards,
{hr_name}
{company_name}
"""

    html = f"""\
<div style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:560px;margin:auto;
            border:1px solid #e7eaf3;border-radius:16px;overflow:hidden;color:#0f172a">
  <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:24px 28px;color:#fff">
    <div style="font-size:20px;font-weight:800">HireMatch</div>
    <div style="opacity:.9;font-size:13px">{company_name}</div>
  </div>
  <div style="padding:28px">
    <p style="margin:0 0 14px">Dear {candidate},</p>
    <p style="margin:0 0 14px">Congratulations! We have reviewed your resume and you
       have been <b style="color:#16a34a">shortlisted</b> for the position of
       <b>{job_title}</b> at <b>{company_name}</b>.</p>
    <p style="margin:0 0 10px">You are cordially invited to attend an interview:</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px">
      <tr><td style="padding:8px 0;color:#64748b;width:150px">Position</td><td style="padding:8px 0"><b>{job_title}</b></td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Company</td><td style="padding:8px 0"><b>{company_name}</b></td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Employment type</td><td style="padding:8px 0">{employment_type}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Interview venue</td><td style="padding:8px 0"><b>{location}</b></td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Contact (HR)</td><td style="padding:8px 0">{hr_name}</td></tr>
      {f'<tr><td style="padding:8px 0;color:#64748b">Website</td><td style="padding:8px 0">{website}</td></tr>' if website else ''}
    </table>
    <p style="margin:0 0 14px">Please reply to this email to confirm your availability.
       Kindly carry an updated copy of your resume and any relevant portfolio or
       documents on the day of the interview.</p>
    <p style="margin:0 0 4px">We look forward to meeting you.</p>
    <p style="margin:16px 0 0">Warm regards,<br><b>{hr_name}</b><br>{company_name}</p>
  </div>
  <div style="padding:14px 28px;background:#f8f9ff;color:#94a3b8;font-size:12px">
    This is an automated message from HireMatch on behalf of {company_name}.
  </div>
</div>"""
    return subject, text, html
