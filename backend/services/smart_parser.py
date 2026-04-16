import json
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value guards — Ollama (phi3:mini) sometimes returns list/dict for strings
# ---------------------------------------------------------------------------
def _str_or_none(val) -> str | None:
    """Return a string or None; collapse lists/dicts to None."""
    if val is None:
        return None
    if isinstance(val, str):
        return val.strip() or None
    if isinstance(val, (int, float)):
        return str(val)
    return None


def _int_or_none(val) -> int | None:
    """Return an int or None; collapse non-numeric values."""
    if val is None:
        return None
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        try:
            return int(val)
        except ValueError:
            return None
    return None


def _float_or_none(val) -> float | None:
    """Return a float or None; collapse non-numeric values."""
    if val is None:
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def _build_parse_prompt(from_addr: str, subject: str, body: str) -> str:
    current_year = datetime.now().year
    email_text = f"From: {from_addr}\nSubject: {subject}\n\n{body}"[:3000]

    return f"""You are a classifier for a small Italian lakeside campsite called "Piccolo Camping" (Lake Como, Italy).
The email may be in Italian, English, German, French, Dutch, or Spanish.

Return ONLY a valid JSON object — no extra text, no markdown, no explanation.

{{{{
  "tipo": "contatto",
  "nome": null,
  "cognome": null,
  "telefono": null,
  "data_arrivo": null,
  "data_partenza": null,
  "adulti": null,
  "bambini": null,
  "posto_per": null,
  "lingua": "IT",
  "confidenza": 0.0
}}}}

CRITICAL RULE — "tipo" field:
  "prenotazione" → A real PERSON (tourist/camper) explicitly wants to BOOK a pitch/spot at this campsite AND mentions dates or number of people.
  "contatto"     → A real PERSON (tourist/camper) asks a question or requests information about staying at this campsite (prices, availability, facilities, directions, etc.) WITHOUT a booking request.
  "spam"         → EVERYTHING ELSE. Mark as spam if ANY of the following is true:
    - The sender is selling or promoting a product or service TO the campsite (washing machines, solar panels, software, advertising, websites, laundry equipment, etc.)
    - The email is a newsletter, promotional offer, or marketing message from any company
    - The email is from a payment processor, bank, or financial service (Nexi, PayPal, Stripe, etc.)
    - The email is about another business or tourist facility (hotel, spa, restaurant, etc.)
    - The email is an automated notification, system alert, invoice, receipt, or reminder
    - The sender is not a private individual looking to camp at this specific campsite
    - There is no mention of camping, holidays, staying at a campsite, tents, caravans, campers, or similar

SPAM EXAMPLES (classify ALL of these as spam with confidenza >= 0.8):
- "Offriamo lavatrici/asciugatrici per il vostro campeggio" → spam
- "Express Wash forniamo lavatrici" → spam
- "Rinnovare la struttura / progetto benessere / spa" → spam
- "Buongiorno, siamo un'agenzia di marketing..." → spam
- "Notifica pagamento / transazione" → spam
- "Newsletter / offerta commerciale" → spam
- "Pannelli solari / fotovoltaico per la vostra struttura" → spam
- "Noleggio attrezzature / giostre / gonfiabili" → spam
- "Fattura / rinnovo abbonamento / scadenza" → spam

Other rules:
- "data_arrivo" / "data_partenza": YYYY-MM-DD. Extract ONLY the camping stay dates (check-in / check-out). Ignore travel dates, email send dates, or dates in quoted/previous messages. The EARLIER date is arrivo, the LATER is partenza. Use {current_year} if year is missing.
- "adulti" / "bambini": integer, null if not stated
- "posto_per": "tenda" | "camper" | "caravan" | "bungalow" | null
  tent/tenda/zelt/tente → tenda; motorhome/wohnmobil/camping-car/kastenwagen/van → camper; caravan/roulotte/wohnwagen → caravan
- "lingua": "IT" | "EN" | "DE" | "FR" | "NL" | "ES"
- "confidenza": 0.0–1.0. For spam: use 0.9 if clearly commercial/automated. For prenotazione: >0.7 only if name + dates + vehicle type are all present.

Email:
---
{email_text}
---
"""


# ---------------------------------------------------------------------------
# Main parse entry point
# ---------------------------------------------------------------------------
def parse_email(from_addr: str, subject: str, body: str, settings: dict) -> dict:
    """Call Ollama to classify and extract fields from an email.

    *settings* must contain ``ollama_url`` and ``ollama_model``.
    Returns a dict with tipo/nome/cognome/telefono/dates/adulti/bambini/
    posto_per/lingua/confidenza.  On any failure the fallback dict is returned.
    """
    ollama_url = settings.get("ollama_url", "http://localhost:11434")
    model = settings.get("ollama_model", "phi3:mini")
    prompt = _build_parse_prompt(from_addr, subject, body)

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 512,
                },
            },
            timeout=180,
        )
        response.raise_for_status()

        raw = response.json().get("response", "{}")
        parsed = json.loads(raw)

        # Coerce fields through guards
        result = {
            "tipo": _str_or_none(parsed.get("tipo")) or "contatto",
            "nome": _str_or_none(parsed.get("nome")),
            "cognome": _str_or_none(parsed.get("cognome")),
            "telefono": _str_or_none(parsed.get("telefono")),
            "data_arrivo": _str_or_none(parsed.get("data_arrivo")),
            "data_partenza": _str_or_none(parsed.get("data_partenza")),
            "adulti": _int_or_none(parsed.get("adulti")),
            "bambini": _int_or_none(parsed.get("bambini")),
            "posto_per": _str_or_none(parsed.get("posto_per")),
            "lingua": _str_or_none(parsed.get("lingua")) or "IT",
            "confidenza": _float_or_none(parsed.get("confidenza")) or 0.0,
        }

        logger.info(
            "Smart parser OK — tipo=%s confidenza=%s",
            result["tipo"],
            result["confidenza"],
        )
        return result

    except requests.exceptions.ConnectionError:
        logger.error("Ollama non raggiungibile — avviare con: ollama serve")
        return _fallback()
    except requests.exceptions.Timeout:
        logger.error("Timeout Ollama — modello troppo lento per questo hardware")
        return _fallback()
    except json.JSONDecodeError as e:
        logger.error("LLM non ha restituito JSON valido: %s", e)
        return _fallback()
    except Exception as e:
        logger.error("Errore smart parser: %s", e)
        return _fallback()


# ---------------------------------------------------------------------------
# Translation helper
# ---------------------------------------------------------------------------
_TRANSLATION_PROMPT = """Translate the following text to Italian.
Return ONLY the translated text — no explanations, no notes, no original text.
If the text is already in Italian, return it unchanged.

Text:
---
{text}
---
"""


def translate_to_italian(text: str, settings: dict) -> str | None:
    """Translate *text* to Italian via Ollama. Returns None on failure."""
    if not text or not text.strip():
        return None

    ollama_url = settings.get("ollama_url", "http://localhost:11434")
    model = settings.get("ollama_model", "phi3:mini")
    prompt = _TRANSLATION_PROMPT.format(text=text[:4000])

    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 1024},
            },
            timeout=180,
        )
        response.raise_for_status()
        result = response.json().get("response", "").strip()
        return result if result else None
    except Exception as e:
        logger.error("Errore traduzione: %s", e)
        return None


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------
def _fallback() -> dict:
    return {
        "tipo": "contatto",
        "nome": None,
        "cognome": None,
        "telefono": None,
        "data_arrivo": None,
        "data_partenza": None,
        "adulti": None,
        "bambini": None,
        "posto_per": None,
        "lingua": "IT",
        "confidenza": 0.0,
    }
