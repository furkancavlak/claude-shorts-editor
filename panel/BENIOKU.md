# Short Motoru — izleme sayfası

İş yalnız **Claude Code sohbetinden** açılır ve yürür: videonu ve isteğini sohbette Claude'a söylersin, Claude işi `node panel/is_ac.js` ile açar, motor hazırlar, Claude kurgular. Bu sayfa **yalnız izleme sayfasıdır**: ilerlemeyi, çıkan videoları ve tarz defterini gösterir. Hiçbir şey sormaz; iş açan, başlatan ya da değiştiren bir düğmesi yoktur. Bu bilgisayarda çalışır (`127.0.0.1`), hesap istemez, internete çıkmaz.

Tam olarak ne yazılır:
- **Sayfanın kendisi** (tarayıcıdaki) yalnız okur; sunucudan yalnız bilgi ister, iş klasörlerine ya da tarz defterine hiçbir şey yazmaz, hiçbir şeyi silmez. Tek hatırladığı şey koyu/açık seçimidir, o da tarayıcıda durur.
- **Sayfayı açan ve sunan programlar** (`ac.js`, `server.js`) kendi iki küçük dosyasını yazar: `panel/calisiyor.pid` (kapatabilmek için) ve `panel/panel-cikti.txt` (sunucunun kendi çıktısı). Hiçbir dosyayı silmez, Claude'u ya da bir modeli başlatmaz.
- Sunucu yalnız okuma isteklerine (`GET`, `HEAD`) cevap verir; iş açan ya da değiştiren bir yolu yoktur, başka her istek "yalnız okur" cevabı (405) alır. Yolların listesi: `GET /api/yardim`.

## Sayfada ne var
Üstte iki sütun: solda **Şimdi**, sağda **Son çıkan**. Altında önceki çıktılar, en altta tam genişlikte **Tarz defteri**.
1. **Şimdi:** süren ve takılan her iş, ince çizgilerle ayrılmış satırlar halinde. Her satırda işin adı ve türü (Klip · Sade, Short · Liste …), ne olduğunu söyleyen tek cümle ("Claude kurguluyor", "Motor konuşmayı yazıya döküyor"), beş kısa çizgi ve "3/5 · Kurgu · 4 dk" yazısı. Editli klipte ve Short'ta Claude'un kaydettiği fikir ("Fikir: …") ve deneme ("Deneme: …") de satırda yazar. Bir şey bozulduysa aynı satırda "Ne oldu?" ve "Ne yap?" yazar; "Ne yap?" her zaman sohbette Claude'a söylenecek bir cümledir (ör. "Sohbette “GTA 6'yı almadan önce… işine devam et” yaz."). Süren iş yoksa, yeni video için sohbete ne yazacağını gösterir.
2. **Son çıkan:** en son biten video büyük, gerçek karesiyle (216 × 384): tam başlık, süre, kurgunun fikri ("Fikir: …"), Claude'un o videoda bilerek denediği şey ("Deneme: …"), Claude'un kendi hükmü ("Claude'un hükmü: …") ve İndir. Oynatmayı sen başlatırsın. Henüz biten video yoksa bu sütun yoktur, Şimdi tam genişlik olur; süren iş yoksa Son çıkan öne geçer.
3. **Önceki çıktılar:** diğer videolar ve klipler, aynı düzende ama küçük, yan yana. Dosyanın bilgisayardaki yeri sayfada yazmaz; fareyle videonun ya da İndir'in üstüne gelince görünür (ajanlar için `GET /api/ozet` içinde de var).
4. **Tarz defteri:** `tarzim/` klasöründe ne varsa, ince çizgili okuma alanı: solda senin sözün, sağda kısa açıklama ("Kalıcı tercih · 3 videoda söyledin", "2/3 · bir kez daha söylersen Claude sorar", "Claude denedi, tutmadı"); çelişen iki söz aynı satırda. İç kayıt adları gösterilmez. Defter boşsa tek satır: "İlk videona yorum yaptığında sözlerin burada görünecek." Sayfa deftere hiçbir şey yazmaz; bilgiyi `py -3 alet/tarz.py goster --json` ile okur (bu komut da yalnız okur).

Sayfanın sana söylediği tek şey, gerçekten öyleyse Şimdi'nin başındaki ince sarı kenarlı satırdır: **"Sıra sende · <iş adı> (<tür>): …"** (Claude durup bir şey sorduysa, video son kontrolden geçmediyse ya da Claude yeni biten video için tek sorusunu ("En çok neyi beğendin?") sohbette sorduysa ve cevap henüz deftere düşmediyse; soruyu sorduğunu Claude `durum.js soruldu` ile yazar). Bozulan iş kendiliğinden "sıra sende" sayılmaz; kırmızı yalnız hata işaretinde ve duran çizgidedir.

Sayfa kendiliğinden yenilenir; ikinci ekranda açık bırakılabilir. Varsayılan koyu; "Açık" seçimi hatırlanır.

## Açmak, kapatmak
- **Açmak:** sohbette "paneli aç" de ya da motor klasöründe `Paneli-ac.cmd`ye çift tıkla (pencere açmadan başlar, tarayıcıda `http://127.0.0.1:4317` açılır). Elle: motor kökünde `node panel/ac.js` (arka planda açar) ya da `node panel/server.js` (terminalde kalır).
- **Kapatmak:** `Paneli-kapat.cmd` ya da `node panel/dur.js` (panelin kendi yazdığı `panel/calisiyor.pid` numarasıyla, `PANEL_PID_DOSYA` verildiyse o dosyadakiyle durdurur; başka programa dokunmaz).
- Bir şey eksikse sayfanın üstünde tek satır çıkar: Claude Code'a "bu depoyu kur" yaz.

## Ajanlar için (tarayıcısız)
- `GET /api/yardim`: bütün yollar, sade Türkçe.
- `GET /api/ozet` (bütün işler) ve `GET /api/is/<id>/ozet` (tek iş): sayfadaki durumun metin hali. Panel kapalıyken aynısı: `node panel/durum.js panel/isler/<id> ozet`.
- `GET /api/defter`: tarz defteri (JSON, yalnız okur). `GET /api/sozluk`: ortak adlar.
- Ortak adlar (iş türleri, aşamalar, durumlar, kontroller) tek dosyada: `panel/sozluk.json`. Sayfa, `server.js`, `durum.js` ve `AJAN-TALIMATI.md` aynı adları kullanır.
- "Deneme: …" ve "Hüküm: …" satırları işin geçmişinden okunur: `node panel/durum.js panel/isler/<id> not "Deneme: …"` (ve `not "Hüküm: …"`). Fikir `is.fikir`'den (`durum.js fikir`), soru `is.soru`'dan (`durum.js soruldu`).
- **İş açmak ve sürdürmek sunucudan yapılmaz.** İş sohbetten `node panel/is_ac.js` ile açılır (`klip`, `short`, `devam`), durumu `node panel/durum.js` yazar; ikisi de panel kapalıyken çalışır. Sunucuda `GET` dışında yol yoktur. Hazırlık sürerken `is.json`'da `hazirlayan` (hazırlayan komutun PID'i) durur; o komut kapanmışsa sayfa işi "Yarıda kaldı" gösterir.
- Deneme için: `PANEL_PORT` (kapı), `PANEL_ISLER` (işler klasörü), `PANEL_TARZIM` (defter klasörü), `PANEL_PID_DOSYA` (pid dosyası; `server.js` ve `dur.js` ikisi de okur, asıl panelinkine dokunmamak için), `PANEL_SAHTE_EKSIK` (kurulum şeridini denemek için).

## İşler nerede
`panel/isler/<id>/`: `is.json` (işin durumu; yalnız `panel/is_ac.js` ve `panel/durum.js` yazar, elle yazılmaz), `ham/`, `ses/`, `plan.json` / `klip_plan.json`, `short.mp4` ya da `klipler/`, `kapi_sonuc.txt`, `panel-gunluk.txt`. `panel/isler/` depoya girmez.

## Dosyalar
`is_ac.js` (sohbetten iş açma), `hazirlik.js` (motorun hazırlığı: yazıya dökme, an ve kamera bulma; `is_ac.js` çalıştırır, sayfa yalnız sürüp sürmediğine bakar), `durum.js` (ajanın iş durumunu yazdığı araç), `server.js` (izleme sayfasının sunucusu), `ac.js` (sayfayı açma), `dur.js` (durdurma), `hazir_mi.py` (kurulum eksiği var mı; yalnız bakar), `is_dosyasi.js` (ortak iş dosyası kodu), `sozluk.json` + `sozluk.js` (ortak adlar ve sade durum), `kapi_topla.js` (son kontrol), `arayuz/` (izleme sayfası), `AJAN-TALIMATI.md` (ajanın adımları).
