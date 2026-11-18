# -*- coding: utf-8 -*-
"""tarz.py - the user's own style notebook (tarzim/). After a delivered video the agent asks ONE question, writes
the user's exact words down (its own reading kept in a separate field), and turns a reading into a standing
preference only when the same one came back in 3 different videos AND the user said yes. Nothing runs in the
background: the agent calls these commands inside the user's chat. UTF-8 without BOM. Nothing is deleted unless a
command is given --sil; replaced files go to tarzim/yedek/.

  ozet     read at the start of every job (plus "tidy-up due" / "turned off" notes):
             py -3 alet/tarz.py ozet
  soru     what to ask after delivery (and whether the second question is allowed this time):
             py -3 alet/tarz.py soru --is 261118-0102-ab
  ekle     write one answer; the user's words (--soz) and your reading (--cikarim) stay apart:
             py -3 alet/tarz.py ekle --is 261118-0102-ab --tur begeni --soz "kesmeler hızlıydı" --cikarim "hızlı kesimi seviyor" --konu kesim-ritmi=hizli
  say      how many different videos gave the same reading, and what is waiting for the user:
             py -3 alet/tarz.py say
  tercih   write the user's answer to a threshold / "hep-asla" / contradiction question:
             py -3 alet/tarz.py tercih --konu kesim-ritmi=hizli --cevap evet --soz "evet, hep böyle" --is 261118-0102-ab
  ornek    keep an approved job's scene source (no media) as an example, with why it was approved:
             py -3 alet/tarz.py ornek --is 261118-0102-ab --kaynak panel/isler/261118-0102-ab/kurgu/sahne --neden "ritmi beğendi"
  aletim   keep a tool you wrote for this user in tarzim/aletlerim/ (change log; alet/ is not touched):
             py -3 alet/tarz.py aletim --dosya panel/isler/<id>/kurgu/benim_aletim.py --neden "neden gerekti"
  bakim    list what a tidy-up would do; changes only with --uygula after the user agreed:
             py -3 alet/tarz.py bakim
  kapat    turn the notebook off (empty file tarzim/KAPALI): no questions, no records:
             py -3 alet/tarz.py kapat
  ac       turn it back on (KAPALI is moved to tarzim/yedek/):
             py -3 alet/tarz.py ac
  goster   READ ONLY, for the panel: what the notebook holds (--json for a machine-readable view):
             py -3 alet/tarz.py goster --json

--konu is "<subject>=<what the user wants>" in short words, e.g. yazi-boyutu=kucuk, muzik=yok. Reuse a subject
that "say" lists instead of inventing a new spelling. Every command takes --klasor <folder> (default: tarzim/ in the
engine root). The numbers below are guesses, not measurements; tarzim/ayar.json overrides.
"""
import argparse, difflib, hashlib, json, os, re, shutil, sys
from datetime import datetime

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # engine root
AYAR = {
    "esik_video": 3,        # same reading in this many different videos -> ask whether it is a standing preference
    "ozet_satir": 60,       # ozet.md longer than this -> offer a tidy-up at the start of a job
    "bakim_her": 10,        # ... or every this many videos
    "ornek_en_cok": 5,      # examples kept in ornekler/
    "eski_gun": 90,         # a preference not confirmed for this many days -> marked stale (user agrees)
    "sil_gun": 180,         # ... -> offered for removal (user agrees)
    "yedek_tut": 5,         # ozet backups kept; older ones are offered for removal (--sil)
    "ikinci_soru_her": 3,   # the second question at most once every this many videos
    "reddedilen_ozette": 8, # "tried, did not work" lines shown in ozet.md
}
ILK_SATIR = "Bunlar ipucudur, kural değil: bugünkü istek her zaman üstündür; geçmiş videolara benzemeye çalışma."
TURLER = ["sessiz", "begeni", "degisiklik", "ret", "cevap2", "deney"]   # a user's reaction to a delivered video
SAYILAN = {"begeni", "degisiklik", "ret", "cevap2"}                      # + deney with sonuç "tuttu"
ALANLAR = ["iş", "tür", "güç", "konu", "kapsam", "sonuç", "cevap", "soru2", "söz", "çıkarım", "not"]
METIN_UZ = {".html", ".htm", ".js", ".mjs", ".css", ".json", ".md", ".txt", ".py", ".svg"}
ATLA_KLASOR = {"render", ".cache", "node_modules", "__pycache__", "kaynak", "media", "medya"}
SAYI = {2: "İki", 3: "Üç", 4: "Dört", 5: "Beş"}
TUR_AD = {"ret": "beğenmedi", "degisiklik": "değişiklik istedi", "deney": "denendi, tutmadı"}


def simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def bos_yol(yol):
    """Backup target that never overwrites: two backups in the same second get -2, -3 ..."""
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    kok, uz = os.path.splitext(yol)
    if uz not in (".md", ".py", ".js", ".json", ".txt", ".html", ".css"):
        kok, uz = yol, ""
    i, aday = 2, yol
    while os.path.exists(aday):
        aday, i = "%s-%d%s" % (kok, i, uz), i + 1
    return aday


def yaz(yol, metin):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        f.write(metin)


def konu_ayir(k):
    if not k or "=" not in k:
        return None, None
    a, b = k.split("=", 1)
    return a.strip(), b.strip()


def konu_temiz(k):
    k = re.sub(r"\s+", "-", (k or "").strip().lower())
    if k.count("=") != 1 or k.startswith("=") or k.endswith("="):
        sys.exit('HATA: --konu "<konu>=<istenen>" biçiminde olmalı, ör. yazi-boyutu=kucuk')
    return k


class Defter:
    def __init__(self, klasor):
        self.k = os.path.abspath(klasor or os.path.join(KOK, "tarzim"))
        self.ayar = dict(AYAR)
        p = self.yol("ayar.json")
        if os.path.exists(p):
            try:
                self.ayar.update(json.load(open(p, encoding="utf-8-sig")))
            except Exception as e:
                print("UYARI: ayar.json okunamadı (%s); varsayılan sayılar kullanıldı." % e)

    def yol(self, *a):
        return os.path.join(self.k, *a)

    def var(self):
        return os.path.exists(self.yol("gunluk.md"))

    def kapali(self):
        return os.path.exists(self.yol("KAPALI"))

    def hazirla(self):
        for d in ("ornekler", "aletlerim", "yedek"):
            os.makedirs(self.yol(d), exist_ok=True)
        if not self.var():
            yaz(self.yol("gunluk.md"), "# Tarz günlüğü\nYalnız eklenir; düzeltme yeni satırla yapılır. söz = kullanıcının "
                "birebir sözü, çıkarım = ajanın yorumu (ayrı). güç: zayıf = sessiz okey, orta = tek yorum, "
                "güçlü = açık \"hep / asla\".\n\n")

    # ---------------------------------------------------------------- the log
    def kaydet(self, alan):
        parca = [simdi()]
        for a in ALANLAR:
            v = alan.get(a)
            if v is None or v == "":
                continue
            v = re.sub(r"\s+", " ", str(v)).replace("|", "/").strip()
            parca.append("%s: %s" % (a, '"%s"' % v.replace('"', "'") if a == "söz" else v))
        satir = "- " + " | ".join(parca)
        with open(self.yol("gunluk.md"), "a", encoding="utf-8", newline="\n") as f:
            f.write(satir + "\n")
        return satir

    def gunluk(self):
        out = []
        if not self.var():
            return out
        for s in open(self.yol("gunluk.md"), encoding="utf-8-sig"):
            s = s.rstrip("\n")
            if not s.startswith("- "):
                continue
            p = s[2:].split(" | ")
            g = {"tarih": p[0]}
            for x in p[1:]:
                if ": " in x:
                    a, v = x.split(": ", 1)
                    if a in ALANLAR:
                        g[a] = v
            if len(g.get("söz", "")) >= 2 and g["söz"][0] == g["söz"][-1] == '"':
                g["söz"] = g["söz"][1:-1]
            out.append(g)
        return out

    # ---------------------------------------------------------------- everything derived from the log
    def hesap(self):
        G = self.gunluk()
        ad = {}                                   # merged subject names (tidy-up): old -> new
        for g in G:
            if g.get("tür") == "bakim" and g.get("sonuç") == "birlestir" and ">" in g.get("konu", ""):
                a, b = g["konu"].split(">", 1); ad[a.strip()] = b.strip()
        for g in G:
            k, y = konu_ayir(g.get("konu"))
            if k and g.get("tür") != "bakim" or (k and g.get("sonuç") in ("eski", "kaldir")):
                while k in ad:
                    k = ad[k]
                g["k"], g["y"] = k, y
        aktif, son_karar, gozlem, tum = {}, {}, {}, {}     # gozlem: since the last decision; tum: all time
        for i, g in enumerate(G):
            t, k, y = g.get("tür"), g.get("k"), g.get("y")
            if not k:
                continue
            if t == "karar":
                son_karar[k] = i
                once = gozlem.pop(k, {}).get(y, [])   # a decision starts the count again
                if g.get("cevap") == "evet":       # shown with what the user said about it, and the yes itself
                    aktif[k] = {"yon": y, "kuruldu": g["tarih"], "son": g["tarih"], "eski": False, "sayi": 0,
                                "soz": once[-1][1].get("söz", "") if once else g.get("söz", ""), "cevap": g.get("söz", ""),
                                "acik": "açık söz" in g.get("not", "")}
                elif aktif.get(k, {}).get("yon") == y:
                    aktif.pop(k)
            elif t == "bakim":
                if g.get("sonuç") == "eski" and aktif.get(k, {}).get("yon") == y:
                    aktif[k]["eski"] = True
                if g.get("sonuç") == "kaldir" and aktif.get(k, {}).get("yon") == y:
                    aktif.pop(k); son_karar[k] = i; gozlem.pop(k, None)
            elif (t in SAYILAN or (t == "deney" and g.get("sonuç") == "tuttu")) and g.get("kapsam") != "bu-video":
                gozlem.setdefault(k, {}).setdefault(y, []).append((g.get("iş", "?"), g))
                tum.setdefault(k, {}).setdefault(y, set()).add(g.get("iş", "?"))
                if aktif.get(k, {}).get("yon") == y:
                    aktif[k].update(son=g["tarih"], eski=False)
        for k, a in aktif.items():                # how many videos stand behind a preference (all time)
            a["sayi"] = len(tum.get(k, {}).get(a["yon"], ()))
        videolar, soru2 = [], []
        son_bakim = -1
        for i, g in enumerate(G):
            if g.get("tür") in TURLER and g.get("iş") and g["iş"] not in videolar:
                videolar.append(g["iş"])
            if g.get("soru2") == "evet" and g.get("iş"):
                soru2.append(g["iş"])
            if g.get("tür") == "bakim" and g.get("sonuç") == "tamam":
                son_bakim = i
        bakimdan_beri = len({g.get("iş") for g in G[son_bakim + 1:] if g.get("tür") in TURLER and g.get("iş")})
        esik, celiski, acik = [], [], []
        for k, yonler in gozlem.items():
            for y, L in yonler.items():
                isler = sorted({i for i, _ in L}, key=lambda x: [j for j, _ in L].index(x))
                if len(isler) >= self.ayar["esik_video"] and aktif.get(k, {}).get("yon") != y:
                    sozler = {i: g.get("söz", "") for i, g in L}          # the user's own words, one per video
                    esik.append((k, y, isler, " / ".join('"%s" (%s)' % (sozler[i], i) for i in isler)))
                for _, g in L:
                    if g.get("güç") == "güçlü" and aktif.get(k, {}).get("yon") != y and (k, y) not in [(a, b) for a, b, _ in acik]:
                        acik.append((k, y, g.get("söz", "")))
            taraf = {y: L for y, L in yonler.items()}
            if k in aktif:
                taraf.setdefault(aktif[k]["yon"], [])
            # liking two different things is not a contradiction; asking for one while another was asked for
            # (change request, rejection, answer to "what should I do differently", or a standing preference) is
            yonlendiren = k in aktif or any(g.get("tür") in ("degisiklik", "ret", "cevap2") for L in yonler.values() for _, g in L)
            if len(taraf) >= 2 and yonlendiren:   # the preference side counts its videos of all time
                celiski.append((k, [(y, aktif[k]["sayi"] if y == aktif.get(k, {}).get("yon") else len({i for i, _ in L}),
                                     (L[-1][1].get("söz", "") if L else aktif[k]["soz"]),
                                     y == aktif.get(k, {}).get("yon")) for y, L in taraf.items()]))
        return {"G": G, "aktif": aktif, "gozlem": gozlem, "videolar": videolar, "soru2": soru2, "esik": esik,
                "celiski": celiski, "acik": acik, "bakimdan_beri": bakimdan_beri,
                "son_bakim": G[son_bakim]["tarih"][:10] if son_bakim >= 0 else "yok"}

    # ---------------------------------------------------------------- the two files people read
    def ozet_metni(self, h):
        L = [ILK_SATIR, "(Bu dosyayı alet/tarz.py yazar; elle değiştirme. Kullanıcının ham sözleri gunluk.md'de.)", "",
             "## Kalıcı tercihler (kullanıcı \"evet\" dedi)"]
        if not h["aktif"]:
            L.append("- henüz yok")
        for k, a in sorted(h["aktif"].items()):
            gun = (datetime.now() - datetime.strptime(a["son"][:10], "%Y-%m-%d")).days
            dayanak = "açık söz" if a["acik"] and a["sayi"] < self.ayar["esik_video"] else "%d video" % a["sayi"]
            L.append('- %s = %s · "%s"%s · %s · son doğrulama %s%s' % (k, a["yon"], a["soz"],
                     ' (cevap: "%s")' % a["cevap"] if a["cevap"] and a["cevap"] != a["soz"] else "", dayanak, a["son"][:10],
                     " · ESKİ (%d gün)" % gun if a["eski"] else ""))
        red = self.reddedilen(h)
        tutmadi = [r for r in red if r["tur"] == "deney"][-self.ayar["reddedilen_ozette"]:]
        if tutmadi:
            L += ["", "## Denendi, tutmadı (aynısını yeniden deneme)"]
            L += ['- %s = %s · "%s" · %s' % (r["k"], r["y"], r["soz"], r["son_is"]) for r in tutmadi]
        if h["celiski"]:
            L += ["", "## Çelişkiler (kullanıcıya ikisini göster, sen seçme)"]
            for k, taraf in h["celiski"]:
                L.append("- %s: " % k + " <-> ".join('"%s"%s (%d video, son söz: "%s")' % (y, " [kalıcı tercih]" if ak else "", n, s)
                                                     for y, n, s, ak in taraf))
        L += ["", "## Sayaç", "%d video · son bakım: %s · bakım önerisi: %d videoda bir ya da %d satırı geçince" % (
            len(h["videolar"]), h["son_bakim"], self.ayar["bakim_her"], self.ayar["ozet_satir"])]
        return "\n".join(L) + "\n"

    def reddedilen(self, h):
        grup = {}
        for g in h["G"]:
            t = g.get("tür")
            if not g.get("k") or not (t in ("ret", "degisiklik") or (t == "deney" and g.get("sonuç") == "tutmadi")):
                continue
            anahtar = (g["k"], g["y"], t, g.get("kapsam", "genel"))
            r = grup.setdefault(anahtar, {"k": g["k"], "y": g["y"], "tur": t, "kapsam": g.get("kapsam", "genel"), "isler": []})
            if g.get("iş") not in r["isler"]:
                r["isler"].append(g.get("iş"))
            r.update(soz=g.get("söz", ""), son_is=g.get("iş", "?"), tarih=g["tarih"][:10])
        return list(grup.values())

    def yeniden_yaz(self):
        """ozet.md and reddedilenler.md are views of gunluk.md; a hand edit is kept in yedek/ before it is replaced"""
        h = self.hesap()
        durum_yol = self.yol(".tarz-durum.json")
        try:
            durum = json.load(open(durum_yol, encoding="utf-8"))
        except Exception:
            durum = {}
        red = self.reddedilen(h)
        reddedilen_metin = ("# Reddedilenler\nKullanıcının beğenmediği ve denenip tutmayan şeyler (alet/tarz.py yazar). "
                            "Tek red kural değildir; \"hep / asla\" dediyse kalıcı tercihe girer.\n\n" +
                            ("".join('- %s = %s · %s · %s · %d kez · son %s %s · "%s"\n' % (
                                r["k"], r["y"], TUR_AD[r["tur"]], "yalnız o videoda" if r["kapsam"] == "bu-video" else "genel",
                                len(r["isler"]), r["son_is"], r["tarih"], r["soz"]) for r in red) or "- henüz yok\n"))
        notlar = []
        for ad, metin in (("ozet.md", self.ozet_metni(h)), ("reddedilenler.md", reddedilen_metin)):
            yol = self.yol(ad)
            if os.path.exists(yol):
                eski = open(yol, encoding="utf-8-sig").read()
                if durum.get(ad) and hashlib.sha1(eski.encode("utf-8")).hexdigest() != durum[ad] and eski != metin:
                    y = bos_yol(self.yol("yedek", ad.replace(".md", "-elle-%s.md" % datetime.now().strftime("%Y%m%d-%H%M%S"))))
                    shutil.copy2(yol, y)
                    notlar.append("NOT: %s elle değiştirilmiş; o hali %s altına alındı. Kalıcı bir şey için tarz.py tercih kullan." % (ad, y))
            yaz(yol, metin)
            durum[ad] = hashlib.sha1(metin.encode("utf-8")).hexdigest()
        json.dump(durum, open(durum_yol, "w", encoding="utf-8"), indent=1)
        for n in notlar:
            print(n)
        return h

    def bakim_listesi(self, h):
        """[(what, command flag or None)] - nothing changes here"""
        out, bugun = [], datetime.now()
        satir = len(open(self.yol("ozet.md"), encoding="utf-8").read().splitlines()) if os.path.exists(self.yol("ozet.md")) else 0
        if satir > self.ayar["ozet_satir"]:
            out.append(("ozet.md %d satır (sınır %d): birleştirilecek ya da eskiyen satırlara bak." % (satir, self.ayar["ozet_satir"]), None))
        for k, a in sorted(h["aktif"].items()):
            gun = (bugun - datetime.strptime(a["son"][:10], "%Y-%m-%d")).days
            if gun >= self.ayar["sil_gun"]:
                out.append(("'%s=%s' %d gündür doğrulanmadı: kaldırılabilir (kullanıcı onaylarsa)." % (k, a["yon"], gun), "--kaldir %s=%s --sil" % (k, a["yon"])))
            elif gun >= self.ayar["eski_gun"] and not a["eski"]:
                out.append(("'%s=%s' %d gündür doğrulanmadı: ESKİ işaretlenebilir." % (k, a["yon"], gun), "--eski %s=%s" % (k, a["yon"])))
        konular = sorted({g["k"] for g in h["G"] if g.get("k")})
        for i, a in enumerate(konular):
            for b in konular[i + 1:]:
                if difflib.SequenceMatcher(None, a, b).ratio() >= 0.8:
                    out.append(("'%s' ile '%s' aynı konu olabilir: birleştirilebilir." % (a, b), "--birlestir %s>%s" % (a, b)))
        for k, taraf in h["celiski"]:
            out.append(("'%s' konusunda çelişki var: kullanıcıya ikisini göster (tarz.py tercih ile karar)." % k, None))
        ornek = sorted(d for d in os.listdir(self.yol("ornekler")) if os.path.isdir(self.yol("ornekler", d))) if os.path.isdir(self.yol("ornekler")) else []
        if len(ornek) > self.ayar["ornek_en_cok"]:
            out.append(("%d örnek var (sınır %d): en eskisi '%s' yedeğe alınabilir." % (len(ornek), self.ayar["ornek_en_cok"], ornek[0]), "--ornek-cikar %s" % ornek[0]))
        yedekler = sorted(f for f in os.listdir(self.yol("yedek")) if f.startswith("ozet-")) if os.path.isdir(self.yol("yedek")) else []
        if len(yedekler) > self.ayar["yedek_tut"]:
            fazla = yedekler[:len(yedekler) - self.ayar["yedek_tut"]]
            out.append(("ozet yedeği %d tane (sınır %d): en eski %d tanesi silinebilir: %s" % (len(yedekler), self.ayar["yedek_tut"], len(fazla), ", ".join(fazla)), "--sil"))
        return out


# -------------------------------------------------------------------- commands
def k_ozet(d, a):
    if d.kapali():
        print("KAPALI: tarz defteri kapalı (tarzim/KAPALI). ozet.md okunmaz, soru sorulmaz, kayıt yapılmaz.")
        return
    if not d.var():
        print("Tarz defteri henüz yok: notsuz çalış. İlk teslimden sonraki soruyla açılır.")
        return
    h = d.yeniden_yaz()
    print(open(d.yol("ozet.md"), encoding="utf-8").read().rstrip())
    print("---")
    ornek = [x for x in os.listdir(d.yol("ornekler")) if os.path.isdir(d.yol("ornekler", x))] if os.path.isdir(d.yol("ornekler")) else []
    print("Örnek: %d (tarzim/ornekler/). İşe başlarken açma; yalnız takılırsan bak, kopyalama." % len(ornek))
    satir = len(open(d.yol("ozet.md"), encoding="utf-8").read().splitlines())
    if satir > d.ayar["ozet_satir"] or h["bakimdan_beri"] >= d.ayar["bakim_her"]:
        print("BAKIM ÖNERİSİ: %s. İşe başlamadan kullanıcıya sun: py -3 alet/tarz.py bakim (onaysız hiçbir şey değişmez)." % (
            "ozet.md %d satır" % satir if satir > d.ayar["ozet_satir"] else "son bakımdan beri %d video" % h["bakimdan_beri"]))
    else:
        print("Bakım: gerekmiyor (son bakımdan beri %d video, öneri %d videoda bir)." % (h["bakimdan_beri"], d.ayar["bakim_her"]))


def k_soru(d, a):
    if d.kapali():
        print("SORMA: tarz defteri kapalı (tarzim/KAPALI).")
        return
    h = d.hesap()
    v = h["videolar"]
    sira = v.index(a.is_) + 1 if a.is_ in v else len(v) + 1
    son2 = max([v.index(x) + 1 for x in h["soru2"] if x in v] or [0])
    print('1. SORU (teslimden sonra, son mesajın son cümlesi): "En çok neyi beğendin? \'Geç\' dersen sormam."')
    print("   Sorma: kullanıcı okeyle birlikte zaten bir şey söylediyse (onu kaydet) ya da \"sorma\" dediyse.")
    print('   Değişiklik ister ya da reddederse: "Neyi beğenmedin? Hep mi böyle yapmayayım, yalnız bu videoda mı?"')
    if sira - son2 >= d.ayar["ikinci_soru_her"]:
        print('2. SORU bu videoda sorulabilir (%d. video): "Bir dahakinde neyi farklı yapayım?" Cevabı: --tur cevap2 --ikinci-soru' % sira)
    else:
        print("2. SORU bu videoda sorulmaz (%d. video; en çok %d videoda bir, sonraki: %d. video)." % (sira, d.ayar["ikinci_soru_her"], son2 + d.ayar["ikinci_soru_her"]))
    for k, y, isler, soz in h["esik"]:
        print('BEKLEYEN EŞİK: %s=%s %d videoda: %s. Sor: "%s videodur <bunu kısaca> diyorsun, hep böyle yapayım mı?"' % (
            k, y, len(isler), soz, SAYI.get(len(isler), str(len(isler)))))
    for k, y, soz in h["acik"]:
        print('BEKLEYEN AÇIK SÖZ: "%s" (%s=%s). Bir kez teyit et, sonra tarz.py tercih.' % (soz, k, y))
    for k, taraf in h["celiski"]:
        print("BEKLEYEN ÇELİŞKİ: %s: %s. İkisini göster, sen seçme." % (k, " <-> ".join('"%s"' % y for y, *_ in taraf)))
    if is_kurgusu(a.is_) == "sade":     # a Sade clip is a plain cut on purpose: no experiment, so no reminder
        print("DENEY: yok (Sade klip; deneme ve deneme notu istenmez).")
    else:
        print("DENEY: son mesajda bu işte bilerek denediğin tek şeyi bir satırla söyledin mi? Tepkisi: --tur deney --sonuc tuttu|tutmadi|yorumsuz")


def is_kurgusu(is_id):
    """"sade" | "editli" | None: the job's kurgu from panel/isler/<id>/is.json (a Short has none); only read"""
    try:
        return json.load(open(os.path.join(KOK, "panel", "isler", os.path.basename(str(is_id)), "is.json"),
                              encoding="utf-8-sig")).get("kurgu")
    except (OSError, ValueError, TypeError):
        return None


def k_ekle(d, a):
    if d.kapali():
        print("KAPALI: tarz defteri kapalı; kaydedilmedi.")
        return
    tur = a.tur
    konu = konu_temiz(a.konu) if a.konu else None
    if tur == "deney" and a.sonuc not in ("tuttu", "tutmadi", "yorumsuz"):
        sys.exit("HATA: deney için --sonuc tuttu | tutmadi | yorumsuz ver")
    if tur == "sessiz":
        guc, konu = "zayıf", None
    elif tur == "deney" and a.sonuc == "yorumsuz":   # no reaction to the experiment is no signal
        guc = "zayıf"
    else:
        guc = {"zayif": "zayıf", "orta": "orta", "guclu": "güçlü"}[a.guc or "orta"]
    if tur in ("ret", "degisiklik") and not a.kapsam:
        sys.exit('HATA: ret / değişiklikte --kapsam genel | bu-video ver (kullanıcıya sor: "Hep mi böyle yapmayayım, yalnız bu videoda mı?")')
    if not a.soz and tur != "sessiz" and not (tur == "deney" and a.sonuc == "yorumsuz"):
        sys.exit("HATA: --soz kullanıcının birebir sözü olmalı (yorumun --cikarim'a)")
    d.hazirla()
    once = {g.get("k") for g in d.hesap()["G"] if g.get("k")}
    satir = d.kaydet({"iş": a.is_, "tür": tur, "güç": guc, "konu": konu, "kapsam": a.kapsam or ("genel" if konu else None),
                      "sonuç": a.sonuc, "soru2": "evet" if a.ikinci_soru else None, "söz": a.soz or "(yorum yok)", "çıkarım": a.cikarim})
    h = d.yeniden_yaz()
    print("YAZILDI: " + satir)
    if tur == "sessiz":
        print("Sessiz okey: zayıf işaret; hiçbir şeyi saymaz.")
        return
    k, y = konu_ayir(konu)
    if not k:
        print("Konu verilmedi: söz günlükte durur ama hiçbir sayaca girmez.")
        return
    if k not in once:
        benzer = difflib.get_close_matches(k, sorted(once), n=1, cutoff=0.75)
        if benzer:
            print("DİKKAT: '%s' yeni bir konu; '%s' zaten var. Aynı şeyse bir dahakine onu kullan." % (k, benzer[0]))
    if a.kapsam == "bu-video":
        print("Yalnız bu video: sayılmaz, reddedilenler.md'de durur.")
        return
    if tur == "deney" and a.sonuc != "tuttu":
        print("Denendi, %s: reddedilenler.md'ye ve özetin \"Denendi, tutmadı\" bölümüne girdi." % "tutmadı" if a.sonuc == "tutmadi"
              else "Deneye yorum gelmedi: kaydedildi, sayılmaz.")
        return
    L = h["gozlem"].get(k, {}).get(y, [])
    isler = []
    for i, _ in L:
        if i not in isler:
            isler.append(i)
    ak = h["aktif"].get(k)
    if ak and ak["yon"] == y:
        print("DOĞRULANDI: kalıcı tercih '%s=%s' yeniden görüldü (%d video)." % (k, y, len(isler)))
    else:
        print("SAYAÇ: '%s=%s' %d farklı videoda (%s); eşik %d." % (k, y, len(isler), ", ".join(isler), d.ayar["esik_video"]))
    for kk, yy, ii, soz in h["esik"]:
        if (kk, yy) == (k, y):
            print("EŞİK: '%s=%s' %d ayrı videoda. Kullanıcının sözleri: %s" % (k, y, len(ii), soz))
            print('      Sor (onun sözleriyle): "%s videodur <bunu kısaca> diyorsun, hep böyle yapayım mı?"' % SAYI.get(len(ii), str(len(ii))))
            print('      Cevap: py -3 alet/tarz.py tercih --konu %s=%s --cevap evet|hayir --soz "<cevabı>" --is %s' % (k, y, a.is_))
    if guc == "güçlü" and not (ak and ak["yon"] == y):
        print('AÇIK SÖZ ("hep / asla"): bir kez teyit et ("%s: hep böyle mi?"), evet derse hemen yaz:' % a.soz)
        print('      py -3 alet/tarz.py tercih --konu %s=%s --cevap evet --soz "<cevabı>" --is %s --acik' % (k, y, a.is_))
    for kk, taraf in h["celiski"]:
        if kk == k:
            print("ÇELİŞKİ: '%s' konusunda %s. İkisini kullanıcıya göster, sen seçme." % (k, " ile ".join(
                '"%s"%s (%d video, son söz: "%s")' % (yy, " [kalıcı tercih]" if akt else "", n, s) for yy, n, s, akt in taraf)))
            print("      Karar: py -3 alet/tarz.py tercih --konu %s=<seçtiği> --cevap evet --soz \"<cevabı>\"%s" % (k, " --yerine" if ak else ""))
            print("      \"Duruma göre\" derse: tercih --konu %s=<herhangi biri> --cevap hayir (bu konunun sayacı sıfırlanır)." % k)


def k_tercih(d, a):
    if d.kapali():
        print("KAPALI: tarz defteri kapalı; kaydedilmedi.")
        return
    konu = konu_temiz(a.konu); k, y = konu_ayir(konu)
    if not a.soz:
        sys.exit("HATA: --soz kullanıcının cevabı (birebir) olmalı")
    d.hazirla()
    h = d.hesap()
    ak = h["aktif"].get(k)
    if a.cevap == "evet" and ak and ak["yon"] != y and not a.yerine:
        sys.exit("ÇELİŞKİ: kalıcı tercih '%s=%s' var. Kullanıcı yenisini istiyorsa --yerine ekle (eskisi yedekte kalır)." % (k, ak["yon"]))
    if os.path.exists(d.yol("ozet.md")):
        shutil.copy2(d.yol("ozet.md"), bos_yol(d.yol("yedek", "ozet-%s.md" % datetime.now().strftime("%Y%m%d-%H%M%S"))))
    notlar = (["açık söz"] if a.acik else []) + (["eski '%s=%s' yerine" % (k, ak["yon"])] if a.yerine and ak else [])
    satir = d.kaydet({"iş": a.is_, "tür": "karar", "konu": konu, "cevap": a.cevap, "söz": a.soz, "not": "; ".join(notlar)})
    d.yeniden_yaz()
    print("YAZILDI: " + satir)
    print("Kalıcı tercih oldu: %s=%s (ozet.md)." % (k, y) if a.cevap == "evet" else
          "Tercih olmadı: '%s=%s' sayacı sıfırlandı; yeniden %d videoda görülürse yine sorulur." % (k, y, d.ayar["esik_video"]))


def k_say(d, a):
    if not d.var():
        print("Defter yok.")
        return
    h = d.hesap()
    print("%d video kayıtlı. Konular (son karardan beri farklı video sayısı):" % len(h["videolar"]))
    for k in sorted(h["gozlem"]):
        for y, L in h["gozlem"][k].items():
            n = len({i for i, _ in L}); ak = h["aktif"].get(k, {}).get("yon") == y
            print("  %s=%s: %d video%s" % (k, y, n, " · kalıcı tercih" if ak else " · EŞİK" if n >= d.ayar["esik_video"] else ""))
    for k, a2 in sorted(h["aktif"].items()):
        if k not in h["gozlem"]:
            print("  %s=%s: kalıcı tercih (%s)" % (k, a2["yon"], "açık söz" if a2["acik"] else "karar"))
    print("Bilinen konu adları: " + ", ".join(sorted({g["k"] for g in h["G"] if g.get("k")})))


def k_goster(d, a):
    """READ ONLY (the panel's notebook view): what the notebook holds, as JSON. Never writes a file in tarzim/."""
    out = {"var": d.var(), "kapali": d.kapali(), "klasor": d.k, "esik": d.ayar["esik_video"], "video": 0,
           "tercihler": [], "sayilanlar": [], "tutmayanlar": [], "celiskiler": [], "son": [], "ornek": 0}
    if d.var():
        h = d.hesap()
        out["video"] = len(h["videolar"])
        for k, t in sorted(h["aktif"].items()):
            out["tercihler"].append({"konu": k, "yon": t["yon"], "soz": t["soz"], "cevap": t["cevap"], "kuruldu": t["kuruldu"][:10],
                                     "son": t["son"][:10], "video": t["sayi"], "eski": t["eski"], "acik": t["acik"]})
        for k in sorted(h["gozlem"]):
            for y, L in h["gozlem"][k].items():
                if h["aktif"].get(k, {}).get("yon") == y:
                    continue
                isler = []
                for i, g in L:
                    if i not in [x["is"] for x in isler]:
                        isler.append({"is": i, "soz": g.get("söz", ""), "tarih": g["tarih"][:10]})
                out["sayilanlar"].append({"konu": k, "yon": y, "video": len(isler), "esik": d.ayar["esik_video"],
                                          "soracak": len(isler) >= d.ayar["esik_video"], "sozler": isler})
        for r in d.reddedilen(h):
            out["tutmayanlar"].append({"konu": r["k"], "yon": r["y"], "tur": r["tur"], "ne": TUR_AD[r["tur"]], "kapsam": r["kapsam"],
                                       "kez": len(r["isler"]), "son_is": r["son_is"], "tarih": r["tarih"], "soz": r["soz"]})
        for k, taraf in h["celiski"]:
            out["celiskiler"].append({"konu": k, "taraflar": [{"yon": y, "video": n, "soz": s, "kalici": ak} for y, n, s, ak in taraf]})
        for g in [g for g in h["G"] if g.get("tür") in TURLER + ["karar"]][-a.son:][::-1]:
            out["son"].append({"tarih": g["tarih"], "is": g.get("iş", ""), "tur": g.get("tür"), "sonuc": g.get("sonuç", ""),
                               "konu": g.get("konu", ""), "soz": g.get("söz", ""), "cevap": g.get("cevap", "")})
        out["isler"] = sorted({g["iş"] for g in h["G"] if g.get("iş")})
        out["denemeler"] = {g["iş"]: g.get("sonuç", "") for g in h["G"] if g.get("tür") == "deney" and g.get("iş")}
    if os.path.isdir(d.yol("ornekler")):
        out["ornek"] = len([x for x in os.listdir(d.yol("ornekler")) if os.path.isdir(d.yol("ornekler", x))])
    if a.json:
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        return
    print("Defter %s · %d video · %d kalıcı tercih · %d sayılan · %d tutmayan · %d çelişki" % (
        "kapalı" if out["kapali"] else "var" if out["var"] else "yok", out["video"], len(out["tercihler"]),
        len(out["sayilanlar"]), len(out["tutmayanlar"]), len(out["celiskiler"])))


def k_ornek(d, a):
    d.hazirla()
    kaynak = os.path.abspath(a.kaynak)
    if not os.path.isdir(kaynak):
        sys.exit("HATA: kaynak klasör yok: " + kaynak)
    hedef = d.yol("ornekler", a.is_)
    if os.path.exists(hedef) and not a.ustune_yaz:
        sys.exit("HATA: %s zaten var (yeniden yazmak için --ustune-yaz; eskisi yedeğe alınır)" % hedef)
    if os.path.exists(hedef):
        shutil.move(hedef, bos_yol(d.yol("yedek", "ornekler", "%s-%s" % (a.is_, datetime.now().strftime("%Y%m%d-%H%M%S")))))
    alinan, atlanan = 0, 0
    for kok, dirs, files in os.walk(kaynak):
        dirs[:] = [x for x in dirs if x not in ATLA_KLASOR and not x.startswith(".")]
        for f in files:
            p = os.path.join(kok, f)
            if os.path.splitext(f)[1].lower() in METIN_UZ and os.path.getsize(p) <= 2_000_000:
                q = os.path.join(hedef, os.path.relpath(p, kaynak)); os.makedirs(os.path.dirname(q), exist_ok=True)
                shutil.copy2(p, q); alinan += 1
            else:
                atlanan += 1
    yaz(os.path.join(hedef, "not.md"), "# Örnek: %s\n\nNeden onaylandı: %s\n\nKaynak: %s\nAlındı: %s\n\n"
        "Bu bir örnek, kalıp değil. İşe başlarken açma; takılırsan hissini al, yapısını kopyalama.\n"
        "Görüntü, ses ve font dosyaları alınmadı (%d dosya atlandı).\n" % (a.is_, a.neden, kaynak, simdi(), atlanan))
    d.kaydet({"iş": a.is_, "tür": "ornek", "söz": a.neden, "not": "%d metin dosyası, %d medya/büyük dosya atlandı" % (alinan, atlanan)})
    print("ÖRNEK: %s (%d metin dosyası alındı, %d medya ya da büyük dosya atlandı)." % (hedef, alinan, atlanan))
    sayi = len([x for x in os.listdir(d.yol("ornekler")) if os.path.isdir(d.yol("ornekler", x))])
    if sayi > d.ayar["ornek_en_cok"]:
        print("Örnek sayısı %d > %d: bakımda en eskisini yedeğe almayı öner (tarz.py bakim)." % (sayi, d.ayar["ornek_en_cok"]))


def k_aletim(d, a):
    d.hazirla()
    p = os.path.abspath(a.dosya)
    if not os.path.isfile(p):
        sys.exit("HATA: dosya yok: " + p)
    hedef = d.yol("aletlerim", os.path.basename(p))
    if os.path.exists(hedef):
        y = bos_yol(d.yol("yedek", "aletlerim", "%s-%s" % (datetime.now().strftime("%Y%m%d-%H%M%S"), os.path.basename(p))))
        shutil.move(hedef, y)
        print("Önceki sürüm yedekte: " + y)
    shutil.copy2(p, hedef)
    log = d.yol("aletlerim", "DEGISIKLIKLER.md")
    if not os.path.exists(log):
        yaz(log, "# Benim aletlerim: değişiklik günlüğü\nPaylaşılan alet/ klasörü değişmez; bu aletler yalnız bu kullanıcı için.\n\n")
    with open(log, "a", encoding="utf-8", newline="\n") as f:
        f.write("- %s · %s · %s\n" % (simdi(), os.path.basename(p), a.neden.replace("\n", " ")))
    print("ALETİM: %s (günlük: %s)" % (hedef, log))


def k_bakim(d, a):
    if not d.var():
        print("Defter yok; bakım gerekmiyor.")
        return
    h = d.yeniden_yaz()
    liste = d.bakim_listesi(h)
    istek = [x for x in (a.eski or []) + (a.kaldir or []) + (a.birlestir or [])] + ([a.ornek_cikar] if a.ornek_cikar else [])
    if not a.uygula:
        print("BAKIM (yalnız liste; hiçbir şey değişmedi). Son bakımdan beri %d video (öneri %d videoda bir):" % (h["bakimdan_beri"], d.ayar["bakim_her"]))
        for ne, bayrak in liste or [("yapılacak bir şey yok.", None)]:
            print("  - " + ne + ("   [uygulamak: tarz.py bakim --uygula %s]" % bayrak if bayrak else ""))
        print("Kullanıcı onaylarsa seçtiklerini --uygula ile yap; ozet.md'nin önceki hali tarzim/yedek/'e alınır.")
        print("Yapılacak bir şey yoksa ya da kullanıcı \"şimdi değil\" derse: tarz.py bakim --uygula (yalnız sayacı sıfırlar).")
        return
    if a.kaldir and not a.sil:
        sys.exit("HATA: --kaldir yalnız --sil ile (kullanıcı açıkça onayladıysa). Hiçbir şey değişmedi.")
    shutil.copy2(d.yol("ozet.md"), bos_yol(d.yol("yedek", "ozet-%s.md" % datetime.now().strftime("%Y%m%d-%H%M%S"))))
    for x in a.eski or []:
        d.kaydet({"tür": "bakim", "sonuç": "eski", "konu": konu_temiz(x), "söz": "(bakım, kullanıcı onayladı)"})
    for x in a.birlestir or []:
        d.kaydet({"tür": "bakim", "sonuç": "birlestir", "konu": x, "söz": "(bakım, kullanıcı onayladı)"})
    for x in a.kaldir or []:
        d.kaydet({"tür": "bakim", "sonuç": "kaldir", "konu": konu_temiz(x), "söz": "(bakım, kullanıcı onayladı)"})
    if a.ornek_cikar:
        kaynak = d.yol("ornekler", a.ornek_cikar)
        if os.path.isdir(kaynak):
            shutil.move(kaynak, bos_yol(d.yol("yedek", "ornekler", "%s-%s" % (a.ornek_cikar, datetime.now().strftime("%Y%m%d-%H%M%S")))))
            print("Örnek yedeğe alındı: " + a.ornek_cikar)
    if a.sil:
        # only the tool's own automatic ozet backups; hand-edited copies (ozet-elle-*) are never removed
        yedekler = sorted((f for f in os.listdir(d.yol("yedek")) if re.fullmatch(r"ozet-\d{8}-\d{6}(-\d+)?\.md", f)),
                          key=lambda f: (os.path.getmtime(d.yol("yedek", f)), f))
        for f in yedekler[:max(0, len(yedekler) - d.ayar["yedek_tut"])]:
            os.remove(d.yol("yedek", f)); print("Silindi (eski özet yedeği): " + f)
    d.kaydet({"tür": "bakim", "sonuç": "tamam", "söz": "(bakım yapıldı)", "not": "; ".join(istek) or "yalnız sayaç"})
    d.yeniden_yaz()
    print("BAKIM TAMAM. ozet.md yeniden yazıldı; önceki hali tarzim/yedek/'te.")


def k_kapat(d, a):
    d.hazirla()
    yaz(d.yol("KAPALI"), "")
    d.kaydet({"tür": "kapat", "söz": a.soz or "sorma"})
    print("KAPALI: soru sorulmaz, kayıt yapılmaz, ozet.md okunmaz. Açmak: py -3 alet/tarz.py ac (ya da KAPALI dosyasını sil).")


def k_ac(d, a):
    if not d.kapali():
        print("Defter zaten açık.")
        return
    shutil.move(d.yol("KAPALI"), bos_yol(d.yol("yedek", "KAPALI-%s" % datetime.now().strftime("%Y%m%d-%H%M%S"))))
    d.kaydet({"tür": "ac", "söz": a.soz or "tekrar sor"})
    print("AÇIK: defter yeniden çalışıyor.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--klasor", help="tarzim klasörü (varsayılan: motor kökünde tarzim/)")
    sp = ap.add_subparsers(dest="komut", required=True)
    ornek = lambda s: dict(formatter_class=argparse.RawDescriptionHelpFormatter, description="örnek: " + s)
    p = sp.add_parser("ozet", **ornek("py -3 alet/tarz.py ozet"))
    p = sp.add_parser("soru", **ornek("py -3 alet/tarz.py soru --is 261118-0102-ab")); p.add_argument("--is", dest="is_", required=True)
    p = sp.add_parser("ekle", **ornek('py -3 alet/tarz.py ekle --is 261118-0102-ab --tur begeni --soz "kesmeler hızlıydı" '
                                      '--cikarim "hızlı kesimi seviyor" --konu kesim-ritmi=hizli'))
    p.add_argument("--is", dest="is_", required=True); p.add_argument("--tur", required=True, choices=TURLER)
    p.add_argument("--soz", help="kullanıcının birebir sözü"); p.add_argument("--cikarim", help="senin yorumun (ayrı alan)")
    p.add_argument("--konu", help="konu=istenen, ör. yazi-boyutu=kucuk"); p.add_argument("--guc", choices=["zayif", "orta", "guclu"])
    p.add_argument("--kapsam", choices=["genel", "bu-video"]); p.add_argument("--sonuc", choices=["tuttu", "tutmadi", "yorumsuz"])
    p.add_argument("--ikinci-soru", action="store_true", help="bu cevap 2. soruya verildi")
    p = sp.add_parser("say", **ornek("py -3 alet/tarz.py say"))
    p = sp.add_parser("tercih", **ornek('py -3 alet/tarz.py tercih --konu kesim-ritmi=hizli --cevap evet --soz "evet, hep böyle" --is 261118-0102-ab'))
    p.add_argument("--konu", required=True); p.add_argument("--cevap", required=True, choices=["evet", "hayir"])
    p.add_argument("--soz", required=True); p.add_argument("--is", dest="is_")
    p.add_argument("--yerine", action="store_true", help="aynı konudaki eski kalıcı tercihin yerine")
    p.add_argument("--acik", action="store_true", help="kullanıcı açıkça hep/asla dedi (eşik beklenmedi)")
    p = sp.add_parser("ornek", **ornek('py -3 alet/tarz.py ornek --is 261118-0102-ab --kaynak panel/isler/261118-0102-ab/kurgu/sahne --neden "ritmi beğendi"'))
    p.add_argument("--is", dest="is_", required=True); p.add_argument("--kaynak", required=True); p.add_argument("--neden", required=True)
    p.add_argument("--ustune-yaz", action="store_true")
    p = sp.add_parser("aletim", **ornek('py -3 alet/tarz.py aletim --dosya panel/isler/<id>/kurgu/benim_aletim.py --neden "neden gerekti"'))
    p.add_argument("--dosya", required=True); p.add_argument("--neden", required=True)
    p = sp.add_parser("bakim", **ornek("py -3 alet/tarz.py bakim   (sonra onayla: py -3 alet/tarz.py bakim --uygula --eski muzik=yok)"))
    p.add_argument("--uygula", action="store_true"); p.add_argument("--eski", action="append", metavar="KONU=YON")
    p.add_argument("--kaldir", action="append", metavar="KONU=YON"); p.add_argument("--birlestir", action="append", metavar="ESKI>YENI")
    p.add_argument("--ornek-cikar", metavar="AD"); p.add_argument("--sil", action="store_true", help="silmeye izin (kullanıcı açıkça onayladıysa)")
    p = sp.add_parser("goster", **ornek("py -3 alet/tarz.py goster --json   (yalnız okur; panelin defter görünümü)"))
    p.add_argument("--json", action="store_true"); p.add_argument("--son", type=int, default=6, help="son kaç kayıt")
    p = sp.add_parser("kapat", **ornek('py -3 alet/tarz.py kapat --soz "sorma artık"')); p.add_argument("--soz")
    p = sp.add_parser("ac", **ornek("py -3 alet/tarz.py ac")); p.add_argument("--soz")
    a = ap.parse_args()
    d = Defter(a.klasor)
    {"ozet": k_ozet, "soru": k_soru, "ekle": k_ekle, "say": k_say, "tercih": k_tercih, "ornek": k_ornek,
     "aletim": k_aletim, "bakim": k_bakim, "kapat": k_kapat, "ac": k_ac, "goster": k_goster}[a.komut](d, a)


if __name__ == "__main__":
    main()
