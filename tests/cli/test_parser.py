"""
Tests for CLI argument parser functionality.
"""

import argparse
from unittest.mock import patch
from io import StringIO
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
api_dir = project_root / "traverser_ai_api"
sys.path.insert(0, str(api_dir))

try:
    from cli.parser import (
        build_parser, 
        add_common_arguments, 
        add_force_argument, 
        add_target_arguments,
        validate_target_args
    )
except ImportError as e:
    pytest.skip(f"CLI parser module not available: {e}", allow_module_level=True)


@pytest.mark.cli
def test_build_parser_basic():
    """Test basic parser building."""
    parser = build_parser()
    
    assert isinstance(parser, argparse.ArgumentParser)
    assert parser.description == "Modular CLI for Appium Traverser"
    # prog can vary depending on how Python is invoked (pytest, __main__.py, etc.)
    assert parser.prog in ["pytest", "__main__.py", "run_cli.py"]


@pytest.mark.cli
def test_build_parser_verbose_argument():
    """Test verbose argument in parser."""
    parser = build_parser()
    
    # Test with verbose flag
    args = parser.parse_args(['--verbose'])
    assert args.verbose is True
    
    # Test with short verbose flag
    args = parser.parse_args(['-v'])
    assert args.verbose is True
    
    # Test without verbose flag
    args = parser.parse_args([])
    assert args.verbose is False


@pytest.mark.cli
def test_build_parser_version_argument():
    """Test version argument in parser."""
    parser = build_parser()
    
    # Test version argument
    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        with pytest.raises(SystemExit):
            parser.parse_args(['--version'])
    
    output = mock_stdout.getvalue()
    assert "1.0.0" in output


@pytest.mark.cli
def test_build_parser_help_output():
    """Test help output contains expected content."""
    parser = build_parser()
    
    with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        with pytest.raises(SystemExit):
            parser.parse_args(['--help'])
    
    help_output = mock_stdout.getvalue()
    
    # Check that help contains expected examples
    assert "traverser-cli device list" in help_output
    assert "traverser-cli apps scan-health" in help_output
    assert "traverser-cli crawler start" in help_output
    assert "python run_cli.py device list" in help_output


@pytest.mark.cli
def test_add_common_arguments():
    """Test adding common arguments to a parser."""
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    
    # Test verbose argument
    args = parser.parse_args(['--verbose'])
    assert args.verbose is True
    
    # Test short verbose argument
    args = parser.parse_args(['-v'])
    assert args.verbose is True


@pytest.mark.cli
def test_add_force_argument():
    """Test adding force argument to a parser."""
    parser = argparse.ArgumentParser()
    add_force_argument(parser)
    
    # Test force argument
    args = parser.parse_args(['--force'])
    assert args.force is True
    
    # Test without force argument
    args = parser.parse_args([])
    assert args.force is False


@pytest.mark.cli
def test_add_target_arguments():
    """Test adding target arguments to a parser."""
    parser = argparse.ArgumentParser()
    add_target_arguments(parser)
    
    # Test target index
    args = parser.parse_args(['--target-index', '5'])
    assert args.target_index == '5'
    assert not hasattr(args, 'target_app_package') or args.target_app_package is None
    
    # Test target app package
    args = parser.parse_args(['--target-app-package', 'com.example.app'])
    assert args.target_app_package == 'com.example.app'
    assert not hasattr(args, 'target_index') or args.target_index is None
    
    # Test without target arguments
    args = parser.parse_args([])
    assert not hasattr(args, 'target_index') or args.target_index is None
    assert not hasattr(args, 'target_app_package') or args.target_app_package is None


@pytest.mark.cli
def test_add_target_arguments_mutually_exclusive():
    """Test that target arguments are mutually exclusive."""
    parser = argparse.ArgumentParser()
    add_target_arguments(parser)
    
    # Should raise error when both target arguments are provided
    with pytest.raises(SystemExit):
        parser.parse_args(['--target-index', '5', '--target-app-package', 'com.example.app'])


@pytest.mark.cli
def test_validate_target_args_valid_cases():
    """Test validate_target_args with valid arguments."""
    # Test with no target arguments
    args = argparse.Namespace()
    assert validate_target_args(args) is True
    
    # Test with only target index
    args = argparse.Namespace(target_index='5', target_app_package=None)
    assert validate_target_args(args) is True
    
    # Test with only target package
    args = argparse.Namespace(target_index=None, target_app_package='com.example.app')
    assert validate_target_args(args) is True


@pytest.mark.cli
def test_validate_target_args_invalid_case():
    """Test validate_target_args with invalid arguments."""
    # Test with both target arguments (should be invalid)
    args = argparse.Namespace(target_index='5', target_app_package='com.example.app')
    assert validate_target_args(args) is False


@pytest.mark.cli
def test_validate_target_args_edge_cases():
    """Test validate_target_args with edge cases."""
    # Test with empty strings
    args = argparse.Namespace(target_index='', target_app_package='')
    assert validate_target_args(args) is True  # Empty strings are falsy
    
    # Test with missing attributes
    args = argparse.Namespace()
    # Don't set target_index and target_app_package at all
    assert validate_target_args(args) is True


@pytest.mark.cli
def test_parser_with_subcommands_integration():
    """Test parser integration with subcommands (simulated)."""
    parser = build_parser()
    
    # Create subparsers for testing
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add a test subcommand
    test_parser = subparsers.add_parser('test', help='Test command')
    add_common_arguments(test_parser)
    add_force_argument(test_parser)
    add_target_arguments(test_parser)
    
    # Test parsing subcommand with arguments
    args = parser.parse_args(['test', '--verbose', '--force', '--target-index', '3'])
    
    assert args.command == 'test'
    assert args.verbose is True
    assert args.force is True
    assert args.target_index == '3'


@pytest.mark.cli
def test_parser_error_handling():
    """Test parser error handling."""
    parser = build_parser()
    
    # Test with invalid argument
    with pytest.raises(SystemExit):
        parser.parse_args(['--invalid-argument'])


@pytest.mark.cli
def test_parser_description_formatting():
    """Test that parser description is properly formatted."""
    parser = build_parser()
    
    # Check that formatter_class is set correctly
    assert parser.formatter_class == argparse.RawDescriptionHelpFormatter
    
    # Check that epilog contains expected content
    assert "Examples (console script):" in parser.epilog
    assert "Examples (python entrypoint):" in parser.epilog


@pytest.mark.cli
def test_argument_types():
    """Test that arguments have correct types."""
    parser = argparse.ArgumentParser()
    add_target_arguments(parser)
    
    # Test that target_index is stored as string
    args = parser.parse_args(['--target-index', '123'])
    assert isinstance(args.target_index, str)
    assert args.target_index == '123'
    
    # Test that target_app_package is stored as string
    args = parser.parse_args(['--target-app-package', 'com.example.app'])
    assert isinstance(args.target_app_package, str)
    assert args.target_app_package == 'com.example.app'


@pytest.mark.cli
def test_argument_help_text():
    """Test that arguments have appropriate help text."""
    parser = build_parser()
    
    # Check verbose argument help
    actions = [action for action in parser._actions if '--verbose' in action.option_strings]
    assert len(actions) > 0
    assert "Enable verbose logging" in actions[0].help
    
    # Test help text in utility functions
    parser = argparse.ArgumentParser()
    add_force_argument(parser)
    
    actions = [action for action in parser._actions if '--force' in action.option_strings]
    assert len(actions) > 0
    assert "Force operation" in actions[0].help
