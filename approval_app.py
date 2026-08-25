"""
Phase 3/4: the approval webhook.

This is the ONE part of the system that needs to run continuously (GitHub
Actions only runs on a schedule, it can't sit there waiting for an email
click). Deploy this small Flask app anywhere that stays up — Render, Fly.io,
a small VPS, etc. — and point APPROVAL_BASE_URL at it.

Routes:
  GET /approve/<token>    -> publish that content's chain to Threads
  GET /regenerate/<token> -> mark the batch for regeneration (no auto re-run
                              here; it just flags status so the next manual
                              or scheduled run knows today's batch was rejected)
  GET /health              -> liveness check
"""
from flask import Flask, render_template_string

import storage
import threads_client

app = Flask(__name__)

RESULT_PAGE = """
<html><body style="font-family: -apple-system, Arial, sans-serif; max-width:520px; margin:60px auto; text-align:center;">
  <h2>{{ heading }}</h2>
  <p>{{ message }}</p>
</body></html>
"""


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/approve/<token>")
def approve(token):
    row = storage.consume_token(token)
    if not row or row["kind"] != "approve" or row["content_id"] is None:
        return render_template_string(
            RESULT_PAGE, heading="Link expired or already used",
            message="This approval link is no longer valid.",
        ), 410

    content = storage.get_content(row["content_id"])
    if not content:
        return render_template_string(
            RESULT_PAGE, heading="Not found", message="Could not find this content.",
        ), 404

    if content["status"] == "published":
        return render_template_string(
            RESULT_PAGE, heading="Already published",
            message=f"\"{content['title']}\" was already posted to Threads.",
        )

    import json
    thread_posts = json.loads(content["full_thread_json"])

    try:
        first_post_id = threads_client.publish_chain(thread_posts)
    except threads_client.ThreadsPublishError as e:
        storage.update_status(content["id"], "approved")  # approved but publish failed
        return render_template_string(
            RESULT_PAGE, heading="Approved, but publishing failed",
            message=f"\"{content['title']}\" is marked approved. Publishing error: {e}",
        ), 502

    storage.update_status(content["id"], "published", threads_post_id=first_post_id)
    return render_template_string(
        RESULT_PAGE, heading="Posted to Threads ✅",
        message=f"\"{content['title']}\" is now live.",
    )


@app.route("/regenerate/<token>")
def regenerate(token):
    row = storage.consume_token(token)
    if not row or row["kind"] != "regenerate":
        return render_template_string(
            RESULT_PAGE, heading="Link expired or already used",
            message="This link is no longer valid.",
        ), 410

    for item in storage.batch_for_date(row["batch_date"]):
        if item["status"] == "proposed":
            storage.update_status(item["id"], "rejected")

    return render_template_string(
        RESULT_PAGE, heading="Noted",
        message="Today's options were marked as rejected. Re-run daily_job.py "
                "(or trigger the GitHub Action manually) to generate a fresh batch.",
    )


if __name__ == "__main__":
    storage.init_db()
    app.run(host="0.0.0.0", port=8080)
