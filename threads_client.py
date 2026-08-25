"""
Phase 4: publish an approved Threads text chain via the Threads Graph API.

Flow per the Threads API:
  1. POST /{THREADS_USER_ID}/threads with media_type=TEXT&text=... (and
     reply_to_id=<previous post id> for posts after the first) -> returns a
     creation_id (container id).
  2. POST /{THREADS_USER_ID}/threads_publish with creation_id=<that id> ->
     returns the published post id.
  3. Use that published id as reply_to_id for the next post in the chain.

The access token is only ever read from the environment (config.py) — never
logged, printed, or written to storage.
"""
import time

import requests

import config


class ThreadsPublishError(RuntimeError):
    pass


def _post(path: str, params: dict) -> dict:
    url = f"{config.THREADS_API_BASE}/{path}"
    params = {**params, "access_token": config.THREADS_ACCESS_TOKEN}
    resp = requests.post(url, params=params, timeout=30)
    if resp.status_code >= 400:
        # Strip the access_token before raising so it never ends up in logs.
        safe_params = {k: v for k, v in params.items() if k != "access_token"}
        raise ThreadsPublishError(f"Threads API error {resp.status_code} for {path} "
                                   f"(params={safe_params}): {resp.text}")
    return resp.json()


def _create_container(text: str, reply_to_id: str = None) -> str:
    params = {"media_type": "TEXT", "text": text}
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    data = _post(f"{config.THREADS_USER_ID}/threads", params)
    return data["id"]


def _publish_container(creation_id: str) -> str:
    data = _post(f"{config.THREADS_USER_ID}/threads_publish", {"creation_id": creation_id})
    return data["id"]


def publish_chain(thread_posts: list, delay_seconds: float = 3.0) -> str:
    """
    Publishes each post in order, each as a reply to the previous one, so the
    chain reads as one connected thread. Returns the id of the FIRST post
    (stored as threads_post_id in content_history).

    delay_seconds: small pause between posts — Threads containers need a
    moment to process before they can be replied to / before rate limits.
    """
    if not thread_posts:
        raise ThreadsPublishError("Cannot publish an empty thread.")

    first_post_id = None
    previous_id = None

    for i, text in enumerate(thread_posts):
        creation_id = _create_container(text, reply_to_id=previous_id)
        # Threads recommends a short wait before publishing a just-created container.
        time.sleep(delay_seconds)
        published_id = _publish_container(creation_id)

        if i == 0:
            first_post_id = published_id
        previous_id = published_id

        if i < len(thread_posts) - 1:
            time.sleep(delay_seconds)

    return first_post_id
