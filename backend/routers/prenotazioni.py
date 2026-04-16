"""
Prenotazioni router — full CRUD + actions (send mail, translate).
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Prenotazione, StoricoMessaggio, Impostazione, ModelloMail
from schemas import (
    PrenotazioneOut,
    PrenotazioneDetail,
    PrenotazioneUpdate,
    MessaggioOut,
    MessaggioCreate,
    InviaMailRequest,
    InviaMessaggioRequest,
)
from services.mail_sender import send_email
from services.smart_parser import translate_to_italian

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_settings(db: Session) -> dict:
    rows = db.query(Impostazione).all()
    return {r.chiave: r.valore for r in rows}


def _get_pren_or_404(db: Session, pren_id: int) -> Prenotazione:
    p = db.query(Prenotazione).filter_by(id=pren_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")
    return p


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[PrenotazioneOut])
def list_prenotazioni(db: Session = Depends(get_db)):
    """List all prenotazioni, ordered by data_ricezione desc."""
    return (
        db.query(Prenotazione)
        .order_by(Prenotazione.data_ricezione.desc())
        .all()
    )


@router.get("/{pren_id}", response_model=PrenotazioneDetail)
def get_prenotazione(pren_id: int, db: Session = Depends(get_db)):
    """Get single prenotazione with joinedload messaggi."""
    p = (
        db.query(Prenotazione)
        .options(joinedload(Prenotazione.messaggi))
        .filter_by(id=pren_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")
    return p


@router.patch("/{pren_id}", response_model=PrenotazioneOut)
def update_prenotazione(
    pren_id: int, data: PrenotazioneUpdate, db: Session = Depends(get_db)
):
    """Update prenotazione fields (only those provided)."""
    p = _get_pren_or_404(db, pren_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{pren_id}")
def delete_prenotazione(pren_id: int, db: Session = Depends(get_db)):
    """Delete prenotazione with cascade."""
    p = _get_pren_or_404(db, pren_id)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
@router.post("/{pren_id}/messaggi", response_model=MessaggioOut)
def add_messaggio(
    pren_id: int, data: MessaggioCreate, db: Session = Depends(get_db)
):
    """Add a manual message to the prenotazione."""
    _get_pren_or_404(db, pren_id)
    msg = StoricoMessaggio(
        id_prenotazione=pren_id,
        mittente=data.mittente,
        testo=data.testo,
        data_ora=datetime.now(timezone.utc),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Send free-text email (no template)
# ---------------------------------------------------------------------------
@router.post("/{pren_id}/invia-messaggio")
def invia_messaggio(
    pren_id: int, data: InviaMessaggioRequest, db: Session = Depends(get_db)
):
    """Send a free-text email to the client and save in thread."""
    p = _get_pren_or_404(db, pren_id)
    if not p.email:
        raise HTTPException(status_code=400, detail="Prenotazione senza email cliente")

    settings = _load_settings(db)

    subject = data.soggetto or f"Re: Piccolo Camping"

    # Find last client message for In-Reply-To
    last_msg = (
        db.query(StoricoMessaggio)
        .filter_by(id_prenotazione=pren_id, mittente="Cliente")
        .order_by(StoricoMessaggio.data_ora.desc())
        .first()
    )
    reply_to = last_msg.message_id if last_msg else None

    try:
        new_mid = send_email(
            to_addr=p.email,
            subject=subject,
            body=data.testo,
            settings=settings,
            reply_to_message_id=reply_to,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore invio: {e}")

    msg = StoricoMessaggio(
        id_prenotazione=pren_id,
        mittente="Campeggio",
        testo=data.testo,
        message_id=new_mid,
        data_ora=datetime.now(timezone.utc),
    )
    db.add(msg)

    # Update stato based on action type
    if data.tipo_azione == "accetta":
        p.stato = "Attesa Bonifico"
    elif data.tipo_azione == "accetta_noCaparra":
        p.stato = "Confermata"
    elif data.tipo_azione == "rifiuta":
        p.stato = "Rifiutata"
    elif p.stato in ("Nuova", "Nuova Risposta"):
        p.stato = "In lavorazione"

    db.commit()
    db.refresh(msg)
    return {"ok": True, "message_id": new_mid}


# ---------------------------------------------------------------------------
# Send email via template
# ---------------------------------------------------------------------------
@router.post("/{pren_id}/invia-mail")
def invia_mail_prenotazione(
    pren_id: int, data: InviaMailRequest, db: Session = Depends(get_db)
):
    """Send email using a template.

    Loads the ModelloMail by id, applies variable replacements, sends via SMTP,
    saves as StoricoMessaggio, updates stato.
    """
    p = _get_pren_or_404(db, pren_id)

    # Load template
    template = db.query(ModelloMail).filter_by(id=data.modello_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Modello mail non trovato")

    if not p.email:
        raise HTTPException(status_code=400, detail="Prenotazione senza email cliente")

    settings = _load_settings(db)

    # Calculate caparra
    caparra_pct = float(settings.get("caparra_percentuale", "30"))
    costo = p.costo_totale or 0
    caparra = round(costo * caparra_pct / 100, 2) if costo else ""

    # Apply variable replacements
    replacements = {
        "nome": p.nome or "",
        "cognome": p.cognome or "",
        "data_arrivo": p.data_arrivo or "",
        "data_partenza": p.data_partenza or "",
        "adulti": str(p.adulti) if p.adulti is not None else "",
        "bambini": str(p.bambini) if p.bambini is not None else "",
        "posto_per": p.posto_per or "",
        "costo_totale": str(costo) if costo else "",
        "caparra": str(caparra) if caparra else "",
        "caparra_percentuale": str(int(caparra_pct)),
        "testo_aggiuntivo": data.testo_aggiuntivo or "",
    }

    try:
        corpo = template.corpo.format(**replacements)
        soggetto = template.soggetto.format(**replacements) if template.soggetto else ""
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Variabile mancante nel template: {e}",
        )

    # Find last client message_id for In-Reply-To threading
    last_client_msg = (
        db.query(StoricoMessaggio)
        .filter_by(id_prenotazione=pren_id, mittente="Cliente")
        .order_by(StoricoMessaggio.data_ora.desc())
        .first()
    )
    reply_to_mid = last_client_msg.message_id if last_client_msg else None

    # Send
    try:
        new_mid = send_email(
            to_addr=p.email,
            subject=soggetto,
            body=corpo,
            settings=settings,
            reply_to_message_id=reply_to_mid,
        )
    except Exception as e:
        logger.error("Invio mail fallito per #%d: %s", pren_id, e)
        raise HTTPException(status_code=500, detail=f"Invio fallito: {e}")

    # Save sent message
    db.add(StoricoMessaggio(
        id_prenotazione=pren_id,
        mittente="Campeggio",
        testo=f"[EMAIL {template.tipo.upper()} - {template.lingua}]\n"
              f"Oggetto: {soggetto}\n\n{corpo}",
        message_id=new_mid,
        data_ora=datetime.now(timezone.utc),
    ))

    # Update stato based on template type
    tipo = template.tipo.lower()
    if tipo == "accetta":
        p.stato = "Attesa Bonifico"
    elif tipo == "rifiuta":
        p.stato = "Rifiutata"
    elif tipo == "info":
        if p.stato in ("Nuova", "Nuova Risposta"):
            p.stato = "In lavorazione"

    db.commit()
    db.refresh(p)

    return {
        "success": True,
        "message_id": new_mid,
        "stato": p.stato,
    }


# ---------------------------------------------------------------------------
# Translate
# ---------------------------------------------------------------------------
@router.post("/{pren_id}/traduci")
def traduci_conversazione(pren_id: int, db: Session = Depends(get_db)):
    """Translate all untranslated messages via Ollama, store in testo_tradotto."""
    p = (
        db.query(Prenotazione)
        .options(joinedload(Prenotazione.messaggi))
        .filter_by(id=pren_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    settings = _load_settings(db)
    tradotti = 0

    for msg in p.messaggi:
        if msg.testo_tradotto:
            continue  # already translated
        if not msg.testo:
            continue
        traduzione = translate_to_italian(msg.testo, settings)
        if traduzione:
            msg.testo_tradotto = traduzione
            tradotti += 1

    if tradotti:
        db.commit()

    return {
        "success": True,
        "tradotti": tradotti,
        "messaggi": [MessaggioOut.model_validate(m) for m in p.messaggi],
    }
