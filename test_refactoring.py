#!/usr/bin/env python3
"""
Simple test script to verify the refactoring is working correctly.
"""

import sys
import os

# Change to traverser_ai_api directory and add it to path
api_dir = os.path.join(os.path.dirname(__file__), 'traverser_ai_api')
sys.path.insert(0, api_dir)
os.chdir(api_dir)

def test_imports():
    """Test that all modules can be imported successfully."""
    try:
        print("Testing imports...")
        
        # Test core modules
        from core.controller import CrawlerOrchestrator, CrawlerLaunchPlan
        print("✓ Core controller modules imported successfully")
        
        from core.validation import ValidationConstraints, validate_launch_plan
        print("✓ Core validation modules imported successfully")
        
        from core.adapters import SubprocessAdapter, QProcessAdapter
        print("✓ Core adapter modules imported successfully")
        
        # Test CLI service
        from cli.services.crawler_service import CrawlerService
        print("✓ CLI CrawlerService imported successfully")
        
        # Test UI manager
        from ui.crawler_manager import CrawlerManager
        print("✓ UI CrawlerManager imported successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orchestrator_creation():
    """Test that the orchestrator can be created."""
    try:
        print("\nTesting orchestrator creation...")
        
        from core.controller import CrawlerOrchestrator
        
        # Test creating orchestrator
        orchestrator = CrawlerOrchestrator()
        print("✓ CrawlerOrchestrator created successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Orchestrator creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_constraints():
    """Test validation constraints."""
    try:
        print("\nTesting validation constraints...")
        
        from core.validation import ValidationConstraints
        
        # Test creating constraints
        constraints = ValidationConstraints()
        print("✓ ValidationConstraints created successfully")
        
        # Test default values
        assert constraints.max_crawl_steps > 0
        assert constraints.max_crawl_duration_seconds > 0
        print("✓ Validation constraints have correct default values")
        
        return True
        
    except Exception as e:
        print(f"✗ Constraints test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=== Testing Refactored Code ===\n")
    
    tests = [
        test_imports,
        test_orchestrator_creation,
        test_constraints,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        else:
            print("Test failed, stopping execution")
            break
    
    print(f"\n=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests passed! Refactoring appears to be working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())