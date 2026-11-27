# NKB Asistall — Altın + Nasdaq Paper Panel

Mock UI: XAU/USD + NASDAQ, mum grafik, Al/Sat paper ticket, açık pozisyonlar, cüzdan.

## Canlı fiyat

- **Kaynak:** Yahoo Finance chart API (anahtar gerekmez)
- XAU/USD → `GC=F` (COMEX altın vadeli)
- NASDAQ → `^IXIC` (Nasdaq Composite)
- Opsiyonel anahtarlar: yok (Twelve Data / Finnhub bağlanmadı)

## Çalıştırma (yerel)

```bash
NKB_PAPER_OPEN=1 python run_nkb_paper.py
# http://127.0.0.1:5055/z/piyasa/
```

## Asistall VPS entegrasyonu

`web_panel.py` içinde `coin_optimizer` kaydının yanına:

```python
try:
    from nkb_paper.web_panel import bp as _nkb_paper_bp
    app.register_blueprint(_nkb_paper_bp)
    print("[NKB PAPER] Altın/Nasdaq paper panel -> /z/piyasa")
except Exception as _nkb_err:
    print(f"[NKB PAPER] Yuklenemedi (opsiyonel): {_nkb_err}")
```

URL (secret şifre `PANEL_PASSWORD_SECRET` ile giriş sonrası): `https://asistall.tr/z/piyasa/`

Mevcut `/z` kripto paneli ve `PANEL_PASSWORD` bozulmaz.
