"""Template for r2_credentials.py — the real, gitignored module that holds
UkoreHub's shared Cloudflare R2 key, baked into UkoreHubLauncher.exe at
build time.

To build a real exe:
1. Copy this file to r2_credentials.py (same directory, gitignored — see
   the repo-root .gitignore).
2. Fill in the four values below with the studio's real R2 credentials
   (rotate them first if they were ever pasted anywhere insecure — a
   chat log, a ticket, plaintext Slack — before using them here).
3. Run build_exe.py (or `git release-launcher`), which bundles
   r2_credentials.py's compiled bytecode into the exe the same way it
   already bundles updater.py and the vendored core/ package — no
   --add-data/hidden-imports change needed, this is a plain sibling
   import.

Never commit r2_credentials.py itself. See the ukorehub-cloud-sync skill
for how these reach app/launcher.py (via UKOREHUB_R2_* env vars set in
updater.py's _launch(), never written to any JSON file)."""

R2_ACCOUNT_ID = ""
R2_ACCESS_KEY_ID = ""
R2_SECRET_ACCESS_KEY = ""
R2_BUCKET_NAME = ""
