from sqlalchemy import func
from ..db import db


def next_code(model, prefix: str, year: int | None = None) -> str:
    from datetime import datetime
    year = year or datetime.now().year
    # Codes look like PREFIX-YYYY-001
    pattern = f"{prefix}-{year}-%"
    rows = db.session.query(model.code).filter(model.code.like(pattern)).all()
    max_num = 0
    for (code,) in rows:
        try:
            num = int(str(code).split('-')[-1])
            max_num = max(max_num, num)
        except Exception:
            continue
    return f"{prefix}-{year}-{max_num + 1:03d}"
