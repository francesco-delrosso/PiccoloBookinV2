from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Prenotazione(Base):
    __tablename__ = "prenotazioni"

    id = Column(Integer, primary_key=True, index=True)
    tipo_richiesta = Column(String, default="Contatto")
    nome = Column(String, nullable=True)
    cognome = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    data_arrivo = Column(String, nullable=True)
    data_partenza = Column(String, nullable=True)
    adulti = Column(Integer, nullable=True)
    bambini = Column(Integer, nullable=True)
    posto_per = Column(String, nullable=True)
    stato = Column(String, default="Nuova")
    costo_totale = Column(Float, nullable=True)
    data_ricezione = Column(DateTime, default=lambda: datetime.now())
    message_id = Column(String, unique=True, nullable=True)
    lingua_suggerita = Column(String, nullable=True)

    messaggi = relationship(
        "StoricoMessaggio",
        back_populates="prenotazione",
        cascade="all, delete-orphan",
        order_by="StoricoMessaggio.data_ora",
    )


class StoricoMessaggio(Base):
    __tablename__ = "storico_messaggi"

    id = Column(Integer, primary_key=True, index=True)
    id_prenotazione = Column(
        Integer, ForeignKey("prenotazioni.id", ondelete="CASCADE"), nullable=False
    )
    mittente = Column(String, nullable=False)
    testo = Column(Text, nullable=True)
    testo_tradotto = Column(Text, nullable=True)
    data_ora = Column(DateTime, default=lambda: datetime.now())
    message_id = Column(String, unique=True, nullable=True)

    prenotazione = relationship("Prenotazione", back_populates="messaggi")


class Impostazione(Base):
    __tablename__ = "impostazioni"

    id = Column(Integer, primary_key=True, index=True)
    chiave = Column(String, unique=True, nullable=False)
    valore = Column(Text, nullable=True)


class ModelloMail(Base):
    __tablename__ = "modelli_mail"

    id = Column(Integer, primary_key=True, index=True)
    lingua = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    soggetto = Column(String, nullable=True)
    corpo = Column(Text, nullable=True)
