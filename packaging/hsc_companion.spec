# PyInstaller spec for HSC Companion 2027 (macOS .app / Windows .exe / Linux folder).
# Build from the repository root:  pyinstaller packaging/hsc_companion.spec --noconfirm
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
VERSION = (ROOT / "VERSION").read_text().strip()

datas = [
    (str(ROOT / "app" / "templates"), "app/templates"),
    (str(ROOT / "app" / "static"), "app/static"),
    (str(ROOT / "migrations"), "migrations"),
    (str(ROOT / "data" / "seed"), "data/seed"),
    (str(ROOT / "alembic.ini"), "."),
    (str(ROOT / ".env.example"), "."),
    (str(ROOT / "VERSION"), "."),
]
hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + ["sqlalchemy.dialects.sqlite", "python_multipart", "multipart", "fitz", "pdfplumber", "dotenv", "httpx"]
)

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "IPython", "matplotlib", "PyQt5", "PySide6", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="HSC Companion", console=False,
    icon=str(ROOT / "packaging" / ("icon.icns" if sys.platform == "darwin" else "icon.ico")),
)
coll = COLLECT(exe, a.binaries, a.datas, name="HSC Companion")

if sys.platform == "darwin":
    app = BUNDLE(
        coll, name="HSC Companion.app", icon=str(ROOT / "packaging" / "icon.icns"), bundle_identifier="au.hsccompanion.app",
        info_plist={"CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION, "NSHighResolutionCapable": True,
                    "LSMinimumSystemVersion": "11.0", "CFBundleDisplayName": "HSC Companion"},
    )
