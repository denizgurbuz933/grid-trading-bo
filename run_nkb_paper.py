# -*- coding: utf-8 -*-
"""Yerel / bağımsız NKB Altın+Nasdaq paper paneli.

  NKB_PAPER_OPEN=1 python run_nkb_paper.py

Varsayılan: http://127.0.0.1:5055/z/piyasa/
Asistall entegrasyonu: web_panel.py içinde nkb_paper blueprint kaydı (VPS).
"""
from __future__ import annotations

import os

from flask import Flask

# Standalone: secret session gerekmesin
os.environ.setdefault("NKB_PAPER_OPEN", "1")

from nkb_paper.web_panel import bp  # noqa: E402

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "nkb-paper-local-dev")
app.register_blueprint(bp)


@app.route("/")
def root():
    from flask import redirect

    return redirect("/z/piyasa/")


@app.route("/health")
def health():
    return {"ok": True, "service": "nkb-paper"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5055"))
    print(f"[NKB PAPER] http://127.0.0.1:{port}/z/piyasa/  (Paper / Demo)")
    app.run(host="0.0.0.0", port=port, debug=False)
