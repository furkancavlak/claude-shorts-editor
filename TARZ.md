# Tarz defteri: videolarına verdiğin cevapları hatırlayan küçük defter

## Ne yapar
Bir video bittiğinde kurguyu yapan Claude (ya da hangi modeli kullanıyorsan o) sana tek bir soru sorar: "En çok neyi beğendin? 'Geç' dersen sormam." Bir şeyi beğenmezsen: "Neyi beğenmedin? Hep mi böyle yapmayayım, yalnız bu videoda mı?" Üç videoda bir, ikinci bir soru gelebilir: "Bir dahakinde neyi farklı yapayım?"

Cevabın, söylediğin kelimelerle deftere yazılır. Claude'un o sözden ne anladığı ayrı bir yere yazılır; senin sözün değiştirilmez.

Bir şey hemen kural olmaz:
- Aynı şeyi **üç ayrı videoda** söylersen Claude önce sorar: "Üç videodur … diyorsun, hep böyle yapayım mı?" "Evet" dersen kalıcı tercih olur, "hayır" dersen sayaç sıfırlanır.
- "**Hep** böyle yap" ya da "**asla** yapma" dersen bir kez teyit eder ve hemen yazar.
- İki cevabın birbirini tutmazsa (bir videoda "yazılar büyük olsun", başkasında "küçük kalsın") Claude ikisini sana gösterir, seçmez.
- Sessizce "okey" demen zayıf bir işarettir; hiçbir şeyi saymaz.
- Claude kendi videosuna kendisi not verip "öğrenmez". Defterdeki her şey senin söylediklerinden gelir.

Her yeni işte Claude yalnız kısa özeti okur. Özetin ilk satırı hep aynıdır: "Bunlar ipucudur, kural değil: bugünkü istek her zaman üstündür; geçmiş videolara benzemeye çalışma." Ayrıca Claude her videoda notlarda olmayan bir şeyi bilerek dener ve son mesajda ne denediğini söyler. Beğenirsen deftere girer, beğenmezsen "denendi, tutmadı" diye yazılır. Böylece video eski videoların kopyasına dönmez.

## Ne nerede durur (`tarzim/` klasörü)
| Dosya | İçinde ne var |
|---|---|
| `ozet.md` | Her işin başında okunan tek dosya (en çok ~60 satır): onayladığın tercihler, denenip tutmayanlar, çelişkiler. |
| `gunluk.md` | Bütün cevapların, tarihli ve hangi videoya verildiğiyle. Yalnız eklenir, silinmez. |
| `reddedilenler.md` | Beğenmediğin ve denenip tutmayan şeyler, kaç kez. |
| `ornekler/` | Açıkça beğendiğin en çok 5 videonun sahne dosyaları; görüntü ve ses yoktur, her birinde "neden beğenildi" notu var. Claude bunlara yalnız takılırsa bakar. |
| `aletlerim/` | Senin için yazılmış küçük aletler ve değişiklik günlüğü. Ortak `alet/` klasörü değişmez; depoyu güncellediğinde çakışmaz. |
| `yedek/` | Değişmeden önceki özetler ve kenara alınan dosyalar. |
| `ayar.json` | İsteğe bağlı: sayıları değiştirmek için (aşağıda). |

Hepsi **yalnız senin bilgisayarında** kalır. `tarzim/` `.gitignore`'da: GitHub'a gitmez, depoyu paylaşsan da gitmez. Defteri `alet/tarz.py` yazar; dosyaları elle değiştirirsen o hali `yedek/`'e alınır ve özet yeniden yazılır.

## Bakım
Arka planda hiçbir şey çalışmaz, zamanlanmış görev yoktur. Özet 60 satırı geçerse ya da her 10 videoda bir, Claude işe başlamadan önce bir bakım listesi gösterir: birleştirilebilecek konular, 90 gündür tekrar etmediğin tercihler ("eski" saymayı önerir), 180 gündür tekrar etmediklerin (kaldırmayı önerir), fazla örnekler. Sen onaylamadan hiçbir şey değişmez. Bir şeyin kaldırılması için ayrıca açıkça onay vermen gerekir. Önceki hali `yedek/`'te kalır.

## Sayılar
3 video, 60 satır, 10 video, 5 örnek, 90/180 gün, "ikinci soru 3 videoda bir": hepsi tahmindir, ölçülmüş değil. Değiştirmek için `tarzim/ayar.json` yaz, örnek: `{"esik_video": 4, "bakim_her": 15}`. Adların tam listesi `alet/tarz.py` dosyasının başında.

## Kapatmak
- Claude'a "**sorma**" de. Ya da `tarzim/` içine `KAPALI` adlı boş bir dosya koy. Bundan sonra soru sorulmaz, bir şey yazılmaz, özet okunmaz.
- Açmak için "tekrar sor" de (`py -3 alet/tarz.py ac`) ya da `KAPALI` dosyasını sil.
- Defterin tamamen gitmesini istersen `tarzim/` klasörünü kendin silebilirsin. Claude onu senin onayın olmadan silmez.

## Ne söz vermiyor
Bu defter yalnız söylediklerini hatırlar ve sana sorarak tercihe çevirir. Videoların zamanla belli bir tarza oturacağını ölçmedik; elimizdeki tek şey bu mekanizma.
