# Alet çantası (Short motoru için)

**Bu ne:** Dikey video kurarken elinin altında olan küçük komutlar. İki tür iş için: **klip** (uzun bir yayından tek bir anı dikey klibe çevirmek) ve **bilgi Short'u** (seslendirme + oyun/fragman görüntüsü). Kurguyu bunlar yapmaz; ne olduğunu sen görür, fikri sen bulur, bu aletlerle kendin kurarsın.

Şablon yok, sabit düzen yok, efekt listesi yok. Fikir içerikten çıkar.
Beğenilmiş iki işin sahne kaynağı burada duruyor. Bu sohbetteki ilk işinden önce ilgili olanın `DESIGN.md` ve `index.html`'ini bir kez oku: bir kurguda ne kadar iş olduğunu (fikir, yazı düzeni, hareket, ses) görmek için. İkisi de kalıp değil:
- `ornek-klip/` (bir yayın anından kurulmuş Editli klip). Oradaki geri sayım fikrini başka bir klibe taşımak başarısızlık sayılır: o fikir "8 saniye sonra ölecek" anından çıktı.
- `ornek-short/` (bir Liste Short'u). Oradaki Romen rakamı kapısı fikrini (I II III IV boyası pencereye dönüp sonraki çekimi açıyor) başka bir Short'a taşımak da başarısızlık sayılır: o fikir "bu dört şey" listesinden çıktı.
Örneklerin betikleri çalışmaz (görüntü, ses, font dosyaları içinde yok, yollar kendi iş klasörlerine göre yazılı); okumak içindir.
Aletler hiçbir yapay zekâ modelini başlatmaz; hepsi yerel ffmpeg / Python / HyperFrames ile çalışır ve kendileri internetten bir şey indirmez. Tek istisna yazı tipi: HyperFrames render, sahnede `@font-face` ile bir dosyaya bağlanmamış bir yazı tipi adı, `sans-serif` gibi genel bir ad ya da uzak bir font adresi görürse yazı tipini sormadan Google Fonts'tan indirir (sayfadaki harfleri de gönderir). Bu yüzden sahnede yalnız `fonts/` içindeki dosyaları `@font-face` ile kullan (`sahne_baslat.py --font`, `--font2`; `--yenile` aykırısını yazar). Canvas'a yazı çiziyorsan çizmeden önce fontu yükle (`await document.fonts.load('80px SahneFont')`): canvas fontu kendisi yüklemez, ilk kareler yedek fontla çizilir.

## Çıta (Furkan'ın sözü)
> "çıtamız her videoda bu editi kim yapmış acayip akıcı ve güzel editörü kim bu kanalın dedirtmek"

Nasıl çalışılacağı (fikri yazmak, iyileştirme turu, dürüst hüküm, süre) `panel/AJAN-TALIMATI.md`, "Çıta" bölümünde. Sade klip bunun dışındadır.
Akıcılık önce gelir: düzen (pencerelerin yeri ve boyu) kesmeyle değil hareketle değişir, giden şey gelen şeye yer açar. Efektin sayısı değil özeni önemli: ekrana giren her şey bu videodaki bir nedenle girer ve tasarlanmıştır. "Az efekt" boş ekran demek değildir.

## Göz: iki uçtan da kaç
Teslimden önce bütün videonun şeridine izleyici gözüyle bak. İki ayrı kötü sonuç var, ikisi de çıtanın altında:
- **Düz:** görüntü + kelime kelime altyazı + kaynak satırı. Temiz ama fikir ekranda yok, yazı her videoya konan hazır altyazı gibi, ses yalnız konuşma. Fikri şeritten okuyamıyorsan video budur.
- **Şablon:** her çekim değişimi aynı animasyon, her kelime aynı kayışla giriyor, her geçişte aynı ses üçlüsü (tık + vuus + gum), baştan sona duran birkaç etiket, sayaç, çip. Hareket ve ses ekrandaki olaydan değil alışkanlıktan geliyor.

Sorular (kural değil): Baştan sona ekranda duran şey kaç tane ve her biri fikre mi hizmet ediyor? Çekimden çekime geçişler birbirinin aynısı mı (kesme de hareket de olabilir; hepsi aynıysa şablon, hiç hareket yoksa slayt gibi durur)? Ekrandaki çekim o cümlenin iddiasını mı taşıyor, süs mü? Yazının boyu, yeri, rengi bu video için mi seçildi? Ses ekrandaki olaydan mı geliyor?

Ölçüm notu: çok izlenen 11 GTA Short'una kare kare bakıldı; çoğu düz kesiyor (çekim başına ~2 sn), ekranda 1–2 kelime ve tek kalıcı etiket var. Bu sayılar hedef değildir, o videolar çıta değildir. Onlardan alınan tek ders: fazlalık (çok etiket, her şeye animasyon, her geçişe ses) yapay durur.

**Referans çalış.** Kullanıcı beğendiği videoları motorun kökündeki `referans/` klasörüne koyduysa (git'e girmez), kurguya başlamadan önce onlara `kare_bak.py` ile kare kare bak: kaç saniyede bir kesiyor, ekranda ne kadar yazı var, hangi çekimi hangi söze koymuş. Bunları kısaca not et, sonra kendi işini kur. Referans bir çıtadır, kopyalanacak şey değil: düzenini, rengini, fikrini taşıma.

## Aletler
Hepsi motorun kök klasöründe çalıştırılır. Her birinin `--help` çıktısında örnek bir komut satırı var.

| Alet | Ne yapar | Örnek komut | Ne çıkar |
|---|---|---|---|
| `kaynak_bak.py` | Videonun boyutunu, fps'ini, sesini ve **gerçek yavaşlatma** yapılıp yapılamayacağını söyler. `--kesmeler`: çok çekimli bir parçadaki (fragman parçası) her sert kesmenin kaynak saniyesi ve kare no'su, aralarındaki çekimler (`--esik 6` varsayılandır, düşüğü yumuşak kesmeleri de bulur; 4 sn'den uzun çekim `UYARI` alır: eşiği düşürüp yeniden dene) | `py -3 alet/kaynak_bak.py kayit.mp4 --olc --bas 440 --son 470` (`py -3 alet/kaynak_bak.py ham/video-2.mp4 --kesmeler`) | Ekrana özet; 60 fps kaynakta "en düşük 0.50x"; `KESMELER` ve `CEKIMLER` satırları |
| `kare_bak.py` | Bir aralıktan kare kâğıdı çıkarır; her karede o karenin gerçek kaynak saniyesi ve kare no (kN) yazar. Olayları sen bulursun | `py -3 alet/kare_bak.py kayit.mp4 --bas 440 --son 470 --hiz 1 --cikti bak/genel.jpg` | `bak/genel_01.jpg` … (`--hiz 10` yakın bakış, `--hiz kaynak` her kare, `--kirp w:h:x:y` HUD/yüz büyütme) |
| `kelime.py` | Whisper kelime zamanlarını sese oturtur (başlangıçlar 0.1-1 sn kayabiliyor). Yazıya dokunmaz; güvensiz kelimede Whisper zamanını bırakır ve söyler | `py -3 alet/kelime.py hizala kayit.mp4 panel/isler/<id>/yazi/yazi.json --aralik 440:490 --cikti is/yazi-hizali.json` | Aynı biçimde json; her kelimenin kayması ve güveni |
| `zaman.py` | **Klip için tek zaman haritası**: parçalar, hızlar, yumuşak hız geçişi, iç kesmeler. Görüntü ve ses aynı haritadan geçer. Kare kopyalayacak hızda durur. Parça kenarındaki kelimeleri sese oturtup "yarıda kalan kelime" uyarısını ona göre verir. `--yuz` yayıncı kamerasını 4 px içeriden keser (`--yuz-ic`) | `py -3 alet/zaman.py harita.json --cikti is/zaman --is panel/isler/<id> --yuz` | `video.mp4`, `ses.wav`, `yuz.mp4`, `zamanlar.json/js` (kelimeler ve olaylar yeni zamanda) |
| `cekim.py` | **Bilgi Short'u için tek çekim**: tam kaynak kareleri, siyah bant kesme (`bant`), özneyi takip eden 9:16 kırpma, hızlandırma (gerçek kare atlayarak), `--parcalar` ile gerçek kare hız rampası, `--ara-kare` ile yavaşlatma. Kaynak sesi atılır; dosyada olmayan kare istenirse var olana kadar keser. 29,97 fps kaynakta `--hiz 1` her kaynak karesini bir kez kullanır (0,1 % yavaş, kopya yok). Çıktı boyu `--en`/`--boy` (varsayılan 1080x1920; ör. pencere için `--en 1080 --boy 1080`). `zaman` alt komutu seslendirmenin kelime zamanlarını çekim klasörüne yazar: yanında daha yeni bir `ses-hizali.json` varsa onu kullanır (`KELIME` satırı söyler, `--whisper` istemez); varsayılan uzunluk son duyulan sözün bitişidir (`kontrol.py son` ile aynı ölçü, `ses.wav`'dan; başka ses için `--ses`) | `py -3 alet/cekim.py kes fragman.mp4 --bas 34.63 --son 38.33 --takip 34.63:0.46,38.33:0.71 --cikti is/v/pov.mp4` | 1080x1920 30 fps sessiz mp4; kullanılan kaynak kareleri ve yazılan kare sayısı |
| `sahne_baslat.py` | **Boş** HyperFrames + GSAP sahnesi: 1080x1920, 30 fps, kurulu bir font, yerel gsap, "pencere düzeneği". İçinde tasarım yok. Short'ta `--cekimler` ile yalnız kullandığın çekimleri yerleriyle alır (`dosya` tam yol, ya da çalıştığın klasöre / motorun köküne göre, yoksa json'un klasörüne göre); `--yenile` medyayı, süreleri ve uzunluğu günceller, senin kodunu değiştirmez; json'a yeni eklenen çekimin penceresini de ekler (öbür çekim pencerelerinin hemen arkasına, boş bir track index ile; tam ekran, yalnız kendi zamanında görünür; yerini sen verirsin), json'dan çıkan çekimin penceresini silmez, `UYARI` satırıyla söyler. Short'ta her çekimi kendi süresinde düz kesmeyle gösterir: bu yalnız başlangıçtır, kurgu değil. Font: `--font <ttf>` (`SahneFont`), küçük yazı için ikinci font `--font2 <ttf>` (`SahneFont2`); depoyla gelen `kod/font/Anton.ttf` Türkçe harfleri tam taşır, vermezsen bilgisayarda kurulu ilk fontu alır (Oswald Bold, Bahnschrift, Segoe UI, Arial); seçim senin. Başka bir yazı tipi eklersen dosyasını `fonts/`'a koy ve `@font-face` yaz (yukarıdaki indirme notu) | `py -3 alet/sahne_baslat.py is/sahne --zaman is/zaman --font kod/font/Anton.ttf` (Short: `--zaman is/v --cekimler is/cekimler.json`) | `is/sahne/index.html` ve render komutu |
| `ses.py` | Kodla kısa ses üretir (tik, vuus, gum, darbe, flas, dusus, suzul), sesi konuşmanın altına mikser, ölçer, görüntüye ekler. `--yatak` konuşmada alçalan yumuşak bir altlık, `--akorlar` onun akor değişim saniyeleri. Gerçek tepe aşılırsa sınırlayıcı devreye girer; yükseklik hedeften 0,5 LU'dan fazla saparsa `NOT` yazar. `miks` var olan çıktının üstüne sormadan yazar; `ekle` sesi görüntünün uzunluğunda keser ve kendi yazdığı eski mp4'ün üstüne yalnız `--ustune-yaz` ile yazar ("Tekrar çalıştırmak") | `py -3 alet/ses.py miks is/zaman/ses.wav isaretler.json is/ses-final.wav` | Mastered wav (-14 LUFS civarı, ölçülenler -14,1 ile -14,9 arası; -1.5 dBTP), ölçümler; `ekle` ile son mp4 |
| `kontrol.py` | Yalnız teknik hata: kare şeridi (`serit --an` + `--once`/`--sonra` kare sayısı, bütün video için `--esit 16`, yazı alanı yakın plan için `--kareler ... --kirp`), 1-2 karelik siyah kare (`siyah`: o karede bir pencere yok, üstünde yazı olsa da; `sahne_baslat.py` çekim başlarını kare ızgarasına aşağı yuvarlar), kare kopyası (kare no, saniye, kaynak saniyesi; Short'ta yalnız sahnenin kullandığı çekimler), ses kayması, son kelimede bitiş (yatak varsa `--konusma` ile yalnız sese bakar), süre (Short 10–60 sn varsayılan; klipte `--min 15`), Shorts alanı. Zevke karışmaz: `GECTI` videonun iyi olduğunu söylemez. `hepsi` denetlediği dosyanın yazıldığı saati basar (`DOSYA` satırı); `ses.py ekle`'nin kaydettiği görüntü ya da ses videodan sonra değiştiyse video eskidir ve KALDI der | `py -3 alet/kontrol.py hepsi klip.mp4 --zaman is/zaman --ses is/ses-final.wav --konusma is/zaman/ses.wav --min 15` | Son satır `SONUC: GECTI` ya da `SONUC: KALDI: <neden>`; `hepsi` KALDI'da 1 ile çıkar |

**Tarz defteri** (`tarz.py`): kurgu aleti değil; bu kullanıcının onayladığı ipuçlarını (`tarzim/ozet.md`), sözlerini ve tutmayan denemeleri tutar. İşe başlarken `tarz.py ozet`, teslimden sonra `soru` / `ekle` / `tercih` (adımlar `panel/AJAN-TALIMATI.md` D, kullanıcı için `TARZ.md`). `soru`, `say`, `goster` yalnız okur. `ozet` defter yoksa hiçbir şey yazmaz ve klasör açmaz; defter varsa `ozet.md` ve `reddedilenler.md`'yi günlükten yeniden üretir. `tarzim/` klasörünü yalnız yazan komutlar açar (`ekle`, `tercih`, `ornek`, `aletim`, `kapat`).

**Saniyeler:** `kare_bak.py`, `cekim.py` kaynak saniyesini karelerin üstünde yazan saniye olarak alır. Motorun kestiği fragman parçaları ortadan başlar (ör. ilk kare 33.2 sn); etiketteki saniyeyi ver. İlk karenin yuvarlanmış hâli de olur (`kod/bak.py --aralik` 25.39 yazar, ilk kare 25.392). Adı .mp4 olan MPEG-TS dosyalar da okunur. Kesme noktasını `--hiz kaynak` sayfasından oku; seyrek sayfalar her N kareden birini gösterir.

**Tekrar çalıştırmak:** `zaman.py`, `cekim.py`, `kelime.py`, `kare_bak.py` var olan çıktıyı ezmez. Aynı çıktıyı yeniden üretmek için `--ustune-yaz` ekle: yalnız aletlerin daha önce yazdığı dosya/klasör değişir (klasördeki `.alet-yazdi.json` bunu tutar), senin dosyan asla. Yarıda kalan çalışma arkasında dosya bırakmaz. `zaman-2`, `zaman-3` gibi kopyalar açma. `ses.py ekle` de ikinci turda `--ustune-yaz` ile kendi eski mp4'ünün üstüne yazar (önce yeni dosyayı yazar, sonra yerine koyar; senin ya da eski sürümün yazdığı dosyaya dokunmaz). `ses.py miks` ise her çalışmada çıktısının üstüne yazar. `kontrol.py hepsi` mp4'ün saatini basar ve görüntü ya da ses mp4'ten yeniyse KALDI der: eski dosya denetlenip `GECTI` yanıltmaz. `sahne_baslat.py` var olan sahneyi yalnız `--yenile` ile günceller.

**Pencere düzeneği:** Ekranda bir pencere bir dikdörtgendir (`--x --y --w --h --r`) ve kendi videosuna bakan kendi kamerası vardır. `--cx --cy` kaynakta hangi pikselin pencerenin ortasına geleceğini, `--z` yakınlığı belirler. Düzen değiştirmek pencereyi taşımak ya da yeniden boyutlamak demektir. Her hareket `fromTo` ve `immediateRender:false` ile yazılır, böylece her kare hangi sırayla istenirse istensin aynı çıkar. 0. saniyede görünmesi gereken öğeyi CSS'te görünür bırak: aynı öğeyi `tl.set(..., 0)` ile önce gizleyip sonra açınca ilk karede gizli kaldı. Zamanı dışında gizlenen bir `<video>` penceresi yalnız `visibility` ile gizlenince render'da sızdı (render videonun yerine koyduğu kareye opaklığı taşır, görünürlüğü taşımaz): pencereye `opacity: 0` da ver; GSAP'te `autoAlpha: 0` ikisini birden yapar.
Kurgunun tamamı tek `index.html`'de kalır (bu kural lint'in önerisinden üstündür): lint `composition_file_too_large` deyip "böl" önerirse yalnız uyarıdır, bölme. Hareket kodunu dış bir `.js`'e koyarsan lint `missing_timeline_registry` hatası verir (yalnız `index.html`'in içine bakar): zaman çizelgesini kaydeden `window.__timelines[...] = tl` satırını `index.html`'in kendi `<script>`'inde bırak.

Render ve kare yakalama (2 işçi: bilgisayarda başka iş ya da render çalışırken de güvenli; yalnız hiçbir şey çalışmıyorsa 3, fazlası belleği doldurur):
`hyperframes render is/sahne --output is/sahne/render/taslak.mp4 --quality draft --workers 2`
`hyperframes snapshot is/sahne -o is/bak/an --at "1.0,4.5" --describe false` (`--at` listesi tırnak içinde: PowerShell tırnaksız virgülde böler ve hata vermeden yalnız ilk kareyi alır)
`--describe false` şart: yoksa snapshot, bilgisayarda anahtar varsa kareleri bir yapay zekâ modeline (Gemini) anlattırır; çanta hiçbir model çağırmaz. Snapshot karelerin yanına `contact-sheet*.jpg` (hepsi tek kâğıtta) ve zamanın sonundan bir kare de yazar; model çağırmaz.
Bitince `--quality high` ile tekrarla, sonra `ses.py ekle`. Sahne klasöründe `index.html` dışında `.html` bırakma: lint "multiple_root_compositions" verir.

## Motorun hazır bıraktıkları (`panel/isler/<id>/`)
Serbest adımın girdileri bunlar. Yeniden üretme, oku.
Klip işi:
- `klip_plan.json` (motor değil, an seçerken sen yazarsın; alanları `panel/AJAN-TALIMATI.md` A, 4. adımda): `kaynak` (ham video yolu), `kamera` ve `yuz` kutusu (0-1 oranında), `sohbet_kutu` (varsa), `klipler[].bas/son` (seçilen anlar).
- `yazi/yazi.json`: bir nesne; Whisper kelime zamanları `kelimeler` alanında: `{"kelimeler": [[kelime, baş, son, olasılık], ...], "cumleler": [...], ...}`, kayıt saniyesiyle. `zaman.py --is` bunu kendisi okur.
- `yazi/yazi.txt`: düz döküm. `yazi/adaylar.md` ve `adaylar.json`: aday anlar. `yazi/isaretler.json`: kullanıcının anları ve ses/sohbet tepeleri. `yazi/enerji.json`: ses yüksekliği.
- `kamera/kamera.json`, `kamera/kamera-bak.jpg`: yayıncı kamerasının kutusu ve göz kontrolü karesi.
Bilgi Short'u işi:
- `metin.txt`: seslendirmenin metni. **Ekrana yazılan yazı buradan alınır.**
- `ses/ses.wav`: seslendirme; miks edilen ve kelime zamanlarının saniyesi olan dosya budur (`kod/ses_yazi.py` baştaki ve sondaki sessizliği keserek yazar). `ses/yer-tutucu-ses.wav` (Windows'un deneme sesi) ve `ses/kayit.*` (kullanıcının verdiği ses) ham girdidir: miks edilmez, saniyeleri ses.wav'dan farklıdır. `ses/ses.json`: Whisper kelime zamanları, ses.wav saniyesiyle; o da nesne: `{"sure": ..., "kelimeler": [[kelime, baş, son, olasılık], ...]}`. `ses/ses-hizali.json`: aynı kelimeler, hazırlıkta `kelime.py hizala --hepsi` ile sese oturtulmuş (Whisper cümle başlarını 0,2-0,7 sn erken yazıyor); `cekim.py zaman` onu kendisi seçer. Yazımı yanlış olabilir ("Rockstar" yerine "Roadstar", "jet ski" yerine "Jetsiki"); zamanı buradan, yazımı `metin.txt`'den al.
- `ham/`: yüklenen videolar (fragman parçaları). `is.json` içindeki `ham[].bitis` son karenin değil bitişin saniyesidir.
- `plan.json` motorun bıraktığı bir dosya değil; işi yapan ajan yazar.
- `is.json`: işin durumu (yalnız motor yazar).

Motorda olan, burada tekrar yazılmayan araçlar: `kod/ses_yazi.py` (yerel Whisper), `kod/klip_bul.py` ve `kod/sohbet.py` (sesten, söylenenlerden ve sohbetten an bulma; kamera kutusunda yüz yoksa adayın puanı düşer), `kod/kamera_bul.py` (kamera kutusu; hazırlıkta an bulmadan önce çalışır).

## Tipik iş sırası (komutların sırası öneridir; fikir ve iyileştirme turu atlanmaz)
Klip:
1. `kaynak_bak.py`: fps nedir, yavaşlatma mümkün mü?
2. `kare_bak.py --hiz 1` ile bütün ana göz at, sonra önemli saniyelere `--hiz 10` ve `--hiz kaynak --kirp` ile yakından bak. Ne oluyor, kim ne diyor, ne zaman?
3. Fikri bul: kurulum, dönüş, kapanış. Bu klibe özgü olsun. Tek cümleyle kaydet: `node panel/durum.js panel/isler/<id> fikir klip-1 "<tek cümle>"`.
4. `harita.json` yaz, `zaman.py` çalıştır (haritayı değiştirince `--ustune-yaz`). Kelimeler artık yeni zamanda. Harita yalnız bir aralık değildir: dolguyu kesmek, bir anı yavaşlatmak ya da hızlandırmak burada yapılır.
5. `sahne_baslat.py` (harita değişince `--yenile`), sonra `index.html` içinde kendi kurgun. `--quality draft` render, `kontrol.py serit` ile geçişlere kare kare bak, düzelt.
6. İyileştirme turu: `kontrol.py serit taslak.mp4 --esit 16 --sutun 8 --cikti is/bak/hepsi.jpg` ile bütün videoya bak, en zayıf üç saniyeyi adıyla yaz, düzelt, yeniden render.
7. `isaretler.json` yaz, `ses.py miks`; final render; `ses.py ekle`; `kontrol.py hepsi ... --min 15`.
Bilgi Short'u:
1. `metin.txt` (GTA 6 işinde `bilgi-havuzu.md` de) oku; `ham/` videolarının tamamına `kare_bak.py` ile bak. Her cümleye hangi saniyeler uyuyor? Bir cümleye birden çok çekim düşebilir.
2. Fikri bul: bütün Short'u taşıyan tek motif ve her cümleden sonrakine hareketle geçiş. Bu metne özgü olsun. Tek cümleyle kaydet: `node panel/durum.js panel/isler/<id> fikir "<tek cümle>"`.
3. Her çekim için `cekim.py bant`, sonra `cekim.py kes`; `cekim.py zaman is/v --kelimeler panel/isler/<id>/ses/ses.json` (yanındaki `ses-hizali.json`'u kendisi kullanır; video son duyulan sözün bitişinde biter, `kontrol.py son` ile aynı ölçü; başka uzunluk için `--sure <sn>`, son sözden en çok 0,1 sn sonrası); kullandığın çekimleri `is/cekimler.json`'a yaz (`dosya`, `bas`, `sure`); `sahne_baslat.py is/sahne --zaman is/v --cekimler is/cekimler.json`. Çekim ya da süre değişince aynı komut `--yenile` ile.
4. Draft render; her geçişe `kontrol.py serit --an <geçiş sn> --once 4 --sonra 6` (kare); yazı alanına `serit --kareler ... --kirp`.
5. İyileştirme turu: bütün videonun şeridi (`serit --esit 16 --sutun 8 --cikti is/bak/hepsi.jpg`), en zayıf üç saniye, düzelt, yeniden render.
6. `ses.py miks ses/ses.wav isaretler.json ses-final.wav --yatak -27 --akorlar <bölüm saniyeleri>`; final render; `ses.py ekle`; `kontrol.py hepsi short.mp4 --zaman is/v --ses ses-final.wav --konusma panel/isler/<id>/ses/ses.wav`. Short en az 10 sn'dir (kapı da aynı sayıyı kullanır); `--min` ile indirme, metin kısaysa kullanıcıya söyle.

## Videoyu bozan katı kurallar (hepsi yaşandı)
- **Kare kopyası yok.** 30 fps kaynakta gerçek karelerle yavaşlatma yok; 60 fps kaynakta en fazla 0.5x. Daha yavaşı yalnız ara kare üretimiyle (`cekim.py --ara-kare`), sonra kare kare bakarak: ince hızlı şeyler (pervane, halter, el) bulanıp çiftlenir. `zaman.py` ve `cekim.py` kopyalayacak hızda durur.
- **Ses ve görüntü aynı haritadan** (klip). Yavaşlatmada ve kesmede ikisi birlikte değişir. Ayrı ayrı oynanırsa senkron kayar.
- **Okunması gereken yazı Shorts alanına girmez:** alt %18, sağ ~%11, üst kenar. `kontrol.py alan` ile bak.
- **Yazı kelimesinden önce gelmez:** en fazla ~0.04 sn erken. Kelime zamanı şüpheliyse `kelime.py hizala`.
- **Türkçe harfler maskede kesilmez, sızmaz:** Ö Ü İ noktaları, Ğ şapkası, Ş Ç çengelleri fontun kutusunun dışına taşar; ne kadar taştığı fonta göre değişir. Bir kelime maskede beklerken, girerken ve çıkarken birer kareyi `kontrol.py serit --kareler ... --kirp <yazı alanı>` ile büyütüp bak: harfin hiçbir parçası kesik olmamalı, bekleyen kelimenin noktası maskenin kenarında çizgi gibi görünmemeli. Görünüyorsa maske boşluğunu ya da kaydırma miktarını büyüt, yeniden bak.
- **Siyah bantlar:** fragmanların bazıları sinema oranında (4K'da üstte ve altta 216 px siyah). Bantı kesmeden kırpınca dikey videoda siyah şerit kalır. `cekim.py bant` ile bak; `kes` varsayılan olarak keser.
- **Geçişin içinde düz kare:** yalnız düzenli aralıklı şerit geçişin içindeki 2-4 düz renk / perde karesini kaçırdı. Her geçişe ardışık kare şeridiyle bak. Gelen çekim pencerenin içinde ilk kareden görünmeli.
- **Katman sırası:** üst katmanlara (boya, HUD, gren) açık `z-index` ver; vermeyince boya videoların altında kaldı.
- **Ses tepesi:** ilk miks +0.37 dBTP çıktı (taşma). Son mp4'te `ses.py olc` ile bak: -14 LUFS civarı, tepe -1.0 dBTP'nin altında.
- **Skor tablosu kadraja girmesin, üstüne yazı konmasın** (klip): oyun kamerasını tablonun altından çerçevele.

## Bilgi Short'u kuralları
- Ekrandaki her bilgi ve rakam kullanıcının metninden ya da gösterdiği kaynaktan gelir, kendin rakam ekleme; GTA 6 bilgisinin kaynağı `bilgi-havuzu.md`. Metinde yazıyla geçen sayı ekranda rakamla yazılabilir. Kaynak ekranda küçük ama okunur yazılır ve gerçek kaynağı söyler: bilgiyi asıl söyleyeni ve tarihini yaz, aktaran siteyi parantezde ("KAYNAK: ROCKSTARGAMES.COM/VI", "KAYNAK: ROCKSTAR BASIN BÜLTENİ, 24.06.2026 (GAMEDEVELOPER.COM)"); kullanıcının kendi ölçümüyse öyle yaz.
- Resmî fragman ya da oynanış görüntüsünde kaynak sesi kapalı (`cekim.py` sesi atar); görüntü kullanıcının kendi kaydıysa hak cümlesi söylenmez. Kan, şiddet, hikâye sürprizi (spoiler) yok: silah ve çatışma görünebilir; kan, infaz, vahşet yakın planı olmaz.
- Uzun alıntı kartı yok; görüntünün üstünde kısa damga yeter.
- Seslendirme yer tutucuysa (TTS) ritim yanıltır; asıl ses gelince zamanları yeniden al.

## Furkan'ın varsayılanları (kullanıcı değiştirebilir)
- Küfür filtrelenmez, bip yok.
- Son kelimeden sonra hiçbir şey eklenmez: tekrar yok, kapanış yok, abone çağrısı yok. Video son kelimede biter (en fazla 0.1 sn sonra).
- Yüzün üstüne yazı konmaz (yayıncının yüzü de, yakın plandaki oyun karakterinin yüzü de).
- Her işe çizim yapılmaz. Araç içerikten seçilir. Maskot, çöp adam, kalem/tebeşir imleci, düz kâğıt sahne + ikon kartı, web sayfası/slayt görünümü yok. "Dondur + etiket + halka" tek başına sıradan sayılır.
- İndirilmiş müzik ya da ses örneği yok. Sesler kodla üretilir, konuşmanın altında kalır.

## Bilinmesi gerekenler
- Yayın kayıtlarında kaynağın kendisi de kare tekrarlar (encoder düşürmesi). `kontrol.py kopya` tek tük tekrarı uyarı olarak gösterir (kaynak saniyesiyle; `kare_bak.py --hiz kaynak` ile kaynakta da var mı bak); 2'den fazlası kalır.
- `kelime.py` sesin altında aynı yükseklikte oyun sesi ya da müzik varsa bir başlangıcı erken/geç bulabilir; çok kayan kelimeleri ayrıca yazar, onlara karelerden bak.
- Yayıncı kamerası çoğu zaman 450x250 piksel civarında. 3 katından fazla büyütünce yumuşar.
- `cekim.py --ara-kare` istenen kare sayısını yazar (eski sürüm 2-4 kare az yazıyordu); yazdığı sayıyı yine söyler, sahnede süreyi ona göre ver.
- Render önbelleği: HyperFrames 0.8.140 iş klasöründe önbellek bırakmıyor (`render/` içinde yalnız senin mp4'lerin kalır); ortak önbelleği kullanıcı klasöründe, `~/.cache/hyperframes` (bu bilgisayarda ~640 MB ölçüldü). Eski sürümler sahnenin `render/.cache` klasörünü büyütüyordu. Hangisi olursa olsun silmek kullanıcının onayıyla olur.
