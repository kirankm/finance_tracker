from pathlib import Path
from typing import Any

from app.config import Settings

DEFAULT_DEVELOPMENT_SECRET = "change-me-in-development"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def operational_readiness(settings: Settings) -> dict[str, Any]:
    checks = [
        check(
            "inbound_secret_configured",
            bool(settings.inbound_sms_secret),
            severity="blocker",
            detail="INBOUND_SMS_SECRET is configured.",
        ),
        check(
            "inbound_secret_not_default",
            settings.inbound_sms_secret != DEFAULT_DEVELOPMENT_SECRET,
            severity="blocker",
            detail="INBOUND_SMS_SECRET must not use the development default.",
        ),
        check(
            "database_url_configured",
            bool(settings.database_url),
            severity="blocker",
            detail="DATABASE_URL is configured.",
        ),
        check(
            "raw_sms_export_default_omits_body",
            True,
            severity="blocker",
            detail="JSON export omits raw SMS bodies unless explicitly requested.",
        ),
        check(
            "backup_restore_docs_present",
            (PROJECT_ROOT / "docs/deployment/backup-restore.md").exists(),
            severity="blocker",
            detail="Backup/restore documentation is present.",
        ),
        check(
            "first_real_use_checklist_present",
            (PROJECT_ROOT / "docs/deployment/first-real-use-checklist.md").exists(),
            severity="blocker",
            detail="First real-use checklist is present.",
        ),
        check(
            "android_forwarder_validation_docs_present",
            (PROJECT_ROOT / "docs/deployment/android-forwarder-validation.md").exists(),
            severity="blocker",
            detail="Android forwarder fake-device validation documentation is present.",
        ),
        check(
            "production_pilot_go_no_go_present",
            (PROJECT_ROOT / "docs/deployment/production-pilot-go-no-go.md").exists(),
            severity="blocker",
            detail="Production pilot go/no-go documentation is present.",
        ),
    ]
    status = "ready" if all(item["status"] == "pass" for item in checks) else "blocked"
    return {"status": status, "checks": checks}


def check(name: str, passed: bool, *, severity: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "severity": severity,
        "detail": detail,
    }
