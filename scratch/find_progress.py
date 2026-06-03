with open("app/static/app.js", "r", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        if "progressBarFill" in line or "progress-bar-fill" in line:
            print(f"{idx}: {line.strip()}")
