"""build_dist.py — Automated Cloudflare dist & geplex-cloudflare-upload.zip builder.

Ensures that whenever start bot runs, any changes in source code immediately update
dist/ and generate a fresh geplex-cloudflare-upload.zip (deleting old ones).
"""

import os
import shutil
import zipfile
from pathlib import Path

def build_cloudflare_dist():
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    parent_dir = repo_root.parent

    dist_dir = repo_root / "dist"
    upload_zip_repo = repo_root / "geplex-cloudflare-upload.zip"
    upload_zip_parent = parent_dir / "geplex-cloudflare-upload.zip"

    print("\n[+] Updating Cloudflare dist & geplex-cloudflare-upload.zip...")

    # 1. Clean old dist and old zip files
    if dist_dir.exists():
        try:
            shutil.rmtree(dist_dir)
        except Exception:
            pass

    for old_zip in [upload_zip_repo, upload_zip_parent]:
        if old_zip.exists():
            try:
                old_zip.unlink()
                print(f"  -> Old zip removed: {old_zip.name}")
            except Exception:
                pass

    dist_dir.mkdir(parents=True, exist_ok=True)

    # 2. Copy static and assets directories
    static_src = repo_root / "static"
    assets_src = repo_root / "assets"

    if static_src.exists():
        shutil.copytree(static_src, dist_dir / "static", dirs_exist_ok=True)
    if assets_src.exists():
        shutil.copytree(assets_src, dist_dir / "assets", dirs_exist_ok=True)

    # 3. Copy index.html and login.html to root of dist
    index_html = static_src / "index.html"
    login_html = static_src / "login.html"

    if index_html.exists():
        content = index_html.read_text(encoding="utf-8")
        clean_content = content.replace(' nonce="{{CSP_NONCE}}"', '').replace('{{CSP_NONCE}}', '')
        (dist_dir / "index.html").write_text(clean_content, encoding="utf-8")
        (dist_dir / "404.html").write_text(clean_content, encoding="utf-8")

    if login_html.exists():
        content = login_html.read_text(encoding="utf-8")
        clean_content = content.replace(' nonce="{{CSP_NONCE}}"', '').replace('{{CSP_NONCE}}', '')
        (dist_dir / "login.html").write_text(clean_content, encoding="utf-8")

    # Remove duplicates under dist/static/
    for dup in ["index.html", "login.html"]:
        dup_path = dist_dir / "static" / dup
        if dup_path.exists():
            try:
                dup_path.unlink()
            except Exception:
                pass

    # 4. Write deployment-config.js
    api_base = os.getenv("GEPLEX_API_URL", "").rstrip("/")
    default_firebase = '{"apiKey":"AIzaSyCvefrQ-bJZ_mr97j_aLiYptlfKYb3blAs","authDomain":"geplex-ai.firebaseapp.com","databaseURL":"https://geplex-ai-default-rtdb.firebaseio.com","projectId":"geplex-ai","storageBucket":"geplex-ai.firebasestorage.app","messagingSenderId":"587292925892","appId":"1:587292925892:web:1450a207788d49a379ce91","measurementId":"G-R0EX7E2VYG"}'
    firebase_config = os.getenv("GEPLEX_FIREBASE_CONFIG_JSON", default_firebase)

    dep_config_content = f"""window.GEPLEX_DEPLOYMENT = {{
  apiBase: "{api_base}",
  firebaseConfig: {firebase_config}
}};
"""
    (dist_dir / "static" / "deployment-config.js").write_text(dep_config_content, encoding="utf-8")

    # Copy deployment.js
    dep_js = static_src / "deployment.js"
    if dep_js.exists():
        shutil.copy2(dep_js, dist_dir / "static" / "deployment.js")

    # 5. Write _headers
    headers_content = """# GepLex Cloudflare Pages bundle
/*
  Referrer-Policy: strict-origin-when-cross-origin

/static/*
  Cache-Control: no-cache, no-store, must-revalidate

/assets/*
  Cache-Control: public, max-age=86400
  Access-Control-Allow-Origin: *
"""
    (dist_dir / "_headers").write_text(headers_content, encoding="utf-8")

    # Ensure no conflicting _redirects exists
    redirects_file = dist_dir / "_redirects"
    if redirects_file.exists():
        try:
            redirects_file.unlink()
        except Exception:
            pass

    # 6. Create fresh geplex-cloudflare-upload.zip
    with zipfile.ZipFile(upload_zip_repo, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dist_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(dist_dir)
                zf.write(file_path, arcname)

    # Copy to parent folder as well
    try:
        shutil.copy2(upload_zip_repo, upload_zip_parent)
    except Exception:
        pass

    print(f"  -> dist/ updated: {dist_dir}")
    print(f"  -> Fresh zip generated: {upload_zip_repo}")
    if upload_zip_parent.exists():
        print(f"  -> Fresh zip copied to: {upload_zip_parent}")
    print("[+] Cloudflare dist & zip sync complete!\n")

if __name__ == "__main__":
    build_cloudflare_dist()
