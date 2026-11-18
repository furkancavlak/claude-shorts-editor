# Kurulum: ajan için adım adım yordam

Bu belgeyi kullanıcının kodlama ajanı yürütür. Kullanıcı kod bilmez; sen her adımda ona bir cümleyle ne yaptığını ve neden yaptığını söylersin. Başlangıç noktası boş bir Windows bilgisayar olabilir.

## Değişmezler (her adımda geçerli)
- **İndirmeden ya da kurmadan önce:** ne olduğunu, neden gerektiğini ve boyutunu söyle, "evet" bekle. Kullanıcı "hepsini kur" derse eksiklerin listesini boyutlarıyla bir kez göster, tek "evet" yeter.
- **Asla kendiliğinden yapma:** ekran kartı sürücüsü kurmak; bir komutu "yönetici olarak" çalıştırmaya çalışmak; var olan Python'u ya da Node'u kaldırmak veya yükseltmek; `pip install --upgrade` ile başka paketleri yükseltmek; PATH'i elle düzenlemek; `setx` ile ortam değişkeni yazmak; Chrome'u ya da Whisper modelini onaysız indirmek; herhangi bir dosya silmek. `hyperframes render`, `hyperframes browser path` ve `hyperframes browser ensure` Chrome yoksa onu kendiliğinden indirir: Chrome'u yalnız adım 6'da, onayla indir. `hyperframes doctor`'ı Chrome kurulmadan çalıştırma (eksik Chrome'da ne yaptığı denenmedi).
- **Yeniden çalıştırmak güvenli:** her adım önce "var mı" diye bakar, varsa atlanır. `kur_kontrol.py` hiçbir şeyi değiştirmez. `kurulum_testi.py` her seferinde yeni bir klasöre yazar, hiçbir şey silmez.
- **Denenen yol Windows 10 (x64).** Mac ve Linux için komut uydurma; "Windows dışı" bölümüne bak.
- Komutları deponun kök klasöründe (bu dosyanın olduğu yer) çalıştır.
- **Kurulumdan sonra yeni program görünmeyebilir:** `winget` ile kurulan bir program o an açık olan terminalde bulunamaz (PATH yenilenmez). "tanınmıyor" hatası alırsan kullanıcıdan Claude Code'u (ya da terminali) kapatıp açmasını ve yeniden "bu depoyu kur" yazmasını iste; yordam baştan başlar, kurulu adımlar atlanır.
- **winget hakkında:** ilk kullanımda kaynak sözleşmesini kabul etmeyi sorar ve ajanın terminalinde cevap bekleyip takılabilir. Kullanıcıya söyle; kabul ederse komutlara `--accept-source-agreements --accept-package-agreements` ekle. Bazı kurulumlar (ör. Node.js) Windows'un "değişikliğe izin ver" (UAC) penceresini açar: önceden söyle, "Evet"e kullanıcı basar. `winget` hiç yoksa (eski Windows 10): kullanıcıdan Microsoft Store'da "Uygulama Yükleyici"yi (App Installer) kurmasını ya da güncellemesini iste; olmazsa programları kendi sitelerinden kurmak gerekir (python.org, nodejs.org; ffmpeg için gyan.dev "full" zip + PATH ayarı; bu yol denenmedi).
- **Boş Windows'ta `python` yazma:** Python yokken `python` komutu Microsoft Store penceresini açabilir. Her zaman `py -3` kullan.

## Boyutlar (kullanıcıya söylemek için)
"Kurulu" sütunu denenen bilgisayarda diskte kapladığı yerdir. İndirme boyutu çoğunda bilinmiyor (sıkıştırılmış iner, kurulu hâlinden küçüktür); bilinmeyeni uydurma, "kurulu hâli ~X" de.

| Adım | Ne | Kurulu (denenen bilgisayar) | İndirme |
|---|---|---|---|
| 1 | Python 3.14 | ~140 MB | bilinmiyor |
| 2 | Python paketleri (`requirements.txt` ve onların getirdikleri) | ~550 MB | bilinmiyor |
| 3 | ffmpeg (gyan.dev "full") | ~660 MB | bilinmiyor |
| 4 | Node.js | ~100 MB | bilinmiyor |
| 5 | HyperFrames 0.8.140 | ~110 MB | bilinmiyor |
| 6 | HyperFrames'in Chrome'u (152.0.7977.30) | ~270 MB | bilinmiyor (indirirken toplamı yazar) |
| 7 | Whisper modeli `large-v3-turbo` | 1,6 GB | ~1,6 GB |
| 8 | Türkçe Windows sesi (isteğe bağlı) | bilinmiyor | bilinmiyor |
| 9 | Ekran kartı (CUDA) kütüphaneleri (isteğe bağlı; yalnız `ekran_karti.oneri` `kur` ya da `sor` ise sorulur) | ~1,5 GB | bilinmiyor |

Toplam (zorunlular): diskte ~3,4 GB. Yavaş bir hatta (~12 Mbit) yalnız Whisper modeli 15–20 dakika sürer.
Sonradan büyüyenler: HyperFrames, Chrome'unu ve yazı tiplerini `%USERPROFILE%\.cache\hyperframes` altında ortak tutar; iş klasöründe ayrı bir kare önbelleği (`.cache`) oluşmaz. Denenen bilgisayarda bu klasör 639 MB (iki Chrome sürümü 541 MB + yazı tipi önbelleği 98 MB; yazı tipi önbelleğinin ne zaman dolduğu bu depoda denenmedi). İş klasörleri denemelerde iş başına 150–330 MB tuttu (10 dakikalık kayıt, kısa Short'lar).

## 0. Önce bak
```
py -3 kur_kontrol.py --json
```
- `py` tanınmıyorsa Python ya da onun `py` başlatıcısı yok: adım 1'den başla.
- Çıkış kodu 1 normaldir: zorunlu bir şey eksik demektir, JSON yine basılır.
- Çıktı tek bir JSON: `ogeler[]` içinde her gereksinimin `id`, `baslik`, `sart` (zorunlu mu), `durum` (`var` / `yok` / `eski` / `bilinmiyor`), `surum`, `denenen`, `adim` (bu belgedeki adım no; 0 = depo ya da Windows'un kendi dosyası) ve `not` alanı var. `eksik_sart` boşsa zorunlu her şey kurulu: adım 10'a geç.
- **`hazir: true` ekran kartını kapsamaz.** Üst düzeydeki `yazma_cihazi`'na (`cuda` | `cpu`) ve `uyarilar`'a ayrıca bak: `cpu` ise yazıya dökme işlemcide çalışacak demektir (ayrıntı `gpu` bloğunda). Ekran kartı dosyalarını önerip önermeyeceğini üst düzeydeki `ekran_karti.oneri` söyler: adım 9.
- Kullanıcıya kısa özet ver: "Şunlar hazır, şunlar eksik; inecekler: …, toplam ~… Kurayım mı?" Ekran kartı dosyalarını bu soruya yalnız `ekran_karti.oneri` `kur` ya da `sor` ise, kartın adıyla ve ayrı bir seçenek olarak ekle; `kurma` ya da `kurulu` ise hiç anma.
- PowerShell'de Türkçe harfler bozuk görünürse önce `[Console]::OutputEncoding = [Text.Encoding]::UTF8` çalıştır. İnsan için düz liste: `py -3 kur_kontrol.py` (son satır `SONUC: HAZIR` ya da `SONUC: EKSIK: <id'ler>`).
- `durum: "yok"` olan `adim: 0` öğeleri (Anton, YuNet, GSAP) depo eksik indirilmiş demek: kullanıcıdan depoyu yeniden indirmesini iste.

## 1. Python (3.11 ya da üstü; denenen 3.14.5)
- Kontrol: `py -3 --version`. İyi sonuç: `Python 3.11` ya da üstü. `kur_kontrol` öğeleri `python` ve `py_baslatici` (`py -3`'ün açtığı Python ile kontrolü çalıştıran Python aynı olmalı).
- Kur: önce `winget search --id Python.Python` ile kimlikleri gör, sonra `winget install -e --id Python.Python.3.14` (bu kimlik denenen bilgisayarda doğrulanmadı; listede yoksa en yeni `Python.Python.3.x`'i seç ve kullanıcıya söyle). `winget` yoksa kullanıcıdan python.org'dan Windows kurucusunu indirip kurmasını iste; "py launcher" seçeneği açık kalmalı.
- Sonra: yeni terminalde `py -3 --version`.
- Kalırsa: `py` hâlâ yoksa terminali yeniden aç. Python 3.10 ya da eskisi varsa kaldırma; yanına 3.14 kurmayı öner (`py -3` en yenisini açar).
- 3.14'ü öner: paket sürümleri yalnız 3.14.5'te denendi. Kod 3.11'de de derleniyor, ama 3.11–3.13 için `requirements.txt`'teki sürümlerin hazır paketi olup olmadığı denenmedi.

## 2. Python paketleri
- Kontrol: `kur_kontrol` öğeleri `paket_*` (numpy, PIL, scipy, cv2, faster_whisper, ctranslate2). `cv2` için `eski` = bu OpenCV'de yüz bulucu yok.
- Kur: `py -3 -m pip install -r requirements.txt` (sürümler denenen bilgisayardakiler; faster-whisper ayrıca ctranslate2, av, onnxruntime, tokenizers, huggingface_hub getirir).
- Kalırsa:
  - `No matching distribution found` ya da derleme hatası: bu Python sürümü için hazır paket yok. Sürümleri kendiliğinden gevşetme. Kullanıcıya iki yol sun: Python 3.14 kurmak (denenen) ya da sabit sürümsüz denemek (`py -3 -m pip install numpy Pillow scipy opencv-python faster-whisper`; bu karışım denenmedi).
  - `opencv-python-headless` da kuruluysa ikisi aynı `cv2`'yi verir; kaldırma, `kur_kontrol`'ün `cv2` satırına bak.
  - Yetki hatası: yönetici olarak çalıştırma; `--user` ekleyerek dene ve kullanıcıya söyle.

## 3. ffmpeg ve ffprobe (denenen 8.1.1, gyan.dev "full")
- Kontrol: `ffmpeg -hide_banner -version`. İyi sonuç: ilk satır `ffmpeg version 8.1.1-full_build-www.gyan.dev` gibi. `kur_kontrol`: `ffmpeg`, `ffprobe`, `ffmpeg_filtre` (30/30), `ffmpeg_kodlayici` (3/3).
- Kur: `winget install -e --id Gyan.FFmpeg` (denenen bilgisayarda bu yolla kuruldu). Sonra terminali yeniden aç.
- Kalırsa: filtre eksikse (ör. `drawtext`, `minterpolate`) bu ffmpeg "full" değil. Var olan ffmpeg'i kaldırma; kullanıcıya hangisinin PATH'te önce geldiğini (`where ffmpeg`) göster ve sor.

## 4. Node.js (22 ya da üstü; denenen 24.15.0)
- Kontrol: `node --version` → `v22` ya da üstü; `npm --version` bir sayı.
- Kur: `winget install -e --id OpenJS.NodeJS.LTS`, sonra terminali yeniden aç.
- Kalırsa: Node 18–21 varsa iş açma ve izleme sayfası çalışır ama HyperFrames çalışmaz; yükseltmeyi kullanıcıya sor (başka programları etkileyebilir).

## 5. HyperFrames (sabit sürüm 0.8.140)
- Kontrol: `kur_kontrol` öğesi `hyperframes` (sürümü paketin kendi dosyasından okur, programı çalıştırmaz). Elle: `hyperframes --version` → `0.8.140`.
- Kur: `npm i -g hyperframes@0.8.140` (0.9 ve sonrası denenmedi; `@0.8.140` olmadan kurma).
- Kurduktan sonra kullanıcıya sor: HyperFrames varsayılan olarak anonim kullanım verisi gönderir (`hyperframes telemetry status`). "Kapatayım mı?" Evet derse `hyperframes telemetry disable`. `kurulum_testi.py` kendi çalışmasında zaten kapatır.
- Kalırsa: `hyperframes` tanınmıyorsa terminali yeniden aç; yine yoksa `npm config get prefix` klasörünün PATH'te olup olmadığını kullanıcıya göster (PATH'i kendin düzenleme).

## 6. HyperFrames'in Chrome'u
- Kontrol: `kur_kontrol` öğesi `chrome`. Hiçbir program çalıştırmadan `%USERPROFILE%\.cache\hyperframes\chrome\chrome-headless-shell\win64-152.0.7977.30\` altına bakar. HyperFrames videoya çevirirken bilgisayardaki normal Chrome'u kullanmaz, kendi sürümünü ister.
- Kur (onayla): `hyperframes browser ensure`. Chrome Headless Shell'i yukarıdaki klasöre indirir (kurulu ~270 MB) ve sonunda `Ready to render.` yazar.
- Kalırsa: yarım inmiş bir kopya için `hyperframes browser ensure --force` (yeniden indirir; önce sor). Hazır bir chrome-headless-shell varsa `HYPERFRAMES_BROWSER_PATH` ortam değişkeniyle gösterilebilir (denenmedi).

## 7. Whisper modeli (zorunlu; `large-v3-turbo`, ~1,6 GB)
- Kontrol: `kur_kontrol` öğesi `whisper_model`. İyi sonuç: `large-v3-turbo (1618 MB)`. Yalnız yerel önbelleğe bakar, internete çıkmaz.
- Kur (onayla): `py -3 -c "from faster_whisper import download_model; download_model('large-v3-turbo')"`. Hugging Face önbelleğine iner (`%USERPROFILE%\.cache\huggingface\hub`; `HF_HOME` değişkeni bu yeri değiştirir). Kullanıcıya süreyi söyle. Senin komut süre sınırın indirmeden kısaysa (Claude Code'da tek komut en çok 10 dk) komutu arka planda çalıştır (bir ajan değil, yalnız komut) ve bitince `kur_kontrol` ile doğrula.
- Kalırsa: yarıda kesildiyse aynı komutu yeniden çalıştır (kaldığı yerden devam edip etmediği denenmedi), sonra `kur_kontrol` model.bin boyutunu doğrular (`bilinmiyor` + "yarım inmiş olabilir" ise yeniden). `large-v3-turbo` olmazsa `medium` (~1,5 GB) da çalışır; yalnız kullanıcı isterse.
- Motor modeli hiçbir zaman kendisi indirmez: model yoksa `node panel/is_ac.js` iş açmayı reddeder (çıkış kodu 3, `KURULUM EKSIK: Whisper modeli`).

## 8. Türkçe yer tutucu ses (isteğe bağlı, yalnız Windows)
- Ne için: kullanıcı ses vermeden metin yazarsa deneme sesi; bir de `kurulum_testi.py`'nin konuşan cümlesi. Gerçek ses her zaman kullanıcının kendi kaydıdır.
- Kontrol: `kur_kontrol` öğesi `turkce_ses` (ör. `Microsoft Tolga`).
- Kur: otomatik yapma. Kullanıcıya anlat: Windows Ayarlar → Saat ve dil → Konuşma → Ses ekle → Türkçe. Boyutu bilinmiyor. Yoksa deneme yine çalışır (ses yerine ton kullanır, kelime kontrolünü atlar).

## 9. Ekran kartıyla yazıya dökme (isteğe bağlı; ne söyleyeceğini `ekran_karti` belirler)
**Bu adımı atlama, ama her bilgisayarda sorma.** `py -3 kur_kontrol.py --json` kartı kendisi tanır (önce `nvidia-smi`, yoksa sistemin aygıt listesi; hiçbir şey indirmez) ve üst düzeyde `ekran_karti` verir: `ad`, `nvidia` (`true` | `false` | `null` = tanınamadı), `bellek_gb`, `oneri`, `neden` (kullanıcıya söylenecek gerekçe).

- **Ne:** Whisper'ın NVIDIA ekran kartında çalışması için 9 dosya (CUDA 12 cuBLAS + cuDNN 9; adları `kod/ses_yazi.py` içinde `CUDA_DLL`), birlikte ~1,5 GB. Kart ve sürücü tek başına yetmez: dosyalar bulunamazsa yazıya dökme işlemcide çalışır ve `UYARI: EKRAN KARTI KULLANILMIYOR` satırını süre tahminiyle yazar. `hazir: true` bunu kapsamaz (denenen bilgisayarda `hazir: true` iken işlemcide çalıştı).
- **`oneri`'ye göre:**
  - `kurma` (NVIDIA yok, macOS ya da kartın belleği modelden küçük): ekran kartı dosyalarından hiç söz etme, sorma. Tek cümle yeter, ör. "Ekran kartın NVIDIA değil; yazıya dökme işlemcide çalışır, 1 saatlik kayıt ~11 dakika sürer." (gerekçe `neden`'de).
  - `kurulu`: dosyalar zaten var, yazıya dökme ekran kartında çalışır. Sorma.
  - `kur`: bir kez, boyutuyla sor: "Ekran kartın <ad>; ~1,5 GB'lık dosyalarla uzun yayın kayıtları ekran kartında yazıya dökülür: 1 saatlik kayıt ~11 dakika yerine ~2 dakika. Yalnız Short yapacaksan gerekmez (Short'ta ses kısa). Kurayım mı?" İndirme her zaman "evet"le.
  - `sor`: önce `neden`'i söyle (kart tanınamadı, `nvidia-smi` çalışmıyor ya da bellek az olabilir), sonra aynı soruyu sor. `nvidia-smi` çalışmıyorsa dosyalar sürücüsüz işe yaramaz; NVIDIA sürücüsünü sen kurma, kullanıcı kurar.
  - "Hayır" derse üstelemeden geç; her uzun kayıttan önce beklenen süreyi söylersin (işlemcide saatlik kayıt başına ~11 dk).
- **Ölçülen** (denenen bilgisayar: Ryzen 5 7500F, RTX 4060 Ti 16 GB):

| Ses | Ekran kartıyla | İşlemcide |
|---|---|---|
| 5 saniyelik cümle (Short) | gerek yok | ~6 sn (model açıldıktan sonra) |
| 10 dakika | 22–36 sn | 157 sn (bilgisayar o sırada başka iş de yapıyordu) |
| 1 saat | 108 sn (~2 dk) | 649 sn (~11 dk) |
| 3 saat | ~5,5 dk (1 saatlikten hesap) | ~32 dk (1 saatlikten hesap) |

- **Ayrıntı `gpu` bloğunda** (`yazma_cihazi: "cuda"` ise yapacak bir şey yok): `eksik_dll` bulunamayan dosyalar, `bulunan_klasorler` bulunanların yeri ve nereden bulunduğu, `oneri` işlemcide çalışacaksa okunacak cümle, `yazma_suresi` ölçülen süreler; ayrıca `kart`, `surucu`, `bellek_mb`, `ct2_cuda_aygit`, `whisper_cuda_dll`.
- **"Evet" derse:** NVIDIA sürücüsü (`nvidia-smi` çalışmalı; sürücüyü sen kurma) ve yukarıdaki 9 dosya gerekir.
  - Kütüphaneler bulunduğu yerden kendiliğinden kullanılır: bu Python'un `nvidia-*` ya da `torch` paketleri, `CUDA_PATH`, Program Files altındaki CUDA 12 / cuDNN 9 kurulumu, PATH. Ayar gerekmez.
  - Başka yerdeyse (ör. başka bir programın Python ortamındaki `torch\lib`; başka ortamlar aranmaz) `WHISPER_CUDA_DLL` ortam değişkeni o klasörü gösterir (birden çok klasör `;` ile). Bu bir bilgisayar ayarıdır: önce kullanıcıya söyle, onayını al. Yeni açılan terminallerde geçerli olur: kullanıcıdan Claude Code'u kapatıp açmasını iste (izleme sayfası açıksa onu da kapatıp yeniden aç).
  - Dosyalar hiç yoksa ve kullanıcı isterse (denenmemiş yol): `py -3 -m pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"`; bu Python'un paketlerine indiği için ayar gerekmez, `kur_kontrol` ile bak. Denenen bilgisayarda bu dosyalar bir PyTorch kurulumunun `torch\lib` klasöründen geldi.
- Doğrulama: `py -3 kod/ses_yazi.py --cihaz` (model açmaz, birkaç saniye): `CIHAZ cuda (ekran karti); kutuphaneler: ...` ya da `CIHAZ cpu. UYARI: ...` (eksik dosya sayısı ve ilk üçünün adı). `py -3 kur_kontrol.py --json` → `yazma_cihazi: "cuda"`. Yazıya dökülen her işin `ses.json` / `yazi.json`'unda `model` alanı `large-v3-turbo/cuda` ya da `.../cpu` der.

## 10. Son kontrol
`py -3 kur_kontrol.py --json` → `"hazir": true` ve `eksik_sart: []`. Değilse eksik öğenin `adim`'ına dön. `gpu.hazir` bu sonuca girmez: adım 9'u `ekran_karti.oneri`'ye göre yaptıysan yeter.

## 11. Kendi kendine deneme (görüntü gerekmez)
```
py -3 kurulum_testi.py
```
- Ne yapar: 8 saniyelik bir deneme görüntüsü ve Türkçe bir cümle üretir; bunlarla gerçek iş açma komutundan (`node panel/is_ac.js short tek_bilgi ...`) bir deneme işi açar, o da cümleyi yazıya döker (iş, test klasörünün içinde açılır; `panel/isler/`'e bir şey yazılmaz). Sonra video bilgisi, kare kâğıdı, kamera bulucu, çekim kesme, boş sahne + bir satır hareketli yazı, videoya çevirme, ses karıştırma ve teknik kontrolden geçirir. Denenen bilgisayarda ~1 dakika sürdü (Whisper işlemcide).
- Çıktı `kurulum-testi/<tarih-saat>/` altında (~22 MB; git'e girmez). Her parça için bir satır: `GECTI`, `KALDI` ya da `ATLANDI` ve sade bir neden. Son satır `SONUC: GECTI`, `SONUC: KALDI: <parçalar>` ya da `SONUC: EKSIK: <atlananlar>` (bir şey kurulmadığı için atlandı). Aynısı `sonuc.json`'da; her komutun tam çıktısı `gunluk/`.
- Chrome yoksa videoya çevirme adımı **atlanır** (çalışsa Chrome'u kendisi indirirdi). Whisper modeli yoksa yazıya dökme atlanır, kalan parçalar yine denenir.
- `KARELER` satırındaki resme kendin bak: 8 kare yan yana, renkli deneme deseni (sarı-mavi şeritler) ve ilk kare dışında ortada "KURULUM DENEMESİ ÇALIŞIYOR" yazısı (Türkçe harfler tam) görünmeli. `VIDEO` satırındaki yolu kullanıcıya ver; isterse açıp dinlesin.
- `KALDI` ise o parçanın `gunluk/<no>-<ad>.txt` dosyasını oku; aşağıdaki tabloya bak. Düzeltip testi yeniden çalıştır (yeni klasöre yazar). Eski deneme klasörlerini silmek kullanıcının onayıyla.
- Kullanıcıya her parçayı sade Türkçe söyle, ör. "Yazıya dökme çalışıyor, cümleyi doğru duydu. Videoya çevirme çalışıyor. Teknik kontrol geçti."

## 12. Bitiş
Kullanıcıya söyle: neler kuruldu, isteğe bağlı olup kurulmayanlar (Türkçe ses; ekran kartı kütüphaneleri kurulmadıysa ya da `kurma` geldiyse dosyaları anmadan yalnız "uzun kayıtta yazıya dökme işlemcide çalışır, saatlik kayıt başına yaklaşık 11 dakika sürer" diye) ve nasıl kullanacağı: "Ne istediğini bana yaz, örneğin 'şu videodan 3 klip çıkar: <dosyanın yolu>' ya da 'şu metinle bir Liste Short'u yap, videolar şu klasörde'. İlerlemeyi görmek istersen 'paneli aç' de." İlk işi birlikte yapmayı öner.

## Sık hatalar
| Görülen | Neden | Ne yap |
|---|---|---|
| `py` / `ffmpeg` / `node` / `hyperframes` tanınmıyor | kurulu değil ya da terminal eski | ilgili adım; kuruluysa terminali (Claude Code'u) yeniden aç |
| `No matching distribution found for numpy==...` | Python sürümüne uygun paket yok | adım 2 "Kalırsa" |
| `HATA: yerel Whisper modeli yok (indirme yapilmaz)` | model inmemiş | adım 7 |
| `node panel/is_ac.js` çıktısında `KURULUM EKSIK: ...` (çıkış kodu 3) | listedeki şey kurulu değil; iş açılmadı | ilgili adım, sonra aynı komutu yeniden çalıştır |
| render sırasında `Downloading Chrome Headless Shell` | Chrome yoktu | kullanıcı onaylamadıysa durdur (Ctrl+C), adım 6 |
| `font bulunamadi` (sahne_baslat) | Windows yazı tipi yok | `--font <kurulu bir .ttf>`; Windows dışında beklenir |
| `kamera_bul` çıktısında `[ WARN:0@...] ... Targets are not supported` | OpenCV 5'in bilgi notu | zararsız |
| `kur_kontrol`'de `py_baslatici: bilinmiyor` | `py -3` başka bir Python açıyor | paketleri o Python'a kur ya da hangisinin kullanılacağını kullanıcıyla seç |

## Windows dışı (Mac, Linux): denenmedi
Bu yollar hiç denenmedi; komut uydurma. Kullanıcı yine de denemek isterse adım adım, her adımda onayla ilerle ve her hatayı olduğu gibi söyle. Bilinen Windows'a bağlı yerler:
- Python `py -3` ile çağrılır; iş açma komutu ve izleme sayfası Windows dışında `python3` kullanır (`PANEL_PYTHON` değişkeni değiştirir).
- Kare kâğıtlarının etiketleri ve bazı yazılar `C:\Windows\Fonts` içindeki Arial / Segoe UI / Bahnschrift'i bekler (`kod/bak.py`, `kod/serit.py`, `alet/_ortak.py`, `alet/sahne_baslat.py`, `kod/motor.py`); bu yazı tipleri olmadan bu aletler hata verebilir.
- Yer tutucu ses (`kod/tts_tr.ps1`) yalnız Windows'ta var. `Paneli-ac.cmd` / `Paneli-kapat.cmd` yalnız Windows; yerine `node panel/ac.js` / `node panel/dur.js`.
- Ekran kartı için dosya adları (`*.dll`) Windows'a göre; Linux'ta karşılığı denenmedi.
- `kur_kontrol.py` ve `kurulum_testi.py` Windows dışında da çalışacak biçimde yazıldı ama orada hiç çalıştırılmadı. Çalışsalar bile "var" demeleri o sistemde motorun çalışacağı anlamına gelmez.
