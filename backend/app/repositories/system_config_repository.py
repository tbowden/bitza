from typing import Optional

from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig


class SystemConfigRepository:
    """
    Data access for the one-row system_config table. No update/delete
    methods — the singleton is created exactly once (by
    BitzaService.create_root_bitza) and never modified afterward. If a
    future need arises to re-point root_bitza_id (e.g. a deliberate
    "designate a different bitza as root" migration), that should be a
    new, explicit, carefully-considered operation — not a casual update
    method sitting here inviting misuse.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self) -> Optional[SystemConfig]:
        return self._db.get(SystemConfig, 1)

    def create(self, root_bitza_id: str) -> SystemConfig:
        config = SystemConfig(id=1, root_bitza_id=root_bitza_id)
        self._db.add(config)
        self._db.flush()
        self._db.refresh(config)
        return config
