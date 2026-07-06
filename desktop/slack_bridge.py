"""Optional Slack bridge for Jarvis.

A dedicated Slack app - separate from any other bot (e.g. a Hermes agent
running elsewhere) - that lets you DM or @mention Jarvis and get the exact
same brain (tools, memory, personality) that answers your voice. Runs over
Socket Mode, so no public server or webhook URL is needed.

Only starts if slack_bot_token and slack_app_token are set in config.json.
"""
import threading


def start(cfg, think_fn, speak_fn, state):
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=cfg["slack_bot_token"])
    bot_user_id = app.client.auth_test()["user_id"]

    def handle(event, say):
        text = (event.get("text") or "").replace(f"<@{bot_user_id}>", "").strip()
        if not text or event.get("bot_id"):
            return
        try:
            answer = think_fn(text)
        except Exception as e:  # noqa: BLE001
            answer = f"Brain hiccup: {e}"
        say(answer)
        if state["mode"] == "idle":  # don't talk over an active voice turn
            threading.Thread(target=speak_fn, args=(answer,), daemon=True).start()

    @app.event("message")
    def on_dm(event, say):
        if event.get("channel_type") == "im":
            handle(event, say)

    @app.event("app_mention")
    def on_mention(event, say):
        handle(event, say)

    handler = SocketModeHandler(app, cfg["slack_app_token"])
    print("(slack bridge connected - DM or @mention the Jarvis bot)")
    handler.start()  # blocks; run this in its own thread
