import os, re, json

ROOT = "."  # ако проекта ти е в друга папка смени
OUT = "translations/keys_found.json"

# хваща _("text") и _('text')
PATTERN = re.compile(r"""_\(\s*(['"])(.*?)\1\s*\)""", re.DOTALL)

def iter_files(root):
    for dirpath, _, filenames in os.walk(root):
        # пропускаме venv, migrations, static uploads и тн
        if any(x in dirpath for x in [".venv", "venv", "__pycache__", ".git", "static/uploads"]):
            continue
        for fn in filenames:
            if fn.endswith((".py", ".html", ".jinja", ".j2")):
                yield os.path.join(dirpath, fn)

keys = set()

for path in iter_files(ROOT):
    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read()
        for _, k in PATTERN.findall(txt):
            k = " ".join(k.split())  # маха странни whitespace
            if k:
                keys.add(k)
    except Exception:
        pass

keys_sorted = sorted(keys)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(keys_sorted, f, ensure_ascii=False, indent=2)

print(f"Found {len(keys_sorted)} keys -> {OUT}")
