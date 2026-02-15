import os
import sys
from pathlib import Path

def generate_tree(startpath, output_file, prefix=''):
    items = list(os.scandir(startpath))
    dirs = [item for item in items if item.is_dir()]
    files = [item for item in items if item.is_file()]
    
    # Skip common noise directories and files
    dirs = [d for d in dirs if d.name not in ('__pycache__', '.git', 'venv', 'node_modules')]
    files = [f for f in files if f.name not in ('generate_tree.py', '.gitignore', 'tree_output.txt')]
    
    entries = dirs + files
    for i, entry in enumerate(entries):
        is_last = (i == len(entries) - 1)
        connector = '└── ' if is_last else '├── '
        output_file.write(f"{prefix}{connector}{entry.name}\n")
        
        if entry.is_dir():
            extension = '    ' if is_last else '│   '
            generate_tree(entry.path, output_file, prefix + extension)

if __name__ == '__main__':
    with open('docs/DIRECTORY_STRUCTURE.md', 'w', encoding='utf-8') as f:
        f.write("# Project Directory Structure\n\n")
        generate_tree('.', f)
    print("Directory tree saved to docs/DIRECTORY_STRUCTURE.md")