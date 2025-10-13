import re
import sys
from pathlib import Path

# --- handle command line arguments ---
if len(sys.argv) != 3:
    print("Usage: python sync_snippets.py <path/to/snippets.py> <path/to/file.qmd>")
    sys.exit(1)

py_file = Path(sys.argv[1])
qmd_file = Path(sys.argv[2])

if not py_file.exists():
    sys.exit(f"❌ Error: Python snippet file not found: {py_file}")
if not qmd_file.exists():
    sys.exit(f"❌ Error: QMD file not found: {qmd_file}")

# --- extract snippets from .py ---
snippet_pattern = re.compile(r"# --- snippet: (.*?)\n(.*?)# --- endsnippet", re.DOTALL)
snippets = {
    name.strip(): code.strip()
    for name, code in snippet_pattern.findall(py_file.read_text())
}

# --- read qmd file ---
qmd_text = qmd_file.read_text()

# --- find code fences with insert option ---
fence_pattern = re.compile(r"```{python\s+insert:([\w-]+)}\n(.*?)```", re.DOTALL)


def replace_code(match):
    name = match.group(1).strip()
    code = snippets.get(name, f"# [ERROR: snippet '{name}' not found]")
    return f"```{{python insert:{name}}}\n{code}\n```"


# --- replace and write out ---
new_qmd = fence_pattern.sub(replace_code, qmd_text)

# --- backup and write ---
backup_path = qmd_file.with_suffix(".bak.qmd")
backup_path.write_text(qmd_text)
qmd_file.write_text(new_qmd)

print(f"✅ Synced snippets from {py_file} → {qmd_file}")
print(f"💾 Backup created at {backup_path}")
