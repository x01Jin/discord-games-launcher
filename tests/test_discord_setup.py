
import os

from launcher import discord_setup
from launcher.discord_setup import (
    SWITCH,
    Launcher,
    _port_of,
    _shortcut_paths,
    _strip_switch,
    with_switch,
    without_switch,
)

RUN_KEY_TARGET = r"C:\Users\Jin\AppData\Local\Discord\Update.exe"
RUN_KEY_ARGS = "--processStart Discord.exe --process-start-args --start-minimized"
SHORTCUT_TARGET = r"C:\Users\Jin\AppData\Local\Discord\Discord.exe"




def test_port_of_reads_the_switch():
    assert _port_of("--processStart Discord.exe --remote-debugging-port=9223") == 9223
    assert _port_of("--remote-debugging-port=9223") == 9223
    assert _port_of("") is None
    assert _port_of("--start-minimized") is None
    assert _port_of("--remote-debugging-port=notanumber") is None


def test_strip_switch_removes_only_the_switch():
    assert _strip_switch("--start-minimized --remote-debugging-port=9223") == "--start-minimized"
    assert _strip_switch("--remote-debugging-port=9223") == ""
    assert _strip_switch("") == ""




def test_run_key_switch_goes_into_the_process_start_args_group():
    patched = with_switch(RUN_KEY_ARGS, RUN_KEY_TARGET)
    assert _port_of(patched) == discord_setup.SILENT_PORT
    assert "--start-minimized" in patched
    assert patched.endswith(
        f'--process-start-args "--start-minimized {SWITCH}{discord_setup.SILENT_PORT}"'
    )


def test_shortcut_without_arguments_gets_a_launcher_group():
    patched = with_switch("", SHORTCUT_TARGET)
    assert patched == f'--processStart Discord.exe --process-start-args "{SWITCH}9223"'


def test_shortcut_with_process_start_only_keeps_it():
    patched = with_switch("--processStart Discord.exe", SHORTCUT_TARGET)
    assert patched == f'--processStart Discord.exe --process-start-args "{SWITCH}9223"'


def test_plain_executable_gets_the_flag_directly():
    patched = with_switch("", r"C:\Tools\thing.exe")
    assert patched == f"{SWITCH}9223"


def test_patching_is_idempotent():
    once = with_switch(RUN_KEY_ARGS, RUN_KEY_TARGET)
    assert with_switch(once, RUN_KEY_TARGET) == once


def test_an_existing_port_is_replaced():
    original = '--processStart Discord.exe --process-start-args "--remote-debugging-port=9222"'
    patched = with_switch(original, SHORTCUT_TARGET, port=9333)
    assert _port_of(patched) == 9333
    assert "9222" not in patched




def test_disable_keeps_the_original_arguments():
    patched = with_switch(RUN_KEY_ARGS, RUN_KEY_TARGET)
    restored = without_switch(patched)
    assert _port_of(restored) is None
    assert "--start-minimized" in restored
    assert "--processStart Discord.exe" in restored


def test_disable_drops_the_group_it_added():
    patched = with_switch("", SHORTCUT_TARGET)
    assert without_switch(patched) == "--processStart Discord.exe"


def test_disable_on_an_untouched_line_changes_nothing():
    assert without_switch(RUN_KEY_ARGS) == RUN_KEY_ARGS
    assert without_switch("--processStart Discord.exe") == "--processStart Discord.exe"




def test_shortcuts_found_once_each(tmp_path, monkeypatch):
    appdata = tmp_path / "Roaming"
    programs = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    paths = {
        "Start menu": programs / "Discord Inc" / "Discord.lnk",
        "Taskbar": appdata
        / "Microsoft"
        / "Internet Explorer"
        / "Quick Launch"
        / "User Pinned"
        / "TaskBar"
        / "Discord.lnk",
        "Desktop": tmp_path / "user" / "Desktop" / "Discord.lnk",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    monkeypatch.setenv("PUBLIC", str(tmp_path / "public"))

    found = _shortcut_paths()
    assert sorted(kind for kind, _path in found) == ["Desktop", "Start menu", "Taskbar"]
    assert len({os.path.normcase(str(path)) for _kind, path in found}) == 3


def test_launcher_patched_flag_matches_the_command_line():
    patched = Launcher("Start menu", "x", SHORTCUT_TARGET, with_switch("", SHORTCUT_TARGET))
    plain = Launcher("Start menu", "x", SHORTCUT_TARGET, "--processStart Discord.exe")
    assert patched.patched is True
    assert plain.patched is False


def test_summary_reports_the_port_already_on_the_entries(monkeypatch):
    launcher = Launcher(
        "Start menu",
        "x",
        SHORTCUT_TARGET,
        with_switch("", SHORTCUT_TARGET, port=9222),
    )
    monkeypatch.setattr(discord_setup, "discover", lambda: [launcher])
    assert discord_setup.summary()["port"] == 9222


def test_summary_shape_without_touching_the_machine(monkeypatch):
    monkeypatch.setattr(discord_setup, "discover", list)
    state = discord_setup.summary()
    assert state["enabled"] is False
    assert state["launchers"] == []
    assert state["port"] == discord_setup.SILENT_PORT
