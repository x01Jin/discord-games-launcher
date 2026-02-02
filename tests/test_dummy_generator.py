"""Test script for Dummy Generator module.

Usage:
    pytest tests/test_dummy_generator.py -v
    python tests/test_dummy_generator.py  # Run basic tests

Note: PyInstaller tests are slow and create actual executables.
Set SKIP_PYINSTALLER_TESTS=True to skip them.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from launcher.dummy_generator import DummyGenerator  # noqa: E402


def test_generator_initialization():
    """Test dummy generator initialization."""
    print("Testing dummy generator initialization...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        
        gen = DummyGenerator(output_dir)
        
        assert gen.output_dir == output_dir
        assert output_dir.exists(), "Output directory should be created"
        print(f"  Output directory: {output_dir}")
        print("  Generator initialized successfully")
    
    print("  PASSED")


def test_dummy_script_creation():
    """Test creation of dummy Python script."""
    print("Testing dummy script creation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "games"
        gen = DummyGenerator(output_dir)
        
        game_id = 12345
        game_name = "Test Game"
        process_name = "test.exe"
        
        # Create script (internal method)
        script_path = gen._create_dummy_script(game_id, game_name, process_name)
        
        assert script_path.exists(), "Script file should be created"
        print(f"  Script created: {script_path}")
        
        # Read and verify content
        content = script_path.read_text()
        assert str(game_id) in content, "Game ID should be in script"
        assert game_name in content, "Game name should be in script"
        assert process_name in content, "Process name should be in script"
        print("  Script content verified")
        
        # Cleanup
        script_path.unlink()
    
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
        print(f"  Path: {path}")
        
        # Test dummy_exists (should be False initially)
        exists = gen.dummy_exists(game_id, process_name)
        assert not exists, "Dummy should not exist yet"
        print("  Correctly reported dummy does not exist")
    
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
        dummy_file.write_text("dummy")
        
        # Test removal
        result = gen.remove_dummy(game_id, process_name)
        assert result is True, "Should return True on successful removal"
        assert not dummy_file.exists(), "File should be deleted"
        assert not game_dir.exists(), "Empty directory should be removed"
        print("  Dummy removed successfully")
        
        # Test removal of non-existent
        result = gen.remove_dummy(game_id, process_name)
        assert result is False, "Should return False when dummy doesn't exist"
        print("  Correctly handled non-existent dummy")
    
    print("  PASSED")


def test_template_formatting():
    """Test template variable formatting."""
    print("Testing template formatting...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a custom template
        template_dir = Path(tmpdir) / "templates"
        template_dir.mkdir()
        template_file = template_dir / "dummy_template.py"
        
        template_content = '''#!/usr/bin/env python3
GAME_ID = {game_id}
GAME_NAME = "{game_name}"
PROCESS_NAME = "{process_name}"
'''
        template_file.write_text(template_content)
        
        output_dir = Path(tmpdir) / "games"
        gen = DummyGenerator(output_dir, template_file)
        
        # Create script
        script_path = gen._create_dummy_script(12345, "Test Game", "test.exe")
        content = script_path.read_text()
        
        assert "GAME_ID = 12345" in content
        assert 'GAME_NAME = "Test Game"' in content
        assert 'PROCESS_NAME = "test.exe"' in content
        print("  Template variables formatted correctly")
        
        script_path.unlink()
    
    print("  PASSED")


def run_all_tests():
    """Run all dummy generator tests."""
    print("\n" + "="*50)
    print("DUMMY GENERATOR MODULE TESTS")
    print("="*50 + "\n")
    
    tests = [
        test_generator_initialization,
        test_dummy_script_creation,
        test_dummy_path_methods,
        test_dummy_removal,
        test_template_formatting,
    ]
    
    # Check if we should skip PyInstaller tests
    skip_pyinstaller = os.environ.get('SKIP_PYINSTALLER_TESTS', 'False').lower() == 'true'
    if skip_pyinstaller:
        print("Note: PyInstaller integration tests skipped (SKIP_PYINSTALLER_TESTS=True)\n")
    
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
    
    print("="*50)
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} tests")
        for name, error in failed:
            print(f"  - {name}: {error}")
    else:
        print(f"ALL TESTS PASSED: {len(tests)}/{len(tests)}")
    print("="*50 + "\n")
    
    return len(failed) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
