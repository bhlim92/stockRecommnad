import os

artifact_dir = r"C:\Users\samsung\.gemini\antigravity\brain\ec205238-3056-44ac-a8bf-ba319f497385"
workspace_dir = r"c:\Users\samsung\proj\stockRecommnad"

test_paths = [
    "/stock_screener_mockup_1780444926617.png",
    "stock_screener_mockup_1780444926617.png",
    "/C:/Users/samsung/.gemini/antigravity/brain/ec205238-3056-44ac-a8bf-ba319f497385/stock_screener_mockup_1780444926617.png",
    "/Users/samsung/.gemini/antigravity/brain/ec205238-3056-44ac-a8bf-ba319f497385/stock_screener_mockup_1780444926617.png",
    "//C:/Users/samsung/.gemini/antigravity/brain/ec205238-3056-44ac-a8bf-ba319f497385/stock_screener_mockup_1780444926617.png",
    "/C:Users/samsung/.gemini/antigravity/brain/ec205238-3056-44ac-a8bf-ba319f497385/stock_screener_mockup_1780444926617.png",
    "/..\\..\\.gemini\\antigravity\\brain\\ec205238-3056-44ac-a8bf-ba319f497385\\stock_screener_mockup_1780444926617.png",
    "/..\\..\\.gemini/antigravity/brain/ec205238-3056-44ac-a8bf-ba319f497385/stock_screener_mockup_1780444926617.png"
]

print("Artifact dir:", artifact_dir)
for p in test_paths:
    # Let's see how they resolve
    abs_p = os.path.abspath(p)
    abs_joined_workspace = os.path.abspath(os.path.join(workspace_dir, p.lstrip("/")))
    abs_joined_artifact = os.path.abspath(os.path.join(artifact_dir, p.lstrip("/")))
    
    print(f"Path: {p}")
    print(f"  abspath: {abs_p} (Inside? {abs_p.startswith(artifact_dir)})")
    print(f"  joined workspace: {abs_joined_workspace} (Inside? {abs_joined_workspace.startswith(artifact_dir)})")
    print(f"  joined artifact: {abs_joined_artifact} (Inside? {abs_joined_artifact.startswith(artifact_dir)})")
