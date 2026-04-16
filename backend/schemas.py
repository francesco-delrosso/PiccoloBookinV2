from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PrenotazioneOut(BaseModel):
    id: int
    tipo_richiesta: Optional[str] = None
    nome: Optional[str] = None
    cognome: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    data_arrivo: Optional[str] = None
    data_partenza: Optional[str] = None
    adulti: Optional[int] = None
    bambini: Optional[int] = None
    posto_per: Optional[str] = None
    stato: Optional[str] = None
    costo_totale: Optional[float] = None
    data_ricezione: Optional[datetime] = None
    message_id: Optional[str] = None
    lingua_suggerita: Optional[str] = None
    model_config = {"from_attributes": True}


class PrenotazioneDetail(PrenotazioneOut):
    messaggi: list["MessaggioOut"] = []


class PrenotazioneUpdate(BaseModel):
    tipo_richiesta: Optional[str] = None
    nome: Optional[str] = None
    cognome: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    data_arrivo: Optional[str] = None
    data_partenza: Optional[str] = None
    adulti: Optional[int] = None
    bambini: Optional[int] = None
    posto_per: Optional[str] = None
    stato: Optional[str] = None
    costo_totale: Optional[float] = None
    lingua_suggerita: Optional[str] = None


class MessaggioOut(BaseModel):
    id: int
    id_prenotazione: int
    mittente: str
    testo: Optional[str] = None
    testo_tradotto: Optional[str] = None
    data_ora: Optional[datetime] = None
    message_id: Optional[str] = None
    model_config = {"from_attributes": True}


class MessaggioCreate(BaseModel):
    mittente: str
    testo: str


class ImpostazioneOut(BaseModel):
    id: int
    chiave: str
    valore: Optional[str] = None
    model_config = {"from_attributes": True}


class ImpostazioneUpdate(BaseModel):
    chiave: str
    valore: Optional[str] = None


class ImpostazioniBatch(BaseModel):
    impostazioni: list[ImpostazioneUpdate]


class ModelloMailOut(BaseModel):
    id: int
    lingua: str
    tipo: str
    soggetto: Optional[str] = None
    corpo: Optional[str] = None
    model_config = {"from_attributes": True}


class ModelloMailUpdate(BaseModel):
    soggetto: Optional[str] = None
    corpo: Optional[str] = None


class InviaMailRequest(BaseModel):
    modello_id: int
    testo_aggiuntivo: Optional[str] = ""


class InviaMessaggioRequest(BaseModel):
    testo: str
    soggetto: Optional[str] = ""


class JobStatus(BaseModel):
    job_id: Optional[str] = None
    status: str = "idle"
    total: int = 0
    processed: int = 0
    errors: list[str] = []
    started_at: Optional[datetime] = None
