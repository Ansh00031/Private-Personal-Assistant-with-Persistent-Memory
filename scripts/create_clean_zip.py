import os
import sys
import zipfile
from pathlib import Path

def create_clean_zip():
    project_root = Path(r"c:\Users\ansh6\Downloads\Personal Ai\project")
    output_zip = Path(r"c:\Users\ansh6\Downloads\Personal_AI_Submission.zip")

    # Excluded directories and file patterns
    exclude_dirs = {"venv", ".git", "__pycache__", ".pytest_cache", ".idea", ".vscode"}
    exclude_files = {
        ".env",  # Secrets must never be included
        "memory.db.unencrypted.bak",
        "test_seed.db",
    }

    if output_zip.exists():
        output_zip.unlink()

    total_files = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(project_root):
            # Modify dirs in-place to avoid walking into excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files or file.endswith(".pyc") or file.endswith(".pyo"):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(project_root)
                zipf.write(file_path, arcname)
                total_files += 1

    size_bytes = output_zip.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"Created: {output_zip}")
    print(f"Total files packaged: {total_files}")
    print(f"Compressed file size: {size_mb:.2f} MB ({size_bytes:,} bytes)")

if __name__ == "__main__":
    create_clean_zip()
