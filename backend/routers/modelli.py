from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ModelloMail
from schemas import ModelloMailOut, ModelloMailUpdate

router = APIRouter()


@router.get("/", response_model=list[ModelloMailOut])
def get_all(db: Session = Depends(get_db)):
    return db.query(ModelloMail).order_by(ModelloMail.lingua, ModelloMail.tipo).all()


@router.put("/{modello_id}", response_model=ModelloMailOut)
def update(modello_id: int, data: ModelloMailUpdate, db: Session = Depends(get_db)):
    row = db.query(ModelloMail).filter(ModelloMail.id == modello_id).first()
    if not row:
        raise HTTPException(404, "Template not found")
    if data.soggetto is not None:
        row.soggetto = data.soggetto
    if data.corpo is not None:
        row.corpo = data.corpo
    db.commit()
    db.refresh(row)
    return row


@router.get("/preview/{modello_id}")
def preview(modello_id: int, db: Session = Depends(get_db)):
    row = db.query(ModelloMail).filter(ModelloMail.id == modello_id).first()
    if not row:
        raise HTTPException(404, "Template not found")

    sample = {
        "nome": "Mario", "cognome": "Rossi",
        "data_arrivo": "2026-07-15", "data_partenza": "2026-07-22",
        "adulti": "2", "bambini": "1", "posto_per": "camper",
        "costo_totale": "350.00", "caparra": "105.00",
        "testo_aggiuntivo": "Nota aggiuntiva di esempio.",
    }

    soggetto = row.soggetto or ""
    corpo = row.corpo or ""
    for key, val in sample.items():
        soggetto = soggetto.replace("{" + key + "}", val)
        corpo = corpo.replace("{" + key + "}", val)
    return {"soggetto": soggetto, "corpo": corpo}
