# Kullanıcı El Kitabı — üretim hattı

`kullanici-el-kitabi.md` — okunabilir kaynak metin (repo içinde diff'lenebilir).
`kullanici-el-kitabi.pdf` — nihai teslim edilen belge (dashboard'dan da bu dosyaya bağlanılır: `app/static/kullanici-el-kitabi.pdf`, aynı içerik).

## Yeniden üretmek için

```bash
pip install matplotlib --break-system-packages
python3 make_charts.py          # charts/*.png üretir (9 grafik)
node generate_docx.js           # kullanici-el-kitabi.docx üretir
python /mnt/skills/public/docx/scripts/office/soffice.py \
  --headless --convert-to pdf kullanici-el-kitabi.docx
cp kullanici-el-kitabi.pdf ../../app/static/kullanici-el-kitabi.pdf
```

İçerik güncellenirse (yeni bölüm, yeni parametre değeri vb.) hem `.md`
hem `generate_docx.js` içindeki ilgili bölüm elle senkron tutulmalı —
otomatik md->docx dönüştürme kullanılmadı (tablo/grafik/TOC üzerinde tam
kontrol için elle yazıldı).
