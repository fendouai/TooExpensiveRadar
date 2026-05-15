from sqlmodel import Session

from app.database import engine, init_db
from app.main import SEED_COMMENTS, persist_analysis
from app.models import TextIngestRequest

init_db()
with Session(engine) as session:
    for text in SEED_COMMENTS:
        persist_analysis(session, TextIngestRequest(content=text, platform="seed"))
print(f"Seeded {len(SEED_COMMENTS)} sample signals")
