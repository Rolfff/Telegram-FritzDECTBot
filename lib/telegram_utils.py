#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Zentrale Telegram-Utility-Funktionen für den FritzDECTBot
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

async def retry_telegram_call(func, *args, max_retries=10, base_delay=1, **kwargs):
    """
    Führt einen Telegram-Aufruf mit Retry-Logik aus.
    Bei NetworkError wird der Aufruf bis zu max_retries Mal wiederholt.
    
    Args:
        func: Die async-Funktion, die ausgeführt werden soll
        *args: Positionale Argumente für die Funktion
        max_retries: Maximale Anzahl an Wiederholungsversuchen (Standard: 10)
        base_delay: Basis-Verzögerung in Sekunden für exponential backoff (Standard: 1)
        **kwargs: Keyword-Argumente für die Funktion
    
    Returns:
        Das Ergebnis der Funktion
    
    Raises:
        Exception: Die ursprüngliche Exception, wenn alle Retrys fehlschlagen
    """
    import telegram.error
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except telegram.error.NetworkError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Telegram NetworkError (Versuch {attempt + 1}/{max_retries}): {str(e)}. Wiederhole in {delay:.1f}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Telegram NetworkError: Alle {max_retries} Versuche fehlgeschlagen. {str(e)}")
                raise
        except Exception as e:
            # Andere Fehler nicht retryen
            raise
