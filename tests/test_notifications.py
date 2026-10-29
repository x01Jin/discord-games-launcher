
import base64

from launcher.notifications import APP_ID, Notifier, build_command, build_payload


def test_payload_escapes_both_lines():
    payload = build_payload("Quest & <Friends>", "Name <b> & Co")

    assert "Quest &amp; &lt;Friends&gt;" in payload
    assert "Name &lt;b&gt; &amp; Co" in payload
    assert "<Friends>" not in payload


def test_command_decodes_to_a_toast_script():
    encoded = build_command("Quest finished", "Test Quest · 700 Orbs")
    script = base64.b64decode(encoded).decode("utf-16-le")

    assert "ToastNotificationManager" in script
    assert APP_ID in script
    assert "Quest finished" in script
    assert "Test Quest · 700 Orbs" in script


def test_notifier_reports_a_finished_quest_through_the_runner():
    sent = []
    notifier = Notifier(runner=sent.append)

    notifier.quest_finished("Test Quest", "700 Orbs")

    assert len(sent) == 1
    script = base64.b64decode(sent[0]).decode("utf-16-le")
    assert "Quest finished" in script
    assert "Test Quest · 700 Orbs" in script


def test_a_quest_without_a_reward_still_gets_a_title():
    sent = []
    notifier = Notifier(runner=sent.append)

    notifier.quest_finished("Test Quest", None)

    assert base64.b64decode(sent[0]).decode("utf-16-le").count("Test Quest") == 1


def test_a_refused_claim_is_announced_with_its_reason():
    sent = []
    notifier = Notifier(runner=sent.append)

    notifier.claim_needs_action(
        "Discord would not claim it here (Unknown Message). Claim it from Discord's own Quests page."
    )

    script = base64.b64decode(sent[0]).decode("utf-16-le")
    assert "Reward not claimed" in script
    assert "Unknown Message" in script


def test_a_failing_runner_is_logged_not_raised():
    class Logger:
        def __init__(self):
            self.messages = []

        def warning(self, message):
            self.messages.append(message)

    logger = Logger()

    def broken(_script):
        raise OSError("powershell.exe is missing")

    Notifier(logger=logger, runner=broken).quest_finished("Test Quest")

    assert logger.messages and "powershell.exe is missing" in logger.messages[0]
