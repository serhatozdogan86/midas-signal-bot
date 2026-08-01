// Midas Sinyal Botu - Kullanici El Kitabi -> DOCX
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  BorderStyle, PageBreak, TableOfContents,
  LevelFormat, VerticalAlign, PageNumber,
  Footer, Header, PositionalTab, PositionalTabAlignment, PositionalTabLeader, TabStopType, TabStopPosition
} = require('docx');

const CH = '/home/claude/handbook/charts/';
const GOLD = 'B8860B';
const INK = '1A1A2E';
const GRAY = '555555';

function h1(text) {
  return new Paragraph({
    text, heading: HeadingLevel.HEADING_1,
    spacing: { before: 480, after: 240 },
    border: { bottom: { color: GOLD, space: 4, style: BorderStyle.SINGLE, size: 8 } },
  });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 360, after: 180 } });
}
function h3(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_3, spacing: { before: 260, after: 140 } });
}
function p(text) {
  return new Paragraph({
    spacing: { after: 200, line: 300 },
    children: [new TextRun({ text })],
  });
}
function pRich(runs) {
  return new Paragraph({ spacing: { after: 200, line: 300 }, children: runs });
}
function bold(t) { return new TextRun({ text: t, bold: true }); }
function reg(t) { return new TextRun({ text: t }); }

function bullet(text, level) {
  return new Paragraph({
    text, bullet: { level: level || 0 }, spacing: { after: 120, line: 290 },
  });
}
function bulletRich(runs, level) {
  return new Paragraph({ children: runs, bullet: { level: level || 0 }, spacing: { after: 120, line: 290 } });
}

function quoteBox(text) {
  return new Paragraph({
    spacing: { before: 160, after: 220, line: 300 },
    indent: { left: 400, right: 400 },
    border: {
      left: { color: GOLD, space: 8, style: BorderStyle.SINGLE, size: 18 },
    },
    shading: { type: ShadingType.CLEAR, fill: 'FBF3DA' },
    children: [new TextRun({ text, italics: true })],
  });
}

function img(name, w, h, caption) {
  const data = fs.readFileSync(CH + name);
  const parts = [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 80 },
      children: [new ImageRun({ data, transformation: { width: w, height: h }, type: 'png' })],
    }),
  ];
  if (caption) {
    parts.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 260 },
      children: [new TextRun({ text: caption, italics: true, size: 19, color: GRAY })],
    }));
  }
  return parts;
}

function cell(text, opts) {
  opts = opts || {};
  return new TableCell({
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { type: ShadingType.CLEAR, fill: INK } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 100, bottom: 100, left: 120, right: 120 },
    children: [new Paragraph({
      children: [new TextRun({ text, bold: !!opts.header || !!opts.bold, color: opts.header ? 'FFFFFF' : undefined, size: opts.size || 21 })],
    })],
  });
}
function table(headers, rows, widths) {
  const headerRow = new TableRow({
    children: headers.map((hd, i) => cell(hd, { header: true, width: widths[i] })),
    tableHeader: true,
  });
  const bodyRows = rows.map(r => new TableRow({
    children: r.map((c, i) => cell(c, { width: widths[i] })),
  }));
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    rows: [headerRow, ...bodyRows],
  });
}
function pageBreak() { return new Paragraph({ children: [new PageBreak()] }); }


function tocLine(title, page, big) {
  return new Paragraph({
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
    spacing: { after: big ? 60 : 160, before: big ? 220 : 0 },
    children: [
      new TextRun({ text: title, bold: !!big, size: big ? 24 : 22 }),
      new PositionalTab({ alignment: PositionalTabAlignment.RIGHT, leader: PositionalTabLeader.DOT, style: 'aTabStopWithLeader' }),
      new TextRun({ text: String(page), bold: !!big, size: big ? 24 : 22 }),
    ],
  });
}

const children = [];

children.push(
  new Paragraph({ spacing: { before: 2200 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'MİDAS SİNYAL BOTU', bold: true, size: 64, color: INK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 80 },
    children: [new TextRun({ text: 'Kullanıcı El Kitabı', size: 40, color: GOLD, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 1600 },
    children: [new TextRun({ text: 'Strateji · Mekanizma · Karar Süreci', size: 26, italics: true, color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: 'Sıfırdan anlatım — teknik terimler açıklanır,', size: 22, color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 1400 },
    children: [new TextRun({ text: 'teori örnek grafiklerle desteklenir.', size: 22, color: GRAY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: 'Serhat Özdoğan', size: 22, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 2000 },
    children: [new TextRun({ text: 'Ağustos 2026', size: 20, color: GRAY })] }),
  pageBreak(),
);

children.push(
  h1('İçindekiler'),
  tocLine('Önsöz', 3, true),
  tocLine('Bölüm 1 — Botun Felsefesi: Ne Yapar, Ne Yapmaz', 4, true),
  tocLine('Bölüm 2 — Temel Kavramlar Sözlüğü', 5, true),
  tocLine('Bölüm 3 — Botun Mimarisi: Günlük Ritim', 9, true),
  tocLine('Bölüm 4 — Karar Hattı: Bir Sinyal Nasıl Doğar', 11, true),
  tocLine('Bölüm 5 — SHORT (Kısa) Pozisyonlar: Neden Daha Sıkı Kurallar?', 17, true),
  tocLine('Bölüm 6 — Portföy Risk Yönetimi: "Isı Motoru"', 18, true),
  tocLine('Bölüm 7 — Maliyet Modeli ve "Net-R"', 20, true),
  tocLine('Bölüm 8 — Gölge Mod ve Gerçek Paraya Geçiş Kriteri', 21, true),
  tocLine('Bölüm 9 — Dashboard Kullanım Kılavuzu', 23, true),
  tocLine('Bölüm 10 — Sık Sorulan Sorular', 25, true),
  tocLine('Bölüm 11 — Sözlük (A\'dan Z\'ye)', 26, true),
  tocLine('Sorumluluk Reddi', 27, true),
  pageBreak(),
);

children.push(
  h1('Önsöz'),
  p('Bu kitap, Midas Sinyal Botu\'nun ne yaptığını, nasıl çalıştığını ve bir kararı neden aldığını en baştan anlatmak için yazıldı. Borsa, hisse senedi veya yazılım konusunda hiç bilgisi olmayan biri de bu kitabı baştan sona okuyup botun ekranında gördüğü her rakamın, her rengin ve her kelimenin ne anlama geldiğini öğrenebilmeli.'),
  p('İki katmanda ilerliyoruz:'),
  bullet('Teori — bir kavramın ne olduğu, neden var olduğu, hangi soruna çözüm ürettiği.'),
  bullet('Pratik — o kavramın botun kodunda tam olarak nasıl uygulandığı, hangi sayının, hangi eşiğin kullanıldığı.'),
  p('Kitap boyunca gerçek benzeri örnek grafikler kullanılır. Bunlar botun canlı ürettiği sinyaller değil, botun mantığını görselleştirmek için hazırlanmış öğretici örneklerdir.'),
  quoteBox('Önemli uyarı: Bu bot bir karar destek aracıdır. Hiçbir emir göndermez, hiçbir hisse almaz veya satmaz. Ürettiği her şey bir öneridir; nihai kararı ve emri her zaman sen, Midas uygulaması üzerinden elle verirsin. Bu kitaptaki hiçbir bilgi yatırım tavsiyesi değildir.'),
  pageBreak(),
);

children.push(
  h1('Bölüm 1 — Botun Felsefesi: Ne Yapar, Ne Yapmaz'),
  h2('1.1 Bot bir "sinyal fabrikası"dır, bir "otomatik tüccar" değildir'),
  p('Piyasada iki tür bot vardır:'),
  bullet('Otomatik işlem botları — kendi başlarına emir gönderir, parayı yönetir, senin hiçbir onayın olmadan alım-satım yapar.'),
  bullet('Karar destek botları — piyasayı sürekli tarar, kurallarına uyan fırsatları tespit eder, sana "şu hisse, şu seviyeden, şu risk ile ilginç görünüyor" der ve orada durur.'),
  pRich([bold('Midas Sinyal Botu ikinci gruptadır.'), reg(' Bunun iki nedeni var:')]),
  bulletRich([bold('Güvenlik: '), reg('Bir yazılım hatası, bir veri kesintisi veya beklenmedik bir piyasa hareketi otomatik bir botun gerçek parayla yanlış karar vermesine yol açabilir. Karar destek modelinde en kötü ihtimalle kaçırılan bir fırsat olur; otomatik modelde en kötü ihtimalle gerçekleşmiş bir zarar olur.')]),
  bulletRich([bold('Öğrenme: '), reg('Sen her sinyali gördüğünde botun mantığını da görürsün — neden bu hisse, neden bu seviye, neden bu risk. Zamanla botun güçlü ve zayıf yönlerini sen de öğrenirsin.')]),
  h2('1.2 "Gölge Mod" nedir?'),
  p('Bot şu anda gölge modda çalışıyor. Bu, botun ürettiği her sinyalin gerçek parayla değil, hayali (kağıt üzerinde) bir hesapla takip edildiği anlamına gelir. Bot "şu fiyattan alırdım" der, bir defter tutar, o hayali işlemin sonucunu (kazandı mı kaybetti mi, kaç R kazandı/kaybetti) kayda geçirir — ama gerçekte hiçbir emir gitmez.'),
  p('Bunun nedeni basit: bir stratejinin gerçekten işe yarayıp yaramadığını, gerçek para riske atmadan önce anlamak. Bu kitabın ilerleyen bölümlerinde ("Gölge Mod ve Gerçek Paraya Geçiş Kriteri") bu sürecin nasıl işlediğini ve gerçek paraya ne zaman geçileceğine nasıl karar verildiğini detaylıca anlatacağız.'),
  h2('1.3 Botun kapsamı: ABD hisseleri, kısa vadeli "swing" işlemler'),
  p('Bot, Midas platformunda işlem gören ABD hisseleri için sinyal üretir. Hedeflediği işlem süresi 1-3 gün — yani "gün içi" (aynı gün alıp satmak) değil, "uzun vadeli yatırım" (yıllarca tutmak) da değil, ortası: swing trade (salınım işlemi). Hedefe ulaşılırsa aynı gün çıkılabilir; ulaşılamazsa en geç 3-5 işlem gününde pozisyon kapatılır ("zaman-stopu", ilerleyen bölümlerde anlatılacak).'),
  pageBreak(),
);

children.push(
  h1('Bölüm 2 — Temel Kavramlar Sözlüğü'),
  p('Bu bölümde, kitabın geri kalanında sürekli karşına çıkacak temel terimleri, en basit tanımlarından başlayarak açıklıyoruz. İlk okumada bazıları soyut gelebilir — merak etme, Bölüm 4\'te (Karar Hattı) hepsini gerçek örneklerle tekrar göreceksin.'),

  h3('Mum Grafiği (Candlestick) ve OHLC'),
  p('Bir hissenin fiyatı sürekli değişir. Bu değişimi belirli bir zaman aralığında (örneğin 1 saat veya 1 gün) özetlemenin en yaygın yolu mum grafiğidir. Her "mum" dört sayıyı taşır:'),
  bulletRich([bold('O (Open / Açılış): '), reg('O aralığın başındaki fiyat')]),
  bulletRich([bold('H (High / En Yüksek): '), reg('O aralıkta görülen en yüksek fiyat')]),
  bulletRich([bold('L (Low / En Düşük): '), reg('O aralıkta görülen en düşük fiyat')]),
  bulletRich([bold('C (Close / Kapanış): '), reg('O aralığın sonundaki fiyat')]),
  p('Kapanış açılıştan yüksekse mum yeşil (fiyat yükseldi), düşükse kırmızı (fiyat düştü) çizilir. Mumun ince çizgisi (fitil) o aralıktaki en yüksek ve en düşük noktaları gösterir.'),

  h3('Zaman Dilimi (Timeframe)'),
  p('Botun kullandığı üç farklı "çözünürlük" vardır:'),
  table(
    ['Kısaltma', 'Anlamı', 'Botta ne için kullanılır'],
    [
      ['1D (Günlük)', 'Her mum bir işlem gününü temsil eder', 'Piyasa rejimi ve hissenin genel trendi'],
      ['1H (Saatlik)', 'Her mum bir saati temsil eder', 'Giriş yapısı (setup), hassas seviye tespiti'],
      ['Gerçek zamanlı', 'Anlık fiyat', 'Giriş tetiğinin tam o anda kırılıp kırılmadığı'],
    ],
    [2200, 4200, 3600],
  ),
  new Paragraph({ spacing: { after: 240 } }),

  h3('LONG ve SHORT'),
  bulletRich([bold('LONG (uzun): '), reg('"Düşük fiyattan al, yüksek fiyattan sat" — fiyatın yükseleceğini düşünerek alım yapmak. Geleneksel, herkesin bildiği yön.')]),
  bulletRich([bold('SHORT (kısa): '), reg('Fiyatın düşeceğini düşünerek, önce (ödünç alınan hisseyi) satıp sonra daha düşük fiyattan geri almak. Ters yönlü bahis.')]),

  h3('Destek ve Direnç'),
  bulletRich([bold('Direnç: '), reg('Fiyatın yukarı çıkarken defalarca "tosladığı", geçmekte zorlandığı seviye — sanki görünmez bir tavan gibi.')]),
  bulletRich([bold('Destek: '), reg('Fiyatın aşağı inerken defalarca "sekip" durduğu, tutunduğu seviye — görünmez bir zemin gibi.')]),

  h3('Hareketli Ortalama (Moving Average / MA)'),
  p('Son N günün/mumun kapanış fiyatlarının ortalaması. "50 günlük ortalama" son 50 günün ortalama kapanışıdır. Fiyattaki günlük gürültüyü yumuşatıp asıl yönü (trendi) görmeyi sağlar. Bot en çok 50 günlük ve 200 günlük ortalamaları kullanır.'),

  h3('Trend'),
  p('Fiyatın genel gidişat yönü. Basitçe:'),
  bulletRich([bold('Yükselen trend: '), reg('fiyat, kısa vadeli ortalama > uzun vadeli ortalamanın üstünde, her yeni tepe eskisinden yüksek (HH = Higher High), her yeni dip eskisinden yüksek (HL = Higher Low).')]),
  bulletRich([bold('Düşen trend: '), reg('tam tersi — her yeni tepe eskisinden alçak (LH = Lower High), her yeni dip eskisinden alçak (LL = Lower Low).')]),

  h3('Stop-Loss (Zarar-Durdur) ve Take-Profit (Kâr-Al)'),
  bulletRich([bold('Stop-Loss (Stop): '), reg('"Buraya gelirse yanıldığımı kabul edip çıkarım" dediğin fiyat seviyesi. Kaybı sınırlamak için var.')]),
  bulletRich([bold('Take-Profit (TP): '), reg('"Buraya gelirse kârımı realize ederim" dediğin fiyat seviyesi. Bot iki hedef kullanır: TP1 (ilk, daha yakın hedef) ve TP2 (ikinci, daha uzak hedef).')]),

  h3('Giriş Bölgesi (Entry Zone)'),
  p('Bot tek bir fiyat değil, bir aralık verir (örneğin $17,82–$18,05). Çünkü gerçek piyasada "tam olarak şu kuruştan al" demek gerçekçi değildir; makul bir bant içinde girmek yeterlidir.'),

  h3('R — Riskin Evrensel Ölçü Birimi'),
  p('Bu, botun tüm muhasebesinin temelini oluşturan en önemli kavramdır.'),
  pRich([bold('Tanım: '), reg('Bir işlemde riske attığın miktar "1R" olarak adlandırılır. Eğer giriş $100, stop $96 ise, riskin $4\'tür — bu senin "1R"ndir. İşlem $104\'e (yani girişin 1R üstüne) giderse +1R kazandın; $92\'ye (girişin 2R altına, teorik olarak) giderse −2R kaybettin demektir. Stop\'a düşersen tam olarak −1R kaybedersin (çünkü stop, tanımı gereği 1R uzaklıktadır).')]),
  pRich([bold('Neden R kullanılır, dolar değil? '), reg('Çünkü hesabın büyüklüğünden bağımsızdır. 1.000 dolarlık bir hesapta da, 100.000 dolarlık bir hesapta da "+2R\'lik bir işlem yaptım" demek aynı oransal başarıyı ifade eder. Bu sayede botun performansı, kimin ne kadar parayla işlem yaptığından bağımsız, evrensel bir dille ölçülebilir.')]),
  p('Aşağıdaki grafik bu mantığı özetliyor:'),
  ...img('04_r_multiple.png', 480, 320, 'Grafik 2.1 — R Nedir? Riskin evrensel ölçü birimi.'),

  h3('RR (Risk/Ödül) Oranı'),
  p('"Ne kadar risk alıp ne kadar ödül hedefliyorum?" sorusunun cevabı. RR = 2,5 demek, riske attığın her 1 birime karşılık 2,5 birim kazanç hedeflediğin anlamına gelir. Bot, düşük RR\'li (riski ödülüne göre çok yüksek) sinyalleri otomatik eler.'),

  h3('ATR (Average True Range / Ortalama Gerçek Aralık)'),
  p('Bir hissenin günlük olarak ortalama ne kadar oynadığının ölçüsü. Volatilitesi yüksek bir hissenin ATR\'si büyük, "sakin" bir hissenin ATR\'si küçüktür. Bot, stop ve hedef mesafelerini sabit bir yüzde yerine hissenin kendi ATR\'sine göre ayarlar — volatil bir hisseye dar bir stop koymak anlamsızdır, çünkü normal günlük oynaklığıyla bile stop\'a çarpar.'),

  h3('RSI (Relative Strength Index / Göreceli Güç Endeksi)'),
  p('0-100 arası bir sayı; hissenin kısa vadede "aşırı alınmış" mı yoksa "aşırı satılmış" mı olduğunu gösterir. Bot, RSI\'ın çok kısa periyodunu (RSI(3)) kullanarak bir geri çekilmenin "yeterince satılmış" olup olmadığını ölçer.'),

  h3('Relative Strength (RS) — Göreceli Güç Sıralaması'),
  p('RSI ile karıştırılmamalı. Bu, bir hissenin kendi sektörüne veya piyasaya göre ne kadar güçlü performans gösterdiğinin sıralamasıdır. "Piyasa %2 düşerken bu hisse sadece %0,5 düştü" demek, o hissenin göreceli gücünün yüksek olduğunu gösterir — bu da bir güven artırıcı sinyaldir.'),

  h3('Rejim (Regime): BULL / BEAR / NEUTRAL'),
  p('Piyasanın (SPY ve QQQ endekslerinin) genel gidişatı. Bot bu üç durumdan birini tespit eder ve LONG/SHORT üretimini buna göre sınırlar.'),

  h3('Gap (Fiyat Boşluğu)'),
  p('Bir hissenin bir önceki kapanışı ile bugünkü açılışı arasında oluşan ani sıçrama. Örneğin hisse $50\'de kapandı ama ertesi sabah $47\'de açıldıysa, aradaki $3\'lük fark gap\'tır (genellikle gece çıkan bir haberden kaynaklanır). Gap\'ler tehlikelidir çünkü stop-loss\'un "kesin çalışacağı" varsayımını bozar — fiyat stop seviyeni "atlayarak" geçebilir.'),

  h3('Likidite ve Dolar Hacmi'),
  p('Bir hissenin ne kadar kolay alınıp satılabildiğinin ölçüsü. Dolar hacmi = günlük işlem gören hisse adedi × fiyat. Bot, çok düşük likiditeli (günde çok az işlem gören) hisseleri evreninden baştan eler — çünkü böyle hisselerde makul bir fiyattan alım/satım yapmak zordur.'),

  h3('Confidence (Güven): H / M / L'),
  p('Her sinyalin yanında bir güven etiketi bulunur:'),
  bulletRich([bold('H (High / Yüksek): '), reg('Birden fazla olumlu faktör aynı anda hizalanmış')]),
  bulletRich([bold('M (Medium / Orta): '), reg('Standart, temel şartları sağlayan sinyal')]),
  bulletRich([bold('L (Low / Düşük): '), reg('Şartları sağlıyor ama destekleyici faktörler zayıf')]),

  h3('Cluster (Küme) ve Kohort'),
  bulletRich([bold('Küme (cluster): '), reg('Aynı gün, aynı yönde (örneğin hepsi LONG) doğan sinyaller bir küme sayılır. Neden önemli? Çünkü bunlar istatistiksel olarak bağımsız değildir — piyasa o gün genel olarak yükseldiği için hepsi birden sinyal vermiş olabilir. Bir küme kazanırsa hep birlikte kazanır, kaybederse hep birlikte kaybeder.')]),
  bulletRich([bold('Kohort: '), reg('Belirli bir kural setiyle (motor sürümüyle) üretilmiş sinyallerin tamamı. Motorun kuralları değiştiğinde yeni bir kohort başlar — eski kohortun performansı yeni kohortun karnesine karıştırılmaz.')]),

  h3('Net-R ve Komisyon Modeli'),
  p('Bir işlemin kağıt üzerindeki R\'si ile komisyon düşüldükten sonraki gerçek R\'si farklıdır. Bot bu farkı ayrıca hesaplar (Bölüm 7\'de detaylı).'),
  pageBreak(),
);

children.push(
  h1('Bölüm 3 — Botun Mimarisi: Günlük Ritim'),
  p('Bot, her işlem günü aynı ritmi izler. Bu ritmi anlamak, dashboard\'da gördüğün "Son tarama", "Gap Nöbeti" gibi ifadelerin ne anlama geldiğini çözer.'),
  ...img('08_schedule.png', 560, 183, 'Grafik 3.1 — Botun günlük ritmi (Türkiye saati).'),

  h2('3.1 15:45 — Hazırlık'),
  p('Seans açılmadan önce bot üç şey yapar:'),
  bullet('Evreni günceller: Midas\'ta işlem gören ABD hisselerinin güncel listesini çeker, çok düşük fiyatlı veya çok düşük hacimli olanları eler (yaklaşık 1.600 hisseden ~300\'e iner).'),
  bullet('Günlük analiz: Kalan hisselerin trend ve rejim durumunu hesaplar.'),
  bullet('İlk izleme listesi: En umut verici 20-40 hisseyi bir "izleme listesi"ne alır.'),

  h2('3.2 16:00-16:30 — Gap Nöbeti'),
  p('Seans açılmadan hemen önceki bu pencerede bot, açık pozisyonların gece bir gap ile stop\'unu (veya hedefini) geçip geçmediğini kontrol eder. Bu, gece çıkan bir haberin sabah pozisyonuna nasıl yansıdığını erkenden görmeni sağlar.'),

  h2('3.3 16:30-23:00 (TR saati) — Seans'),
  p('ABD borsa seansı boyunca bot iki hızda tarama yapar:'),
  bulletRich([bold('Kaba Tarama (15 dakikada bir): '), reg('Tüm evreni (~300 hisse) yeniden tarar. Yeni oluşan fırsatları yakalar, izleme listesini tazeler.')]),
  bulletRich([bold('İnce Tarama (~1 dakikada bir): '), reg('Sadece izleme listesindeki hisseleri, gerçek zamanlı fiyatla kontrol eder. Bir hissenin giriş seviyesi tam o an kırılırsa, sinyal anında üretilir ve Telegram\'a düşer.')]),
  p('Bu iki kademeli yapının nedeni basit: 300 hisseyi saniyede bir kontrol etmek hem gereksiz hem de veri kaynaklarının (API) limitlerini zorlar. Ama asıl fırsatların olduğu dar bir listeyi sık sık kontrol etmek hem mümkün hem de anlamlıdır.'),

  h2('3.4 23:15 — Gün Sonu Raporu'),
  p('Seans kapandıktan sonra bot bir özet çıkarır: o gün açılan/kapanan sinyaller, güncel karne, SPY karşılaştırması, ertesi gün izlenecekler.'),

  h2('3.5 Pazar 21:00\'den sonra — Haftalık Rapor'),
  p('Haftanın toplam performansı, en iyi/en kötü işlem, gerçek paraya geçiş sayacındaki ilerleme.'),
  pageBreak(),
);

children.push(
  h1('Bölüm 4 — Karar Hattı: Bir Sinyal Nasıl Doğar'),
  p('Bu, kitabın kalbidir. Bot bir hisseyi değerlendirirken 9 basamaklı bir elemeli sistem kullanır. Her basamak bir soru sorar; cevap "hayır" ise hisse elenir ve bir sonraki basamağa hiç geçilmez (buna kısa devre denir — gereksiz hesaplama yapılmaz).'),
  ...img('01_pipeline.png', 400, 539, 'Grafik 4.1 — Karar hattı: 9 basamaklı elemeli sistem.'),

  h2('4.1 Basamak 1 — DATA (Veri Yeterliliği)'),
  pRich([bold('Soru: '), reg('Bu hisse için yeterli geçmiş mum verisi var mı?')]),
  p('Yeni halka arz olmuş veya veri sağlayıcısında eksik kaydı olan hisseler burada elenir. Analiz yapabilmek için önce analiz edilecek yeterli veri lazım — en temel, en can alıcı kontrol.'),

  h2('4.2 Basamak 2 — MARKET_REGIME (Piyasa Rejimi)'),
  pRich([bold('Soru: '), reg('Genel piyasa şu an yükseliş mi, düşüş mü, yoksa kararsız mı?')]),
  p('Bot bunu SPY (S&P 500 endeks fonu) ve QQQ (Nasdaq 100 endeks fonu) üzerinden, 200 günlük ortalama ile ölçer:'),
  bullet('Fiyat, yükselen bir 200 günlük ortalamanın üstündeyse → BULL (yükseliş rejimi)'),
  bullet('Fiyat, düşen bir 200 günlük ortalamanın altındaysa → BEAR (düşüş rejimi)'),
  bullet('Diğer tüm durumlar → NEUTRAL (kararsız)'),
  pRich([bold('Neden önemli? '), reg('Çünkü tek tek hisselerin çoğu, genel piyasa yönüne göre hareket eder. BULL rejiminde sadece LONG sinyalleri üretilir; BEAR rejiminde sadece SHORT. NEUTRAL\'da her iki yön de üretilebilir ama eşikler sıkılaşır (daha seçici davranılır).')]),
  pRich([bold('Histerezis — piyasa "testere" yapmasın diye fren: '), reg('Ham bir 200 günlük ortalama kontrolü, fiyat tam o çizginin etrafında dolaştığında rejimi gün be gün BULL-NEUTRAL-BULL diye zıplatabilir. Bot bunu önlemek için bir ±%0,5\'lik "gürültü bandı" kullanır ve rejim değişimi için son 2 kapanışın da bu bandın tamamen dışında olmasını ister.')]),
  ...img('05_regime.png', 560, 305, 'Grafik 4.2 — Piyasa rejimi tespiti: 200 günlük ortalama + histerezis bandı.'),

  h2('4.3 Basamak 3 — TREND (Hissenin Kendi Trendi)'),
  pRich([bold('Soru: '), reg('Bu hisse kendi başına net bir trend içinde mi?')]),
  pRich([bold('LONG için: '), reg('Fiyat > 50 günlük ortalama > 200 günlük ortalama (ortalamalar doğru sırada) + HH/HL yapısı (yükselen tepeler ve dipler).')]),
  pRich([bold('SHORT için: '), reg('Tam tersi — fiyat < 50 günlük ortalama < 200 günlük ortalama + LH/LL yapısı, ayrıca hissenin göreceli gücünün de zayıf olması istenir.')]),
  p('Piyasa geneli iyi olsa bile (BULL rejimi), tek tek her hisse kendi başına yükseliş trendinde olmayabilir — bu basamak o farkı ayıklar.'),

  h2('4.4 Basamak 4 — EARNINGS (Bilanço Takvimi)'),
  pRich([bold('Soru: '), reg('Bu hissenin bilanço açıklaması yakın mı?')]),
  p('Şirketler çeyreklik olarak finansal sonuçlarını (bilançosunu) açıklar. Bu açıklamalar fiyatta büyük, öngörülemez sıçramalara (gap\'lere) yol açabilir — bilanço iyi gelirse fiyat sabah %10 yukarı açılabilir, kötü gelirse %10 aşağı. Bu, teknik analizin öngöremeyeceği bir risktir.'),
  p('Bot, bilanço tarihine ±2 işlem günü kala o hisse için sinyal üretmeyi durdurur. Amaç, teknik bir kurulumun bir gecede haber riskiyle boşa çıkmasını engellemek.'),

  h2('4.5 Basamak 5 — SETUP (Giriş Yapısı) — İki Model'),
  pRich([bold('Soru: '), reg('Şu an, saatlik grafikte, gerçekten "girilebilir" bir yapı var mı?')]),
  p('Bot iki farklı giriş modeli tanır:'),

  h3('Model A: Trend İçi Geri Çekilme ("Pullback")'),
  p('Hisse zaten net bir yükseliş trendindeyken, kısa süreliğine yükselen 20 saatlik ortalamaya doğru geri çekilir. Bu geri çekilme sırasında RSI(3) "aşırı satım" bölgesine girer ve ardından bir dönüş mumu (fiyatın tekrar yukarı dönmeye başladığını gösteren mum) oluşursa, bu bir giriş fırsatı sayılır.'),
  quoteBox('Mantık: "Trend hâlâ sağlam, sadece kısa bir soluklanma oldu; ucuza binme fırsatı."'),
  ...img('02_pullback.png', 560, 316, 'Grafik 4.3 — Setup örneği A: Trend içi geri çekilme (pullback).'),

  h3('Model B: Kırılım + Yeniden Test ("Breakout + Retest")'),
  p('Hisse bir süre yatay bir bantta sıkışır (bir direnç seviyesinin altında). Sonra bu direnci hacimle birlikte yukarı kırar. Kırılımın hemen ardından fiyat genellikle o eski direnç seviyesine bir kez daha dokunur (artık destek olmuştur) — işte bu "yeniden test" anı giriş fırsatıdır.'),
  quoteBox('Mantık: "Yeni bir seviyeye geçiş oldu, piyasa bunu onaylıyor mu diye bir kez daha test ediyor; onaylarsa devam eder."'),
  ...img('03_breakout.png', 560, 316, 'Grafik 4.4 — Setup örneği B: Kırılım + yeniden test (breakout + retest).'),

  p('SHORT tarafında bu iki model aynen ayna görüntüsüyle çalışır (düşen ortalamaya geri sıçrama + RSI aşırı alım + dönüş mumu; veya bir destek seviyesinin kırılıp aşağı yönlü yeniden test edilmesi).'),

  h2('4.6 Basamak 6 — VOLUME (Hacim Teyidi)'),
  pRich([bold('Soru: '), reg('Bu hareketin arkasında yeterli işlem hacmi var mı?')]),
  p('Bir kırılım veya dönüş, düşük hacimle (yani az sayıda kişinin katılımıyla) gerçekleşiyorsa güvenilirliği düşüktür — kolayca geri dönebilir. Bot, tetik mumunda göreceli hacmin (o anki hacmin, o hissenin normal ortalama hacmine oranının) belirli bir eşiğin üstünde olmasını arar. NEUTRAL rejiminde bu eşik daha da yükseltilir (daha seçici davranılır).'),

  h2('4.7 Basamak 7 — CONFLUENCE (Güven Puanı — Filtre Değil!)'),
  p('Bu basamak diğerlerinden farklıdır: bir hisseyi elemez, sadece sinyalin güven puanını (H/M/L) belirler. Üç şeye bakar:'),
  bullet('Göreceli güç sıralaması — hisse, sektörüne/piyasaya göre ne kadar güçlü?'),
  bullet('Sektör ETF gücü — hissenin ait olduğu sektör genel olarak güçlü mü?'),
  bullet('52 haftalık zirveye yakınlık — hisse, son bir yılın en yüksek seviyesine yakın mı? (Yakınsa, "önünde satış baskısı yapacak eski yatırımcı" azdır — teknik olarak olumlu sayılır.)'),

  h2('4.8 Basamak 8 — RISK_REWARD (Risk/Ödül Yeterliliği)'),
  pRich([bold('Soru: '), reg('Bu işlemin potansiyel kazancı, riskine ve maliyetine değer mi?')]),
  p('İki ayrı kontrol yapılır:'),
  bullet('RR oranı belirli bir minimum eşiğin üstünde olmalı (yani hedef, riskin yeterince katı olmalı).'),
  bullet('Maliyet filtresi: Hedef mesafesi, Midas\'ın işlem başına sabit 1,50 dolarlık ücretini (gidiş-dönüş toplamda 3 dolar + kayma) anlamlı şekilde aşmalı. Çok küçük bir hareket hedefleniyorsa, kazanç komisyona gider — böyle sinyaller elenir.'),

  h2('4.9 Basamak 9 — SIGNAL (Nihai Çıktı)'),
  p('Tüm basamaklar geçildiyse, bot artık somut bir sinyal üretir. Bu sinyal şunları içerir:'),
  bullet('Giriş bölgesi (bir fiyat aralığı)'),
  bullet('Stop-Loss seviyesi'),
  bullet('TP1 ve TP2 hedefleri'),
  bullet('RR oranı'),
  bullet('Güven etiketi (H/M/L)'),
  bullet('Zaman-stopu tarihi (en geç ne zaman kapanacağı)'),
  bullet('Gap uyarısı (varsa)'),
  p('Bu bilgi paketi Telegram\'a gönderilir ve dashboard\'a işlenir.'),
  pageBreak(),
);

children.push(
  h1('Bölüm 5 — SHORT (Kısa) Pozisyonlar: Neden Daha Sıkı Kurallar?'),
  p('ABD hisse senedi piyasasının yapısal olarak yukarı eğilimli olduğu, uzun vadeli, iyi belgelenmiş bir gerçektir (ekonomik büyüme, şirket kârlarının uzun vadede artması gibi nedenlerle). Bu, "aşağı yönlü bahisler"in (SHORT) istatistiksel olarak "yukarı yönlü bahisler"den (LONG) daha dezavantajlı bir zeminde oynadığı anlamına gelir.'),
  p('Bu yüzden bot, SHORT sinyalleri için daha sıkı eşikler kullanır:'),
  bullet('SHORT sinyalleri yalnızca MARKET_REGIME açıkça BEAR olduğunda veya hissenin düşüş yapısı son derece netken üretilir.'),
  bullet('Hacim ve göreceli zayıflık eşikleri LONG\'a göre daha yüksek tutulur.'),
  pageBreak(),
);

children.push(
  h1('Bölüm 6 — Portföy Risk Yönetimi: "Isı Motoru"'),
  p('Tek bir sinyalin iyi olması yetmez — birçok sinyalin aynı anda açık olması kendi başına bir risktir. Bunu somut bir örnekle açıklayalım:'),
  quoteBox('Gerçek bir ders (30 Temmuz vakası): Botun geliştirme sürecinde bir gün, piyasa genel olarak sert bir düşüş yaşadı. O gün açık olan pozisyonların neredeyse tamamı aynı yöndeydi (LONG) ve hepsi aynı gün doğmuştu — yani birbirinden bağımsız değillerdi. Piyasa düştüğünde hepsi birlikte, aynı anda zarar etti. Kayıp kendi başına sistemin "bozuk" olduğu anlamına gelmiyordu — sorun, çok fazla korele (birbirine bağlı) pozisyonun aynı anda açık olmasıydı.'),
  p('Bu dersten sonra bot, dört katmanlı bir "ısı motoru" ile donatıldı:'),
  ...img('06_heat.png', 520, 306, 'Grafik 6.1 — Portföy ısı motoru: dört kat fren.'),
  table(
    ['Sınır', 'Değer', 'Ne demek'],
    [
      ['Eşzamanlı toplam açık sinyal', '10', 'Aynı anda en fazla 10 sinyal takip edilir'],
      ['Günlük yeni sinyal', '6', 'Bir günde en fazla 6 yeni sinyal üretilir'],
      ['Aynı yönde eşzamanlı', '8', 'Aynı anda en fazla 8 sinyal aynı yönde (hepsi LONG gibi) olabilir'],
      ['Aynı kümede (yön+gün)', '3', 'Aynı gün, aynı yönde doğan sinyallerden en fazla 3\'ü aktif olabilir'],
    ],
    [3200, 1400, 4400],
  ),
  new Paragraph({ spacing: { before: 240, after: 200 }, children: [new TextRun({
    text: 'Bu tavanlardan biri dolduğunda, motor yeni bir sinyal üretmeye devam eder (veriye kaydedilir, analiz için saklanır) ama o sinyal takibe alınmaz ve Telegram\'a bildirilmez. Böylece "tavanın bize maliyeti ne oldu" sorusu da ayrıca ölçülebilir — belki tavan bizi büyük bir kayıptan korudu, belki de iyi bir fırsatı kaçırdık; veri birikince ikisi de görülebilir.',
  })] }),
  pageBreak(),
);

children.push(
  h1('Bölüm 7 — Maliyet Modeli ve "Net-R": Gerçek Kâr Neye Göre Ölçülür?'),
  p('Bir işlemin kağıt üzerindeki R\'si ile cebine gerçekten giren R\'si arasında bir fark vardır: komisyon. Midas\'ta her işlem sabit 1,50 dolarlık bir ücrete tabidir; bir alım + bir satım (gidiş-dönüş) toplamda 3 dolar eder, buna küçük bir kayma (slippage) payı da eklenir (stop\'a çarpıldığında fiyatın tam o seviyeden değil, biraz ötesinden gerçekleşme ihtimali).'),
  pRich([bold('Sezgiye aykırı ama önemli bir gerçek: '), reg('Çünkü bu ücret sabittir (yüzde değil), dar stoplu işlemler orantılı olarak daha pahalıya gelir. Neden? Aynı miktarda dolar riski almak için, stop\'un dar olduğu bir işlemde çok daha büyük bir pozisyon almak gerekir — ve komisyon, pozisyon büyüklüğüne (dolaylı olarak) bağlıdır.')]),
  ...img('07_cost_model.png', 480, 309, 'Grafik 7.1 — Neden dar stop bazen daha "pahalı"?'),
  p('Bot bu yüzden her kapanan işlem için iki rakam tutar:'),
  bulletRich([bold('Brüt R: '), reg('Ham, komisyon düşülmemiş sonuç.')]),
  bulletRich([bold('Net R: '), reg('Komisyon ve kayma düşüldükten sonraki gerçek sonuç.')]),
  p('Gerçek paraya geçiş kararı her zaman Net R üzerinden değerlendirilir — çünkü hesabına gerçekten giren rakam odur.'),
  pageBreak(),
);

children.push(
  h1('Bölüm 8 — Gölge Mod ve Gerçek Paraya Geçiş Kriteri'),
  p('Gerçek paraya ne zaman geçilir? Bu kararın duygularla değil, önceden yazılmış kurallarla verilmesi gerekir — yoksa "bugün moralim iyi, geçelim" ya da "üst üste 3 kayıp geldi, bu iş olmuyor" gibi anlık kararlar devreye girer.'),
  h2('8.1 Yazılı Kriter (üçü birden sağlanmalı)'),
  bullet('En az 40 sonuçlanmış işlem (kazanan/kaybeden/zaman-stopu ile kapanan — doldurulmamış sinyaller sayılmaz).'),
  bullet('Net beklenti ≥ +0,15R/işlem (ortalama olarak her işlem, komisyon sonrası en az 0,15R kâr getirmeli).'),
  bullet('Maksimum düşüş (drawdown) ≤ 8R (kümülatif R eğrisinin zirvesinden en fazla 8R gerileme yaşanmış olmalı).'),
  ...img('09_equity.png', 540, 288, 'Grafik 8.1 — Örnek kümülatif R eğrisi ve düşüş ölçümü.'),
  h2('8.2 Yanlışlama Kriteri (başarısızlığın da önceden tanımlanması)'),
  p('Başarı gibi başarısızlık da önceden tanımlanmıştır: 40 işlemde net beklenti −0,10R\'nin altına düşerse veya düşüş 8R\'yi aşarsa, gölge üretim durdurulur ve strateji yeniden gözden geçirilir. "Belki biraz daha devam ederse düzelir" diye bir kurtarma denemesi yapılmaz.'),
  h2('8.3 Kohort Mantığı'),
  p('Motorun kuralları her değiştiğinde (örneğin yeni bir filtre eklendiğinde), bu yeni bir kohort başlatır ve sayaç sıfırdan başlar. Eski kuralların ürettiği sinyaller, yeni kuralların karnesine karıştırılmaz — çünkü artık farklı bir sistemi değerlendiriyoruzdur.'),
  pageBreak(),
);

children.push(
  h1('Bölüm 9 — Dashboard Kullanım Kılavuzu'),
  p('Şimdi ekranda gördüğün her bölümü tek tek açıklayalım.'),
  h2('9.1 Üst Bar'),
  bullet('CANLI göstergesi ve saat bilgileri: NY (New York) ve TR (Türkiye) saatleri, seans durumu, verinin kaç saniye önce güncellendiği.'),
  bullet('HESAP düğmesi: Ayrıntılı bir kâr/zarar hesap makinesi açar.'),
  bullet('Yenile: Sayfayı manuel tazeler.'),
  h2('9.2 "Şu An En Acil" Şeridi'),
  p('Dikkatini hemen gerektiren en öncelikli durumu gösterir — örneğin bir pozisyonun stop\'u ihlal etmiş olması.'),
  h2('9.3 Çıkış Nöbeti'),
  p('Aksiyon gerektirebilecek açık pozisyonları listeler — örneğin stop\'a çok yaklaşmış veya hedefine çok yaklaşmış pozisyonlar.'),
  h2('9.4 Açık Pozisyonlar'),
  p('Dolmuş (fiyattan girilmiş) tüm sinyalleri listeler: giriş, güncel fiyat, şu anki R durumu, stop\'a/hedefe uzaklık. Her satırın altında ayrıca ilgili şirketin temel verileri de (sektör, F/K, piyasa değeri, PD/DD, borç/özkaynak, FAVÖK marjı) gösterilir.'),
  h2('9.5 Bekleyen Sinyaller'),
  p('Henüz giriş bölgesine gelmemiş, "izlemede" olan sinyaller.'),
  h2('9.6 Cüzdan'),
  p('Bunlar bot sinyalleri değil — kendi elindeki hisseleri (ve Midas\'ta işlem gören ETF\'leri) kişisel takip etmen için. Sembolü ara, adet + giriş fiyatını gir; canlı fiyat, maliyet, güncel değer ve kâr/zararını (istersen bir satış hedefiyle "hedefte net kâr/zarar"ı da) gör. Bu veri sadece senin cihazında saklanır.'),
  h2('9.7 Kâr/Zarar Hesaplayıcı'),
  p('Bir sinyal seçip "Seçili sinyalden doldur" dersen alanlar otomatik dolar; ya da elle hesap büyüklüğü, risk yüzdesi, giriş/stop/hedef gir. Çıktılar: alınacak adet, pozisyon değeri, riske edilen tutar, stop/hedef durumunda net kâr-zarar, R/R oranı, başabaş fiyatı. Üst bardaki HESAP düğmesi, LONG/SHORT seçimi ve iki yönlü mod (riskten adede veya adetten riske) sunan daha kapsamlı bir modal açar.'),
  h2('9.8 Bot Karnesi'),
  p('Dört ölçüte göre bir hüküm verir (Pozitif beklenti / SPY\'yi geçiyor / Kazanç>kayıp / Yeterli örneklem) ve toplam R\'yi (brüt ve net) gösterir.'),
  h2('9.9 Haber Akışı, Geçmiş, Gap Nöbeti, Durum & Log'),
  p('Sırasıyla: izlenen hisselerle ilgili haberler; kapanmış işlemlerin dökümü; sabah gap kontrolünün özeti; sistem sağlığı (uyarı/hata sayaçları, son tarama zamanı).'),
  pageBreak(),
);

children.push(
  h1('Bölüm 10 — Sık Sorulan Sorular'),
  pRich([bold('S: Bot benim adıma otomatik emir veriyor mu?')]),
  p('Hayır. Hiçbir zaman. Her emri sen, Midas uygulamasından elle veriyorsun.'),
  pRich([bold('S: Neden bazı günler hiç sinyal yok?')]),
  p('Piyasa rejimi NEUTRAL veya BEAR\'daysa (ve hisseler net bir yapı sunmuyorsa), bot sinyal üretmemeyi tercih eder. "Her gün mutlaka bir şey bulmak" bir hedef değildir; kaliteyi düşürmemek hedeftir.'),
  pRich([bold('S: Rejim neden bazen "UNKNOWN" görünüyor?')]),
  p('Hafta sonu/tatil günlerinde veya endeks verisi geçici olarak alınamadığında bot güvenli tarafta kalır ve rejimi belirsiz sayar — bu durumda sinyal üretimi de durur.'),
  pRich([bold('S: Bir sinyal "TUT" diyor, bu ne demek?')]),
  p('Pozisyon henüz ne stop\'a ne hedefe yakın; mevcut haliyle beklenmesi gerektiği anlamına gelir.'),
  pageBreak(),
);

children.push(
  h1('Bölüm 11 — Sözlük (A\'dan Z\'ye)'),
  ...[
    ['ATR', 'Ortalama Gerçek Aralık; bir hissenin günlük tipik oynaklık ölçüsü.'],
    ['BEAR / BULL / NEUTRAL', 'Piyasa rejimi durumları (düşüş / yükseliş / kararsız).'],
    ['Breakout + Retest', 'Bir direncin kırılıp hemen ardından o seviyenin destek olarak yeniden test edilmesi.'],
    ['Cluster (Küme)', 'Aynı gün + aynı yönde doğan, birbirinden istatistiksel olarak bağımsız olmayan sinyaller grubu.'],
    ['Confidence (Güven)', 'Sinyalin H/M/L güven etiketi.'],
    ['Dolar Hacmi', 'Günlük işlem gören hisse adedi × fiyat; likidite ölçüsü.'],
    ['Entry Zone (Giriş Bölgesi)', 'Sinyalin önerdiği giriş fiyat aralığı.'],
    ['Gap', 'Önceki kapanış ile bugünkü açılış arasındaki ani fiyat sıçraması.'],
    ['Histerezis', 'Rejim tespitinde ani zıplamaları önlemek için kullanılan "gürültü bandı".'],
    ['Kohort', 'Belirli bir motor kuralı setiyle üretilmiş sinyallerin bütünü.'],
    ['Likidite', 'Bir hissenin kolay alınıp satılabilme derecesi.'],
    ['LONG', 'Fiyatın yükseleceğine dayalı alım pozisyonu.'],
    ['MA (Moving Average)', 'Hareketli ortalama.'],
    ['Net-R', 'Komisyon/kayma düşüldükten sonraki gerçek R sonucu.'],
    ['Pullback', 'Yükselen trend içinde yaşanan kısa geri çekilme.'],
    ['R', 'Riskin evrensel ölçü birimi (Bölüm 2\'de detaylı).'],
    ['Rejim (Regime)', 'Genel piyasanın BULL/BEAR/NEUTRAL durumu.'],
    ['RR (Risk/Ödül)', 'Hedeflenen kazancın riske oranı.'],
    ['RSI', 'Göreceli Güç Endeksi; aşırı alım/satım ölçüsü.'],
    ['SHORT', 'Fiyatın düşeceğine dayalı satış pozisyonu.'],
    ['Setup', 'Saatlik grafikte tespit edilen giriş yapısı (pullback veya breakout+retest).'],
    ['Stop-Loss', 'Zararı sınırlamak için belirlenen çıkış seviyesi.'],
    ['Take-Profit (TP1/TP2)', 'Kâr almak için belirlenen hedef seviyeleri.'],
    ['Zaman-Stopu', 'Bir pozisyonun en geç kaç işlem gününde kapatılacağı.'],
  ].map(([term, def]) => bulletRich([bold(term + ': '), reg(def)])),
  pageBreak(),
);

children.push(
  h1('Sorumluluk Reddi'),
  p('Bu kitap ve bahsi geçen bot, yatırım tavsiyesi değildir. Botun ürettiği hiçbir sinyal, "al" veya "sat" emri anlamına gelmez; sadece belirli kurallara göre tespit edilmiş bir teknik gözlemdir. Geçmiş performans (gölge mod dahil) gelecekteki sonuçların garantisi değildir. Kendi araştırmanı yap, riskini kendin değerlendir.'),
);

const doc = new Document({
  creator: 'Serhat Özdoğan',
  title: 'Midas Sinyal Botu - Kullanıcı El Kitabı',
  features: { updateFields: true },
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 } },
    },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, color: INK, font: 'Calibri' } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, color: '2A4A7A', font: 'Calibri' } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 23, bold: true, color: GOLD, font: 'Calibri' } },
    ],
  },
  numbering: {
    config: [{
      reference: 'default-bullets',
      levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
                style: { paragraph: { indent: { left: 480, hanging: 260 } } } }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, bottom: 1440, left: 1350, right: 1350 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: 'MİDAS SİNYAL — Kullanıcı El Kitabı', size: 16, color: '999999' })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '999999' })],
      })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('/home/claude/handbook/kullanici-el-kitabi.docx', buf);
  console.log('docx yazildi:', buf.length, 'bayt');
});
