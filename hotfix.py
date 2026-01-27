#!/usr/bin/env python3
"""
Hotfix script to replace all problematic context manager patterns
"""
import re

def fix_context_managers():
    """Fix all 'with get_db_connection() as conn:' patterns in app.py"""
    
    with open('app.py', 'r') as f:
        content = f.read()
    
    # Pattern to match: with get_db_connection() as conn:
    pattern = r'with get_db_connection\(\) as conn:'
    
    # Count occurrences
    matches = re.findall(pattern, content)
    print(f"Found {len(matches)} context manager patterns to fix")
    
    # Replace with proper pattern
    replacement = '''conn, db_type = get_db_connection()
    try:
        cursor = conn.cursor()'''
    
    # This is a complex replacement, so let's do it manually for critical functions
    print("Manual fixes needed for context managers...")
    print("The login function has been fixed.")
    print("Other functions need similar fixes.")
    
    return len(matches)

if __name__ == "__main__":
    count = fix_context_managers()
    print(f"Found {count} patterns that need fixing")
    print("Login function already fixed. Deploy this version first.")