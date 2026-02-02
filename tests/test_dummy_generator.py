"""Test script for Dummy Generator module.

Tests the copy-based dummy executable generation system.

Usage:
    pytest tests/test_dummy_generator.py -v
    python tests/test_dummy_generator.py  # Run basic tests
"""

import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.dummy_generator import DummyGenerator, DummyGeneratorError  # noqa: E402


def test_generator_initialization():
    """Test dummy generator initialization."""
    print("Testing dummy generator initialization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"

        gen = DummyGenerator(output_dir)

        assert gen.output_dir == output_dir
        assert output_dir.exists(), "Output directory should be created"
        print(f"  Output directory: {output_dir}")
        print(f"  Template path: {gen.template_exe_path}")
        print("  Generator initialized successfully")

    print("  PASSED")


def test_generator_with_custom_template():
    """Test initialization with custom template path."""
    print("Testing generator with custom template path...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        template_path = Path(tmpdir) / "CustomDummy.exe"

        # Create a fake template
        template_path.write_bytes(b"FAKE_EXE")

        gen = DummyGenerator(output_dir, template_exe_path=template_path)

        assert gen.template_exe_path == template_path
        assert gen.is_template_available(), "Custom template should be available"
        print("  Custom template recognized")

    print("  PASSED")


def test_template_availability_check():
    """Test template availability checking."""
    print("Testing template availability check...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"

        # Create generator without a real template
        gen = DummyGenerator(output_dir)

        # Check if template is available (likely not in test environment)
        is_available = gen.is_template_available()
        print(f"  Template available: {is_available}")
        print(f"  Template path: {gen.get_template_path()}")

        # Should not crash regardless of availability

    print("  PASSED")


def test_process_name_normalization():
    """Test process name normalization."""
    print("Testing process name normalization...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        gen = DummyGenerator(output_dir)

        # Test basic name
        result = gen._normalize_process_name("game.exe")
        assert result == "game.exe", f"Expected 'game.exe', got '{result}'"
        print("  Basic name: OK")

        # Test backslash path
        result = gen._normalize_process_name("_retail_\\wow.exe")
        assert result == "_retail_/wow.exe", (
            f"Expected '_retail_/wow.exe', got '{result}'"
        )
        print("  Backslash path: OK")

        # Test forward slash path
        result = gen._normalize_process_name("bin/game.exe")
        assert result == "bin/game.exe", f"Expected 'bin/game.exe', got '{result}'"
        print("  Forward slash path: OK")

        # Test without .exe extension
        result = gen._normalize_process_name("game")
        assert result == "game.exe", f"Expected 'game.exe', got '{result}'"
        print("  Auto-add .exe: OK")

    print("  PASSED")


def test_dummy_path_methods():
    """Test path-related methods."""
    print("Testing dummy path methods...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        gen = DummyGenerator(output_dir)

        game_id = 12345
        process_name = "test.exe"

        # Test get_dummy_path
        path = gen.get_dummy_path(game_id, process_name)
        expected = output_dir / str(game_id) / process_name
        assert path == expected, f"Expected {expected}, got {path}"
        print(f"  Dummy path: {path}")

        # Test get_working_directory
        work_dir = gen.get_working_directory(game_id, process_name)
        assert work_dir == output_dir / str(game_id)
        print(f"  Working directory: {work_dir}")

        # Test dummy_exists (should be False initially)
        exists = gen.dummy_exists(game_id, process_name)
        assert not exists, "Dummy should not exist yet"
        print("  Correctly reported dummy does not exist")

    print("  PASSED")


def test_dummy_path_with_subdirectory():
    """Test path methods with process names containing subdirectories."""
    print("Testing dummy paths with subdirectories...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        gen = DummyGenerator(output_dir)

        game_id = 12345
        process_name = "_retail_/wow.exe"

        # Test get_dummy_path with subdirectory
        path = gen.get_dummy_path(game_id, process_name)
        expected = output_dir / str(game_id) / "_retail_" / "wow.exe"
        assert path == expected, f"Expected {expected}, got {path}"
        print(f"  Path with subdirectory: {path}")

        # Test working directory
        work_dir = gen.get_working_directory(game_id, process_name)
        assert work_dir == output_dir / str(game_id) / "_retail_"
        print(f"  Working directory: {work_dir}")

    print("  PASSED")


def test_ensure_dummy_with_template():
    """Test ensure_dummy_for_game with a mock template."""
    print("Testing ensure_dummy_for_game...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        template_path = Path(tmpdir) / "DummyGame.exe"

        # Create a fake template
        template_content = b"FAKE_EXE_CONTENT_FOR_TESTING"
        template_path.write_bytes(template_content)

        gen = DummyGenerator(output_dir, template_exe_path=template_path)

        game_id = 12345
        process_name = "test.exe"

        # Ensure dummy is created
        exe_path, actual_name = gen.ensure_dummy_for_game(game_id, process_name)

        assert exe_path.exists(), "Dummy executable should be created"
        assert actual_name == "test.exe"
        assert exe_path.read_bytes() == template_content, (
            "Content should match template"
        )
        print(f"  Created dummy: {exe_path}")

        # Ensure idempotent - calling again should not fail
        exe_path2, actual_name2 = gen.ensure_dummy_for_game(game_id, process_name)
        assert exe_path2 == exe_path
        assert actual_name2 == actual_name
        print("  Idempotent check: OK")

    print("  PASSED")


def test_ensure_dummy_with_subdirectory():
    """Test ensure_dummy_for_game with process name containing subdirectory."""
    print("Testing ensure_dummy with subdirectory...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        template_path = Path(tmpdir) / "DummyGame.exe"

        # Create a fake template
        template_path.write_bytes(b"FAKE_EXE")

        gen = DummyGenerator(output_dir, template_exe_path=template_path)

        game_id = 12345
        process_name = "_retail_/wow.exe"

        # Ensure dummy is created
        exe_path, actual_name = gen.ensure_dummy_for_game(game_id, process_name)

        assert exe_path.exists(), "Dummy executable should be created"
        assert actual_name == "_retail_/wow.exe"
        assert "_retail_" in str(exe_path.parent)
        print(f"  Created dummy: {exe_path}")

    print("  PASSED")


def test_ensure_dummy_without_template():
    """Test that ensure_dummy_for_game raises error without template."""
    print("Testing ensure_dummy without template...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"

        # Point to non-existent template
        fake_template = Path(tmpdir) / "NonExistent.exe"
        gen = DummyGenerator(output_dir, template_exe_path=fake_template)

        assert not gen.is_template_available()

        try:
            gen.ensure_dummy_for_game(12345, "test.exe")
            assert False, "Should have raised DummyGeneratorError"
        except DummyGeneratorError as e:
            assert "not found" in str(e).lower()
            print(f"  Correctly raised error: {e}")

    print("  PASSED")


def test_dummy_removal():
    """Test dummy removal."""
    print("Testing dummy removal...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        gen = DummyGenerator(output_dir)

        game_id = 12345
        process_name = "test.exe"

        # Create dummy directory and file
        game_dir = output_dir / str(game_id)
        game_dir.mkdir(parents=True)
        dummy_file = game_dir / process_name
        dummy_file.write_bytes(b"dummy")

        # Test removal
        result = gen.remove_dummy(game_id, process_name)
        assert result is True, "Should return True on successful removal"
        assert not dummy_file.exists(), "File should be deleted"
        assert not game_dir.exists(), "Game directory should be removed"
        print("  Dummy removed successfully")

        # Test removal of non-existent
        result = gen.remove_dummy(game_id, process_name)
        assert result is False, "Should return False when dummy doesn't exist"
        print("  Correctly handled non-existent dummy")

    print("  PASSED")


def test_dummy_exists():
    """Test dummy_exists method."""
    print("Testing dummy_exists...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        gen = DummyGenerator(output_dir)

        game_id = 12345
        process_name = "test.exe"

        # Should not exist initially
        assert not gen.dummy_exists(game_id, process_name)
        print("  Non-existent: OK")

        # Create the file
        game_dir = output_dir / str(game_id)
        game_dir.mkdir(parents=True)
        exe_file = game_dir / process_name
        exe_file.write_bytes(b"test")

        # Should exist now
        assert gen.dummy_exists(game_id, process_name)
        print("  Exists: OK")

    print("  PASSED")


def run_all_tests():
    """Run all dummy generator tests."""
    print("\n" + "=" * 50)
    print("DUMMY GENERATOR MODULE TESTS")
    print("=" * 50 + "\n")

    tests = [
        test_generator_initialization,
        test_generator_with_custom_template,
        test_template_availability_check,
        test_process_name_normalization,
        test_dummy_path_methods,
        test_dummy_path_with_subdirectory,
        test_ensure_dummy_with_template,
        test_ensure_dummy_with_subdirectory,
        test_ensure_dummy_without_template,
        test_dummy_removal,
        test_dummy_exists,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback

            traceback.print_exc()
            failed.append((test.__name__, e))
        print()

    print("=" * 50)
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} tests")
        for name, error in failed:
            print(f"  - {name}: {error}")
    else:
        print(f"ALL TESTS PASSED: {len(tests)}/{len(tests)}")
    print("=" * 50 + "\n")

    return len(failed) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
