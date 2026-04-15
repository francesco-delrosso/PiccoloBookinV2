import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Impostazione

router = APIRouter()


@router.get("/")
def get_prezzi(db: Session = Depends(get_db)):
    row = db.query(Impostazione).filter(Impostazione.chiave == "listino_prezzi").first()
    if not row or not row.valore:
        return {"stagioni": [], "voci": []}
    return json.loads(row.valore)


@router.put("/")
def update_prezzi(body: dict, db: Session = Depends(get_db)):
    row = db.query(Impostazione).filter(Impostazione.chiave == "listino_prezzi").first()
    if not row:
        row = Impostazione(chiave="listino_prezzi", valore=json.dumps(body))
        db.add(row)
    else:
        row.valore = json.dumps(body)
    db.commit()
    return body
