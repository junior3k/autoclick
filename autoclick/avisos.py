# pyright: basic
"""Avisos externos (webhook do Discord/URL ou Telegram). Só biblioteca padrão, para a janela
poder testar o envio sem carregar numpy/opencv."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional


def enviar_webhook_sync(titulo: str, texto: str, url: Optional[str] = None) -> tuple[bool, str]:
    """Envia um aviso. Devolve (ok, mensagem). Discord/URL: POST JSON; telegram:TOKEN@CHAT."""
    url = (url if url is not None else os.environ.get("AUTOCLICK_WEBHOOK", "")).strip()
    if not url:
        return False, "nenhum webhook configurado"
    msg = f"{titulo}\n{texto}"
    try:
        if url.lower().startswith("telegram:"):
            resto = url[len("telegram:"):]
            token, _, chat = resto.partition("@")
            if not token or not chat:
                return False, "formato do Telegram: telegram:TOKEN@CHAT_ID"
            api = f"https://api.telegram.org/bot{token}/sendMessage"
            corpo = json.dumps({"chat_id": chat, "text": msg}).encode("utf-8")
        elif url.lower().startswith(("http://", "https://")):
            api = url
            corpo = json.dumps({"content": msg[:1900], "text": msg}).encode("utf-8")
        else:
            return False, "use uma URL http(s) ou telegram:TOKEN@CHAT_ID"
        req = urllib.request.Request(api, data=corpo, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "autoclick"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return (200 <= r.status < 300), f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # rede fora do ar não pode derrubar o programa
        return False, f"{type(e).__name__}: {e}"
