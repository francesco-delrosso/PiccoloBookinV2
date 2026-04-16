import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import inspect, text

from database import Base, engine, SessionLocal
from models import Impostazione, ModelloMail

from routers import prenotazioni, mail, impostazioni, modelli, prezzi

logger = logging.getLogger("camping")

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------
_DEFAULT_SETTINGS: dict[str, str] = {
    "imap_server": "imaps.aruba.it",
    "imap_port": "993",
    "imap_user": "info@piccolocamping.com",
    "imap_password": "",
    "smtp_server": "smtps.aruba.it",
    "smtp_port": "587",
    "smtp_user": "info@piccolocamping.com",
    "smtp_password": "",
    "email_mittente": "info@piccolocamping.com",
    "email_form_sito": "contatti@piccolocamping.com",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "phi3:mini",
    "ollama_workers": "4",
    "caparra_percentuale": "30",
    "filtro_domini_scarta": "aruba.it",
    "filtro_oggetto_scarta": "Fattura,Rinnovo,Scadenza",
    "poll_interval_minutes": "10",
}

# ---------------------------------------------------------------------------
# Default price list
# ---------------------------------------------------------------------------
_DEFAULT_LISTINO = json.dumps(
    {
        "stagioni": [
            {"nome": "Bassa", "colore": "#4A7C9B", "periodi": [["2026-04-01", "2026-06-14"], ["2026-09-01", "2026-09-30"]]},
            {"nome": "Media", "colore": "#8B6914", "periodi": [["2026-06-15", "2026-07-14"]]},
            {"nome": "Alta", "colore": "#DC2626", "periodi": [["2026-07-15", "2026-08-31"]]},
        ],
        "voci": [
            {"id": "v1", "categoria": "Piazzola", "nome": "Tenda piccola (max 4m)", "prezzi": [8, 10, 14], "note": ""},
            {"id": "v2", "categoria": "Piazzola", "nome": "Tenda grande (oltre 4m)", "prezzi": [10, 13, 17], "note": ""},
            {"id": "v3", "categoria": "Piazzola", "nome": "Camper / Caravan", "prezzi": [11, 14, 18], "note": ""},
            {"id": "v4", "categoria": "Persone", "nome": "Adulto", "prezzi": [7, 8.5, 10], "note": ""},
            {"id": "v5", "categoria": "Persone", "nome": "Bambino (3-12 anni)", "prezzi": [4, 5, 6], "note": ""},
            {"id": "v6", "categoria": "Persone", "nome": "Bambino (0-2 anni)", "prezzi": [0, 0, 0], "note": "Gratis"},
            {"id": "v7", "categoria": "Extra", "nome": "Elettricita (al giorno)", "prezzi": [4, 4, 5], "note": ""},
            {"id": "v8", "categoria": "Extra", "nome": "Cane", "prezzi": [3, 3, 4], "note": ""},
            {"id": "v9", "categoria": "Extra", "nome": "Frigorifero (al giorno)", "prezzi": [3.5, 3.5, 4], "note": ""},
            {"id": "v10", "categoria": "Bungalow", "nome": "Bungalow 2 persone", "prezzi": [45, 55, 70], "note": ""},
            {"id": "v11", "categoria": "Bungalow", "nome": "Bungalow 4 persone", "prezzi": [65, 80, 100], "note": ""},
        ],
    },
    ensure_ascii=False,
)

# ---------------------------------------------------------------------------
# Default email templates  (5 languages x 3 types)
# ---------------------------------------------------------------------------
_DEFAULT_TEMPLATES: list[dict] = [
    # --- Italiano ---
    {
        "lingua": "IT",
        "tipo": "accetta",
        "soggetto": "Conferma prenotazione - Piccolo Camping",
        "corpo": (
            "Gentile {nome},\n\n"
            "siamo lieti di confermare la Sua prenotazione presso il Piccolo Camping.\n\n"
            "Riepilogo:\n"
            "- Arrivo: {data_arrivo}\n"
            "- Partenza: {data_partenza}\n"
            "- Ospiti: {adulti} adulti, {bambini} bambini\n"
            "- Piazzola: {posto_per}\n"
            "- Totale stimato: EUR {costo_totale}\n\n"
            "Per confermare definitivamente Le chiediamo di effettuare un bonifico "
            "pari al {caparra_percentuale}% dell'importo totale entro 7 giorni.\n\n"
            "Coordinate bancarie:\n"
            "IBAN: IT00 0000 0000 0000 0000 0000 000\n"
            "Intestato a: Piccolo Camping S.r.l.\n"
            "Causale: Prenotazione {nome} {data_arrivo}\n\n"
            "Restiamo a disposizione per qualsiasi chiarimento.\n\n"
            "Cordiali saluti,\n"
            "Lo Staff del Piccolo Camping"
        ),
    },
    {
        "lingua": "IT",
        "tipo": "rifiuta",
        "soggetto": "Prenotazione non disponibile - Piccolo Camping",
        "corpo": (
            "Gentile {nome},\n\n"
            "La ringraziamo per il Suo interesse verso il Piccolo Camping.\n\n"
            "Purtroppo per il periodo richiesto ({data_arrivo} - {data_partenza}) "
            "non disponiamo di piazzole disponibili.\n\n"
            "Le suggeriamo di verificare la disponibilità per date alternative "
            "oppure di contattarci telefonicamente per valutare insieme altre soluzioni.\n\n"
            "Ci auguriamo di poterLa ospitare in futuro.\n\n"
            "Cordiali saluti,\n"
            "Lo Staff del Piccolo Camping"
        ),
    },
    {
        "lingua": "IT",
        "tipo": "info",
        "soggetto": "Informazioni - Piccolo Camping",
        "corpo": (
            "Gentile {nome},\n\n"
            "La ringraziamo per averci contattato.\n\n"
            "Siamo lieti di fornirLe tutte le informazioni di cui ha bisogno "
            "riguardo al nostro campeggio e ai servizi offerti.\n\n"
            "{testo_aggiuntivo}\n\n"
            "Non esiti a contattarci per ulteriori domande.\n\n"
            "Cordiali saluti,\n"
            "Lo Staff del Piccolo Camping"
        ),
    },
    # --- English ---
    {
        "lingua": "EN",
        "tipo": "accetta",
        "soggetto": "Booking Confirmation - Piccolo Camping",
        "corpo": (
            "Dear {nome},\n\n"
            "We are pleased to confirm your reservation at Piccolo Camping.\n\n"
            "Summary:\n"
            "- Arrival: {data_arrivo}\n"
            "- Departure: {data_partenza}\n"
            "- Guests: {adulti} adults, {bambini} children\n"
            "- Pitch: {posto_per}\n"
            "- Estimated total: EUR {costo_totale}\n\n"
            "To finalise your booking, please transfer a deposit of "
            "{caparra_percentuale}% of the total amount within 7 days.\n\n"
            "Bank details:\n"
            "IBAN: IT00 0000 0000 0000 0000 0000 000\n"
            "Account holder: Piccolo Camping S.r.l.\n"
            "Reference: Booking {nome} {data_arrivo}\n\n"
            "Please do not hesitate to contact us if you have any questions.\n\n"
            "Kind regards,\n"
            "The Piccolo Camping Team"
        ),
    },
    {
        "lingua": "EN",
        "tipo": "rifiuta",
        "soggetto": "Booking Unavailable - Piccolo Camping",
        "corpo": (
            "Dear {nome},\n\n"
            "Thank you for your interest in Piccolo Camping.\n\n"
            "Unfortunately, we do not have availability for the requested period "
            "({data_arrivo} - {data_partenza}).\n\n"
            "We suggest checking alternative dates or calling us directly "
            "so we can explore other options together.\n\n"
            "We hope to welcome you in the future.\n\n"
            "Kind regards,\n"
            "The Piccolo Camping Team"
        ),
    },
    {
        "lingua": "EN",
        "tipo": "info",
        "soggetto": "Information - Piccolo Camping",
        "corpo": (
            "Dear {nome},\n\n"
            "Thank you for reaching out to us.\n\n"
            "We are happy to provide you with all the information you need "
            "about our campsite and the services we offer.\n\n"
            "{testo_aggiuntivo}\n\n"
            "Do not hesitate to contact us with any further questions.\n\n"
            "Kind regards,\n"
            "The Piccolo Camping Team"
        ),
    },
    # --- Deutsch ---
    {
        "lingua": "DE",
        "tipo": "accetta",
        "soggetto": "Buchungsbestaetigung - Piccolo Camping",
        "corpo": (
            "Sehr geehrte/r {nome},\n\n"
            "wir freuen uns, Ihre Reservierung im Piccolo Camping bestaetigen zu koennen.\n\n"
            "Zusammenfassung:\n"
            "- Anreise: {data_arrivo}\n"
            "- Abreise: {data_partenza}\n"
            "- Gaeste: {adulti} Erwachsene, {bambini} Kinder\n"
            "- Stellplatz: {posto_per}\n"
            "- Geschaetzter Gesamtbetrag: EUR {costo_totale}\n\n"
            "Um Ihre Buchung abzuschliessen, ueberweisen Sie bitte eine Anzahlung "
            "von {caparra_percentuale}% des Gesamtbetrags innerhalb von 7 Tagen.\n\n"
            "Bankverbindung:\n"
            "IBAN: IT00 0000 0000 0000 0000 0000 000\n"
            "Kontoinhaber: Piccolo Camping S.r.l.\n"
            "Verwendungszweck: Buchung {nome} {data_arrivo}\n\n"
            "Fuer Rueckfragen stehen wir Ihnen gerne zur Verfuegung.\n\n"
            "Mit freundlichen Gruessen,\n"
            "Das Team vom Piccolo Camping"
        ),
    },
    {
        "lingua": "DE",
        "tipo": "rifiuta",
        "soggetto": "Buchung nicht verfuegbar - Piccolo Camping",
        "corpo": (
            "Sehr geehrte/r {nome},\n\n"
            "vielen Dank fuer Ihr Interesse am Piccolo Camping.\n\n"
            "Leider haben wir fuer den gewuenschten Zeitraum "
            "({data_arrivo} - {data_partenza}) keine Verfuegbarkeit.\n\n"
            "Wir empfehlen Ihnen, alternative Termine zu pruefen oder uns "
            "telefonisch zu kontaktieren, damit wir gemeinsam andere "
            "Moeglichkeiten besprechen koennen.\n\n"
            "Wir hoffen, Sie in Zukunft bei uns begruessen zu duerfen.\n\n"
            "Mit freundlichen Gruessen,\n"
            "Das Team vom Piccolo Camping"
        ),
    },
    {
        "lingua": "DE",
        "tipo": "info",
        "soggetto": "Informationen - Piccolo Camping",
        "corpo": (
            "Sehr geehrte/r {nome},\n\n"
            "vielen Dank fuer Ihre Anfrage.\n\n"
            "Gerne stellen wir Ihnen alle Informationen ueber unseren "
            "Campingplatz und unsere Dienstleistungen zur Verfuegung.\n\n"
            "{testo_aggiuntivo}\n\n"
            "Fuer weitere Fragen stehen wir Ihnen jederzeit gerne zur Verfuegung.\n\n"
            "Mit freundlichen Gruessen,\n"
            "Das Team vom Piccolo Camping"
        ),
    },
    # --- Francais ---
    {
        "lingua": "FR",
        "tipo": "accetta",
        "soggetto": "Confirmation de reservation - Piccolo Camping",
        "corpo": (
            "Cher/Chere {nome},\n\n"
            "Nous avons le plaisir de confirmer votre reservation au Piccolo Camping.\n\n"
            "Recapitulatif :\n"
            "- Arrivee : {data_arrivo}\n"
            "- Depart : {data_partenza}\n"
            "- Personnes : {adulti} adultes, {bambini} enfants\n"
            "- Emplacement : {posto_per}\n"
            "- Total estime : EUR {costo_totale}\n\n"
            "Pour finaliser votre reservation, nous vous prions d'effectuer "
            "un virement de {caparra_percentuale}% du montant total sous 7 jours.\n\n"
            "Coordonnees bancaires :\n"
            "IBAN : IT00 0000 0000 0000 0000 0000 000\n"
            "Titulaire : Piccolo Camping S.r.l.\n"
            "Reference : Reservation {nome} {data_arrivo}\n\n"
            "N'hesitez pas a nous contacter pour toute question.\n\n"
            "Cordialement,\n"
            "L'equipe du Piccolo Camping"
        ),
    },
    {
        "lingua": "FR",
        "tipo": "rifiuta",
        "soggetto": "Reservation non disponible - Piccolo Camping",
        "corpo": (
            "Cher/Chere {nome},\n\n"
            "Nous vous remercions de l'interet que vous portez au Piccolo Camping.\n\n"
            "Malheureusement, nous n'avons pas de disponibilite pour la periode "
            "demandee ({data_arrivo} - {data_partenza}).\n\n"
            "Nous vous suggérons de verifier d'autres dates ou de nous "
            "appeler directement afin d'explorer d'autres solutions ensemble.\n\n"
            "Nous esperons pouvoir vous accueillir prochainement.\n\n"
            "Cordialement,\n"
            "L'equipe du Piccolo Camping"
        ),
    },
    {
        "lingua": "FR",
        "tipo": "info",
        "soggetto": "Informations - Piccolo Camping",
        "corpo": (
            "Cher/Chere {nome},\n\n"
            "Merci de nous avoir contactes.\n\n"
            "Nous sommes heureux de vous fournir toutes les informations "
            "necessaires sur notre camping et les services que nous proposons.\n\n"
            "{testo_aggiuntivo}\n\n"
            "N'hesitez pas a nous contacter pour toute question supplementaire.\n\n"
            "Cordialement,\n"
            "L'equipe du Piccolo Camping"
        ),
    },
    # --- Nederlands ---
    {
        "lingua": "NL",
        "tipo": "accetta",
        "soggetto": "Boekingsbevestiging - Piccolo Camping",
        "corpo": (
            "Beste {nome},\n\n"
            "Met genoegen bevestigen wij uw reservering bij Piccolo Camping.\n\n"
            "Samenvatting:\n"
            "- Aankomst: {data_arrivo}\n"
            "- Vertrek: {data_partenza}\n"
            "- Gasten: {adulti} volwassenen, {bambini} kinderen\n"
            "- Standplaats: {posto_per}\n"
            "- Geschat totaal: EUR {costo_totale}\n\n"
            "Om uw boeking definitief te maken, vragen wij u een aanbetaling "
            "van {caparra_percentuale}% van het totaalbedrag binnen 7 dagen over te maken.\n\n"
            "Bankgegevens:\n"
            "IBAN: IT00 0000 0000 0000 0000 0000 000\n"
            "Rekeninghouder: Piccolo Camping S.r.l.\n"
            "Omschrijving: Reservering {nome} {data_arrivo}\n\n"
            "Neem gerust contact met ons op als u vragen heeft.\n\n"
            "Met vriendelijke groet,\n"
            "Het team van Piccolo Camping"
        ),
    },
    {
        "lingua": "NL",
        "tipo": "rifiuta",
        "soggetto": "Boeking niet beschikbaar - Piccolo Camping",
        "corpo": (
            "Beste {nome},\n\n"
            "Bedankt voor uw interesse in Piccolo Camping.\n\n"
            "Helaas hebben wij geen beschikbaarheid voor de gevraagde periode "
            "({data_arrivo} - {data_partenza}).\n\n"
            "Wij raden u aan om alternatieve data te bekijken of ons telefonisch "
            "te contacteren zodat we samen andere mogelijkheden kunnen bespreken.\n\n"
            "Wij hopen u in de toekomst te mogen verwelkomen.\n\n"
            "Met vriendelijke groet,\n"
            "Het team van Piccolo Camping"
        ),
    },
    {
        "lingua": "NL",
        "tipo": "info",
        "soggetto": "Informatie - Piccolo Camping",
        "corpo": (
            "Beste {nome},\n\n"
            "Bedankt voor uw bericht.\n\n"
            "Wij voorzien u graag van alle informatie die u nodig heeft "
            "over onze camping en de diensten die wij aanbieden.\n\n"
            "{testo_aggiuntivo}\n\n"
            "Aarzel niet om contact met ons op te nemen bij verdere vragen.\n\n"
            "Met vriendelijke groet,\n"
            "Het team van Piccolo Camping"
        ),
    },
]

# ---------------------------------------------------------------------------
# DB migrations (ALTER TABLE ADD COLUMN)
# ---------------------------------------------------------------------------
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("prenotazioni", "lingua_suggerita", "VARCHAR"),
    ("prenotazioni", "costo_totale", "FLOAT"),
    ("storico_messaggi", "testo_tradotto", "TEXT"),
]


def _run_migrations() -> None:
    """Add missing columns to existing tables (idempotent)."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, column, col_type in _MIGRATIONS:
            if table not in inspector.get_table_names():
                continue
            existing = [c["name"] for c in inspector.get_columns(table)]
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                logger.info("Migration: added %s.%s (%s)", table, column, col_type)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------
def _seed_defaults() -> None:
    """Insert default settings if they don't exist."""
    db = SessionLocal()
    try:
        for key, value in _DEFAULT_SETTINGS.items():
            exists = db.query(Impostazione).filter(Impostazione.chiave == key).first()
            if not exists:
                db.add(Impostazione(chiave=key, valore=value))
        # Price list
        exists = db.query(Impostazione).filter(Impostazione.chiave == "listino_prezzi").first()
        if not exists:
            db.add(Impostazione(chiave="listino_prezzi", valore=_DEFAULT_LISTINO))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _seed_templates() -> None:
    """Insert default email templates if the table is empty."""
    db = SessionLocal()
    try:
        count = db.query(ModelloMail).count()
        if count == 0:
            for tpl in _DEFAULT_TEMPLATES:
                db.add(ModelloMail(**tpl))
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
scheduler = BackgroundScheduler()


def _scheduled_poll() -> None:
    from services.mail_poller import poll_emails

    db = SessionLocal()
    try:
        poll_emails(db)
    except Exception:
        logger.exception("Scheduled poll failed")
    finally:
        db.close()


def _start_scheduler() -> None:
    db = SessionLocal()
    try:
        row = db.query(Impostazione).filter(Impostazione.chiave == "poll_interval_minutes").first()
        interval = int(row.valore) if row and row.valore else 10
    finally:
        db.close()

    scheduler.add_job(
        _scheduled_poll,
        "interval",
        minutes=interval,
        id="email_poll",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: polling every %d minutes", interval)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _seed_defaults()
    _seed_templates()
    _start_scheduler()
    logger.info("CampingV2 backend ready")
    yield
    # Shutdown
    scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="CampingV2 API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(prenotazioni.router, prefix="/api/prenotazioni", tags=["prenotazioni"])
app.include_router(mail.router, prefix="/api/mail", tags=["mail"])
app.include_router(impostazioni.router, prefix="/api/impostazioni", tags=["impostazioni"])
app.include_router(modelli.router, prefix="/api/modelli", tags=["modelli"])
app.include_router(prezzi.router, prefix="/api/prezzi", tags=["prezzi"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
