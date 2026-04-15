from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Impostazione
from schemas import ImpostazioneOut, ImpostazioneUpdate, ImpostazioniBatch

router = APIRouter()


@router.get("/", response_model=list[ImpostazioneOut])
def get_all(db: Session = Depends(get_db)):
    return db.query(Impostazione).order_by(Impostazione.chiave).all()


@router.put("/", response_model=ImpostazioneOut)
def update_one(data: ImpostazioneUpdate, db: Session = Depends(get_db)):
    row = db.query(Impostazione).filter(Impostazione.chiave == data.chiave).first()
    if row:
        row.valore = data.valore
    else:
        row = Impostazione(chiave=data.chiave, valore=data.valore)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/batch", response_model=list[ImpostazioneOut])
def update_batch(data: ImpostazioniBatch, db: Session = Depends(get_db)):
    results = []
    for item in data.impostazioni:
        row = db.query(Impostazione).filter(Impostazione.chiave == item.chiave).first()
        if row:
            row.valore = item.valore
        else:
            row = Impostazione(chiave=item.chiave, valore=item.valore)
            db.add(row)
        results.append(row)
    db.commit()
    for r in results:
        db.refresh(r)
    return results
