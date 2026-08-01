"""
Dashboard HTML kaynagi (v4 - neon terminal).

Onceki surumde HTML bu dosyanin icinde dev bir string olarak duruyordu.
Artik yaninda duran dashboard.html dosyasindan okunuyor: tasarim guncellemesi
Python'a dokunmadan tek dosya degistirilerek yapilir.

Sozlesme (app/server.py bunu bekler):
  - HTML icinde <!--TAPE--> yer tutucusu bulunur; server durum bandini oraya basar.
  - HTML </body> ile biter; server #server-diag JSON'unu oraya enjekte eder.
  - On yuz su uclardan beslenir:
      /live        20 sn   acik sinyaller + canli fiyat + kural tabanli oneri
      /performance  5 dk   stats() + benchmark  -> Bot Karnesi
      /signals      5 dk   recent_signals(300)  -> kumulatif R egrisi, guven (H/M/L)
      /candles      talep uzerine (sembol secilince) -> mum grafigi
      /news         5 dk   haber akisi
      /diag         5 dk   rejim, son tarama, gap nobeti, log sayaclari
    Uc erisilemezse ekran ORNEK VERI bandiyla acilir; uretimde bu band gorunmemelidir.
"""
from pathlib import Path

DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
