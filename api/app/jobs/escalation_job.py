"""SLA / aging escalation runner (SCOPING §6.4, §8).

Run on a schedule to alert on sheets aging in the manager/finance review queues:

    python -m app.jobs.escalation_job

Intended to be triggered periodically (e.g. an Azure Container Apps cron job every 15 min,
or an Azure Logic App / Monitor scheduled query). The same logic is exposed as
`POST /admin/escalations/run` for an on-demand sweep from the portal.
"""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.db import engine
from app.services import escalation_service

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with Session(engine) as session:
        summary = escalation_service.run_escalations(session)
    logger.info(
        "escalation sweep: scanned=%d warnings=%d escalations=%d",
        summary.scanned, summary.warnings, summary.escalations,
    )


if __name__ == "__main__":
    main()
