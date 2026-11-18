# Short motoru: ajan için giriş

> `CLAUDE.md` ve `AGENTS.md` aynı metindir (her ajan kendi adını okur). Birini değiştirirsen ötekini de aynen değiştir.

Bu depo, kullanıcının verdiği görüntüden (kendi oyun ya da yayın kaydı; Short'ta resmî fragman görüntüsü de olabilir) dikey Short ve klip kuran bir kurgu motorudur: iş klasörleri, yerel Whisper, kamera bulucu, teknik kontrol ve bir alet çantası. Kurguyu sen (kullanıcının kodlama ajanı) HyperFrames + GSAP ile yazarsın; motor görüntü üretmez ve hiçbir yapay zekâ modelini kendisi başlatmaz.

Kullanıcı kod bilmez. Tek giriş bu sohbettir: kullanıcı ne istediğini söyler, sen kurar, işi açar, bitirir ve videoyu açarsın. Panel yalnız izleme sayfasıdır: ilerleme, çıkan videolar, tarz defteri.

## Hangi iş için hangi dosya
| İş | Oku |
|---|---|
| Kurmak, eksik bir şeyi tamamlamak, "çalışmıyor" | `KURULUM-AJAN.md` |
| Bir klip ya da Short işi (açmak, yapmak, teslim) | `panel/AJAN-TALIMATI.md` |
| Kurgu aletleri | `alet/ALETLER.md` |
| Tarz defteri | `TARZ.md` (kullanıcıya anlatılan), komutlar `py -3 alet/tarz.py --help` |
| Short'ta rakam, tarih, fiyat | kullanıcının metni ya da gösterdiği kaynak (kendin rakam ekleme); GTA 6 bilgisi için `bilgi-havuzu.md` |
| Klip programları, yayıncı izni | `klipci-rehberi.md` |
| İnsan için tanıtım | `README.md` |

Ne kurulu, ne eksik: `py -3 kur_kontrol.py --json` (hiçbir şey indirmez). Her şey çalışıyor mu: `py -3 kurulum_testi.py` (görüntü gerekmez, ~1 dk). İş açmak: `node panel/is_ac.js` (seçenekler `panel/AJAN-TALIMATI.md`, "İşi açmak").

## Kullanıcıyla konuşma
- Sade Türkçe, kısa cümle. Teknik kelimenin yerine gündelik karşılığını kullan ("render" yerine "videoya çevirme", "bağımlılık" yerine "gereken program").
- Bir şeye başlamadan önce tek cümleyle ne yapacağını ve neden yaptığını söyle.
- Gerçekten gerekmeyen şeyi sorma; en çok bir-iki soru (hangi dosya, kaç klip, Sade mi Editli mi, Short'ta metin ya da ses).
- Altyazıyı sorma. Klip kendiliğinden altyazılı açılır; kullanıcı "altyazısız" derse `node panel/is_ac.js klip` komutuna `--altyazisiz` ekle.
- İndiren, silen, kurulu bir şeyi değiştiren ya da para/kota harcayan her adımdan önce sor; indirmede boyutu (MB/GB) söyle ve "evet"i bekle.
- Hata olunca iki şey söyle: ne oldu, şimdi ne yapılacak. Uzun hata metnini yapıştırma.

## Değişmez kurallar
- Başka bir model, başka bir Claude ya da arka plan ajanı başlatma; zamanlanmış görev kurma. İş, kullanıcının bu sohbetinde, onun gözü önünde yapılır.
- İndirmeden önce boyutu söyle ve "evet" bekle (paket, model, Chrome, ses paketi, güncelleme dahil). `hyperframes render` ve `hyperframes browser path` Chrome yoksa onu kendiliğinden indirir: önce `kur_kontrol.py`'ye bak.
- Kullanıcının dosyalarını silme, taşıma, üstüne yazma (kayıtlar, sesler, `tarzim/`, `referans/`, `panel/isler/`). Kendi ara dosyalarını silmek için bile önce boyutunu söyle ve onay al.
- Yalnız kullanma hakkı olan görüntü. Yayın ya da oyun kaydı: kullanıcının kendi kaydı ya da klip almaya açıkça izin veren bir yayıncının yayını; emin değilsen sor, izin yoksa kesme. Resmî fragman ve oynanış görüntüsü (bilgi Short'ları bununla kurulur): sesi her zaman kapalı. Sesi kapatmak izin vermez; yayımcının video kuralları kullanıcının sorumluluğudur. Bunu kullanıcıya bir kez söyle ve `klipci-rehberi.md` bölüm 3b'yi göster. Bu madde yayıncı iznini gevşetmez: başkasının yayını fragman sayılmaz.
- Panel Claude'u ya da bir modeli hiçbir zaman başlatmaz; onu öyle değiştirme.
- Editli klip ve Short, teknik kontrolden geçince değil `panel/AJAN-TALIMATI.md`'deki "Çıta" bölümünü geçince biter. Çıta: izleyen "bu kurguyu kim yapmış" diye sormalı; "görüntü + altyazı" teslim edilmez (Sade klip hariç, o bilerek düz kesimdir).
- Ortam değişkeni, PATH, global npm paketi gibi bilgisayar ayarlarını değiştiren her adımı önce söyle ve onay al.

## Kullanıcı şunu derse
- **"kur"**, "bu depoyu kur": `KURULUM-AJAN.md`'yi baştan izle. Yarıda kaldıysa yine baştan başla; her adım önce "var mı" diye bakar.
- **"şu videodan 3 klip çıkar: <yol>"**: `panel/AJAN-TALIMATI.md` "İşi açmak": eksikse kaç klip ve Sade mi Editli mi sor, `node panel/is_ac.js klip "<yol>" ...`, sonra A bölümü.
- **"şu metinle bir Liste Short'u yap, videolar şu klasörde"**: aynı yerden: tür, videolar, metin ya da ses; `node panel/is_ac.js short <tür> ...`, sonra B bölümü.
- **"devam et"**, "sıradaki işi yap": `panel/AJAN-TALIMATI.md`, "Devam et" maddesi: sırada bekleyen en eski işi kaldığı aşamadan sürdür.
- **"işe devam et"** (izleme sayfası bunu "Yarıda kaldı", "Bir şey bozuldu" ya da "Claude ses vermiyor" olan işte söyletir) ve **"düzelt ve yeniden dene"** ("Son kontrolden geçmedi" olan işte): işi bul, `node panel/durum.js <iş klasörü> ozet` ile ne olduğunu oku, `node panel/is_ac.js devam "<iş klasörü>"` çalıştır (yarım hazırlığı tamamlar ya da işi ilk bitmemiş aşamadan sana geri verir), o aşamayı nedeni gidererek yeniden yap. Ayrıntı: `panel/AJAN-TALIMATI.md`, "İşe devam et" maddesi.
- **"bu videoyu beğenmedim"**, "şunu değiştir": hangi iş olduğunu bul (yoksa en son teslim edilen), neyi beğenmediğini tek soruyla sor, cevabını `panel/AJAN-TALIMATI.md` D'deki gibi tarz defterine yaz (`--tur ret` ya da `degisiklik`), sonra o değişiklikle yeniden kur, teknik kontrolden geçir ve yeniden aç.
- **"video nerede"**, "ne durumda": `node panel/durum.js panel/isler/<id> ozet`; video hazırsa `node panel/durum.js panel/isler/<id> ac` ile aç ve tam yolunu da yaz (açıldığını göremezsin).
- **"paneli aç"**: `node panel/ac.js` (Windows'ta kullanıcı `Paneli-ac.cmd`'ye çift tıklayabilir); izleme sayfası `http://127.0.0.1:4317`'de açılır. Kapatmak: `node panel/dur.js`.
- **"sorma"**: `py -3 alet/tarz.py kapat` (video sonrası sorular ve kayıt durur). "Tekrar sor", "yine sor": `py -3 alet/tarz.py ac`.
- **"güncelle"**: Klasörde `.git` varsa `git status` ile yerel değişiklik var mı bak, kullanıcıya söyle, onay gelince `git pull`. `.git` yoksa yeni sürümü ayrı bir klasöre indirmesini anlat ve `tarzim/`, `referans/`, `panel/isler/` klasörlerini oraya kendisinin taşımasını söyle (sen silme). Sonra `py -3 kur_kontrol.py`.
- **"yer kalmadı"**, "temizle": iş klasörlerinin boyutlarını listele; kullanıcı adını verip onaylarsa yalnız onları sil.

## Bilmen gerekenler
- Windows 10'da denendi (Python 3.14.5, Node 24.15.0, ffmpeg 8.1.1, HyperFrames 0.8.140). Mac ve Linux denenmedi; oralarda komut uydurma, `KURULUM-AJAN.md` "Windows dışı" bölümüne bak.
- Python Windows'ta her yerde `py -3` ile çağrılır; paketler o Python'a kurulu olmalı.
- Yazıya dökme, ekran kartı kütüphaneleri (isteğe bağlı, ~1,5 GB) bulunamazsa işlemcide çalışır ve bunu açıkça yazar (`UYARI: EKRAN KARTI KULLANILMIYOR`). `py -3 kur_kontrol.py --json` çıktısında üstteki `hazir: true` bunu kapsamaz; üst düzeyde `yazma_cihazi` (`cuda` | `cpu`) ve `uyarilar` verir. Ölçülen (1 saatlik kayıt; Ryzen 5 7500F, RTX 4060 Ti): işlemcide ~11 dk/saat (649 sn; 3 saat ≈ 32 dk, hesap), ekran kartıyla ~2 dk/saat (108 sn). 10 dakikadan uzun bir kayıtta işi açmadan önce kullanıcıya beklenen süreyi söyle. Kütüphaneleri kurmak: `KURULUM-AJAN.md` adım 9.
- Komutlar depo kökünde çalıştırılır. Sesi duyamaz, hareketi izleyemezsin: kareye ve ölçüme bakarsın, bunu kullanıcıya dürüstçe söyle.
