"""
Phase 1-3 orchestration: the script GitHub Actions runs daily at 09:00 WIB.

Research -> read history -> generate concepts -> score -> select -> write
chains -> quality check -> save as 'proposed' -> create approval tokens ->
email the options. Publishing itself happens later, when Riyandi clicks
POST THIS (handled by approval_app.py, not here).
"""
import sys
from datetime import datetime

import config
import content_generation as cg
import email_service
import research
import storage


def run():
    storage.init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today}] Starting HOZ Property daily content job...")

    print("Researching current Jakarta/Jabodetabek topics...")
    notes = research.research_jakarta_topics()
    print(f"  -> {len(notes)} research notes")

    history = storage.recent_history(limit=30)

    print("Generating concepts...")
    concepts = cg.generate_concepts(notes, history)
    print(f"  -> {len(concepts)} concepts")

    print("Scoring concepts...")
    concepts = cg.score_concepts(concepts)

    selected = cg.select_top(concepts)
    print(f"  -> selected {len(selected)} concepts")

    print("Writing Threads chains...")
    chains = cg.write_threads_chains(selected)

    print("Running quality check...")
    chains = cg.quality_check(chains)
    print(f"  -> {len(chains)} chains passed quality check")

    if not chains:
        print("No chains passed quality check today. Nothing to send. Exiting.")
        sys.exit(0)

    print("Saving proposed content + creating approval links...")
    options = []
    for chain in chains:
        content_id = storage.save_proposed_content(
            date=today,
            title=chain["title"],
            audience=chain["audience"],
            pillar=chain["pillar"],
            hook=chain["hook"],
            thread_posts=chain["thread_posts"],
        )
        token = storage.create_token(batch_date=today, kind="approve", content_id=content_id)
        approve_url = f"{config.APPROVAL_BASE_URL}/approve/{token}"
        options.append({"content": chain, "approve_url": approve_url})

    regen_token = storage.create_token(batch_date=today, kind="regenerate")
    regenerate_url = f"{config.APPROVAL_BASE_URL}/regenerate/{regen_token}"

    print("Sending approval email...")
    email_service.send_approval_email(today, options, regenerate_url)

    print(f"Done. {len(options)} options sent to {config.EMAIL_TO}.")


if __name__ == "__main__":
    run()
