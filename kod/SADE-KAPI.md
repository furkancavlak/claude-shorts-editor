# Sade klip kapısı: kalan kontrol ne demek, ne değişir

Sade klip (düz kesim) `kod/klip.py` ile kurulur, `kod/kapi.py` ile denetlenir:

```
py -3 kod/kapi.py panel/isler/<id>/klip_plan.json panel/isler/<id>/klipler > panel/isler/<id>/kapi_sonuc.txt
```

**Sade klip tasarım gereği düz kesimdir.** Fikir (`durum.js fikir`), "Deneme: …" notu, iyileştirme turu ve "editörü kim" çıtası Sade'de istenmez; `durum.js hazir` Sade'de bunları sormaz. Teknik kontrol geçince iş biter. Süre: an seçerken hedef 15–45 sn, kontrol 15–60 sn'yi geçirir (4 SURE).

`kapi.py` Klip planını (`"tarz": "klip"`) tanır; ikinci argüman kliplerin klasörüdür. Her satır bütün klipleri kapsar: bir klip kalırsa satır kalır. Kayıt kendi sesiyle çıktığı için "kaynak sesi yok" kontrolü burada yoktur; yerine 7 SES, kaydın sesinin aynı saniyelerde olduğunu denetler. Süre ve kare sayısı teslim edilen mp4'ün kendisinden ölçülür, rapordan alınmaz.

## Kurmadan önce (tur harcamaz)
- **Sözler:** `py -3 kod/klip.py panel/isler/<id>/klip_plan.json --sozler` her klibin altyazıya girecek kelimelerini yazar; Whisper'ın emin olmadıkları `[kelime 0.24]` diye köşeli parantezde. Adları ve oyun terimlerini ekrandan (skor tablosu, öldürme listesi) oku, emin olduklarını klibin `yazim`'ine yaz. Anahtar birden çok kelime olabilir: `"yazim": {"ölüm günü": "doğum günü", "amcan": "RahmiCan", "min valleri": "M4A1"}`. Her değişikliği son mesajda söyle.
- **Kadraj:** `py -3 kod/klip.py panel/isler/<id>/klip_plan.json panel/isler/<id>/klipler --onizle klip-2 [kayıt saniyesi]` tek kare yazar (`klipler/klip-2-onizleme.jpg`): oyunun hangi kısmı görünüyor, altyazı nereye düşüyor, yüz (yeşil çerçeve) nerede. 16:9 oyunun yalnız ~%46'sı görünür. Klibin kendi girdisinde: `"odak": "orta"` (nişangâh; verilmezse kamera ve sohbet kutusundan kaçan, ortaya en yakın yer), `"sag"` (sağ üstteki öldürme listesi), `"sol"` (sol alttaki oyun mesajları) ya da 0–1 arası sayı (kamera ya da sohbet o taraftaysa kırpma yayının kamera penceresini oyun bandına sokar, yüz iki kez görünür ve 5 KADRAJ "UYARI" çıkar: önce `oyun` kırpmasıyla kamerasız almayı dene, olmuyorsa altyazıyı ikinci yüzün üstünden çek ve teslimde söyle); `"oyun": [0, 0.12, 1, 1]` skor tablosu satırını kadrajdan atar. Olayın kanıtı (kim kimi vurdu, "oyundan atıldı" yazısı) kadrajda değilse klibi kurmadan düzelt.
- **Altyazı yeri** (`"yazi_yer"`, plan ya da klip): varsayılan `"oyun_ust"`, oyun bandının dörtte biri aşağısı (çoğu oyunun üst gösterge satırının altı, nişangâhın üstü). Başka seçenekler: `"dikis"` (kamera ile oyunun birleştiği çizgi), `"alt"` (ekranın %70'i) ya da 0–1 arası sayı. Altyazı yüzün üstüne gelirse kontrol kalır.
- **Tepkiden önceki sessiz olay:** Sade klip ilk sözden başlar. Olay sözden önce, sessizce oluyorsa klibe `"on_pay": 2.5` yaz (en çok 3 sn): görüntü ilk sözden o kadar önce başlar. `adaylar.md` bunu "ilk sözden önce N sn konuşma yok" diye işaretler.

## Kalırsa
`KALDI` ise aşağıdaki tablodan düzelt, yalnız o klibi yeniden kur (`py -3 kod/klip.py <plan> <klasör> --sadece klip-2`), kapıyı yeniden çalıştır. En çok 3 tur. Ara turları panele `kapi` ile gönderme, `basla kurgu "2. tur: <neden>"` yaz.

**3 turda geçmezse:** son sonucu `node panel/durum.js panel/isler/<id> kapi panel/isler/<id>/kapi_sonuc.txt` ile gönder (sayfa "Son kontrolden geçmedi" gösterir; `hata` yazma) ve kullanıcıya hangi klibin hangi kontrolde kaldığını söyle. Kalan klibi kendiliğinden plandan çıkarma ve yerine zayıf bir anla doldurma; o klibi çıkarıp kalanları teslim etmeyi öner.

| Geçmeyen kontrol | Genellikle neden | Ne değişir |
|---|---|---|
| 0 KLIP | plandaki bir klip kurulmamış | `klip.py`'yi o klip için çalıştır |
| 1 BASLANGIC | ilk kelime geç başlıyor | `bas`'ı ilk cümlenin başına (`yazi.txt`'deki saniye) çek. Başta bilerek sessiz görüntü istiyorsan `on_pay` yaz (en çok 3 sn; kontrol o zaman `on_pay` + 0,1 sn'ye bakar) |
| 2 BITIS "CUMLE BITMIYOR" | `son` cümle bitmeden; son kelime noktasız ve orada cümle bitmiyor | `son`'u o cümlenin bittiği saniyeye ilerlet (klip hedefin üstüne, 45 sn'ye çıkacaksa başı bir cümle ileri al; 60 sn'yi geçerse 4 SURE kalır) |
| 2 BITIS "KELIME ICINDE KESIYOR" | Whisper sonraki kelimeyi tam son kelimenin bittiği saniyede başlatmış (aralarında boşluk yok) | `son`'u aralarında boşluk olan bir cümle sonuna al. Boşluğu `yazi/yazi.json` → `kelimeler`'de gör: cümlenin son kelimesinin bitişi ile sonraki kelimenin başı arası ≥ 0,1 sn olmalı. `adaylar.md`'deki aday pencereler bu şartı zaten taşır |
| 3 ALTYAZI "fark" | `yazim` anahtarı Whisper'ın yazdığıyla eşleşmedi ya da bir kelime ekrana gelmedi | `yazim`'in sol tarafı Whisper'ın yazdığı kelime(ler) olmalı, `--sozler` çıktısından kopyala (klibin kendi girdisinde; zaman değişmez); kalırsa o düzeltmeyi kaldır |
| 3 ALTYAZI "YAZI YUZUN USTUNDE" | altyazı yeri yüzle çakışıyor (çoğu zaman `yazi_yer` `"dikis"` ya da küçük bir sayı) | `yazi_yer`'i `"oyun_ust"` yap ya da büyüt; `--onizle` ile bak |
| 4 SURE | 15 sn'den kısa ya da 60'tan uzun | komşu cümleyi ekle ya da çıkar; kısa ama iyi an tek başına klip olmaz, bırak. Kullanıcının verdiği aralıkta satır kalmaz, "UYARI:" ile geçer: değiştirme, kullanıcıya söyle |
| 5 KADRAJ "SIYAH BANT" | çıktının kenarında %2'den büyük düz siyah alan (karede siyah çerçeve var ya da `sigdir`'de koyu sayfa) | kayıttaki siyah çerçeveyi `kamera`/`oyun`/`kadraj` dışında bırak; `sigdir` yerine `doldur` dene |
| 5 KADRAJ "DIKIS YANLIS" | kamera bandının sınırı 614/778 px'te değil ya da karede görünmüyor | `kamera` kutusunu düzelt (kutu kameradan büyükse oyun kamera bandına taşar) |
| 5 KADRAJ dikdörtgen | 0–1 dışında, ters (x0 > x1) ya da kayıtta küçük (kamera kırpması < 120 px, diğerleri < 160 px) | `py -3 kod/bak.py "<kayıt>" <sn> <sn+1> 1 <çıktı.jpg> --bolge x0,y0,x1,y1` ile yeniden bak, düzelt |
| 5 KADRAJ "UYARI" (kalmaz) | yüz kamera bandının %30'undan küçük ya da oyun kırpması kamera/sohbet kutusunu kapsıyor | `yuz`'u ver ya da düzelt; `odak`'ı kaydır |
| 6 HIZ | normalde olmaz (Sade yavaşlatmaz); değişken kare hızlı kayıtta çıkabilir | rapordaki `kare_cikti` / `kare_kaynak_beklenen`'e bak; kullanıcıya söyle (OBS'de sabit kare hızı) |
| 6 HIZ "TESLIM DOSYASI EKSIK" | teslim edilen mp4'te rapordan az kare var (18.11.2026'dan önce kurulan kliplerde ses eklenirken son kareler düşüyordu) | o klibi `--sadece` ile yeniden kur |
| 7 SES | yanlış ses izi (`ses_izi`), sesi kayan ya da bozuk kayıt. Sessiz bir klibin yükseltilmesi artık düşürmez: sınırlayıcının çalıştığı anlar karşılaştırmaya girmez (satırda "sinirlayici payi" yazar) | `ses_izi`'ni düzelt (OBS'de 0 = hepsi), yeniden kur. Kalırsa yukarıdaki "3 turda geçmezse" yolu |
| 8 BINDIRME | Sade klipte çizim ve vurgu sözü yoktur; satır "yok" diye geçer | — |

Kapının yakalamadığı şeye gözle bak: her klibin `klipler/<ad>-kareler/serit.jpg`'si. Yüz kamera bandında büyük mü, olay oyun bandında görünüyor mu, kırpma önemli yeri kesiyor mu? Olay bandın dışında kalıyorsa `odak`'ı, `oyun`'u ya da `kadraj`'ı düzelt (önce `--onizle`) ve o klibi yeniden kur (bu da bir tur sayılır).

Bağlı adımlar: `panel/AJAN-TALIMATI.md` A1 (Sade) ve C (Teslim).
