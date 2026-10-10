"""Run with:  python -m app"""
import logging

import uvicorn

from app.config import config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if config.host not in ("127.0.0.1", "localhost"):
        logging.warning("HSC_HOST=%s exposes the app beyond this computer. Use 127.0.0.1 unless you mean to.", config.host)
    from app.main import create_app

    app = create_app()
    try:
        from app.services.backup import auto_backup

        auto_backup()  # daily safety copy (the 14 most recent are kept in data/backups)
    except Exception:
        logging.getLogger("hsc").exception("automatic backup failed")
    print(f"\n  HSC Companion 2027 is running: http://{config.host}:{config.port}\n  Press Ctrl+C to stop.\n")
    uvicorn.run(app, host=config.host, port=config.port, log_level="warning")


if __name__ == "__main__":
    main()
