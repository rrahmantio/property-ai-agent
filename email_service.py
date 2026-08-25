"""
Phase 3: email approval workflow.

Sends one email per day: "HOZ Property | Today's Threads" with each candidate
chain shown in full, plus a [VIEW / POST THIS] link (per option) and one
[REGENERATE] link for the whole batch.

Links point at the approval webhook (approval_app.py), carrying a one-time
token from storage.create_token — never the raw content or any secret.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def _option_html(letter: str, content: dict, approve_url: str) -> str:
    thread_html = "".join(f"<p style='margin:4px 0'>{p}</p>" for p in content["thread_posts"])
    return f"""
    <div style="border:1px solid #ddd; border-radius:8px; padding:16px; margin-bottom:20px;">
      <h3 style="margin:0 0 8px 0;">OPTION {letter}</h3>
      <p><b>Title:</b> {content['title']}</p>
      <p><b>Audience:</b> {content['audience']}</p>
      <p><b>Angle / pillar:</b> {content['pillar']}</p>
      <p><b>Hook:</b> {content['hook']}</p>
      <p><b>Full Threads chain:</b></p>
      <div style="background:#fafafa; padding:12px; border-radius:6px;">{thread_html}</div>
      <p style="margin-top:12px;">
        <a href="{approve_url}"
           style="background:#000; color:#fff; padding:10px 16px; border-radius:6px;
                  text-decoration:none; display:inline-block;">
          VIEW / POST THIS
        </a>
      </p>
    </div>
    """


def build_email_html(batch_date: str, options: list, regenerate_url: str) -> str:
    letters = ["A", "B", "C", "D", "E", "F"]
    body = "".join(
        _option_html(letters[i], opt["content"], opt["approve_url"])
        for i, opt in enumerate(options)
    )
    return f"""
    <html><body style="font-family: -apple-system, Arial, sans-serif; max-width:640px;">
      <h2>HOZ Property | Today's Threads — {batch_date}</h2>
      <p>Review each option below. Click <b>VIEW / POST THIS</b> to publish that chain to
      Threads immediately. If none are good:</p>
      <p>
        <a href="{regenerate_url}"
           style="background:#eee; color:#000; padding:10px 16px; border-radius:6px;
                  text-decoration:none; display:inline-block;">
          REGENERATE
        </a>
      </p>
      <hr/>
      {body}
    </body></html>
    """


def send_approval_email(batch_date: str, options: list, regenerate_url: str):
    """
    options: list of {"content": <chain dict>, "approve_url": <str>}
    """
    html = build_email_html(batch_date, options, regenerate_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "HOZ Property | Today's Threads"
    msg["From"] = config.EMAIL_FROM
    msg["To"] = config.EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(config.EMAIL_SMTP_HOST, config.EMAIL_SMTP_PORT) as server:
        server.starttls()
        server.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_FROM, [config.EMAIL_TO], msg.as_string())
