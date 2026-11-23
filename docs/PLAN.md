# Geliştirme Planı — Claude Code ile

**Başlamadan önce:** `danistay_ibk.json` dosyasını depoda `data/seed/` klasörüne koy.

Her adımı **ayrı bir oturumda** (veya `/clear` sonrası) ver. Bir adım bitince test et,
commit et, sonra diğerine geç. Komutları olduğu gibi kopyalayabilirsin.

---

## Adım 0 — İskelet

> CLAUDE.md'yi oku. Bu klasör yapısına göre proje iskeletini kur: docker-compose.yml
> (PostgreSQL 16 + pgvector, backend, frontend), backend için FastAPI iskeleti ve
> `/health` uç noktası, .env.example, .gitignore, boş Next.js uygulaması. pytest ile
> /health testini yaz ve çalıştır. Bitince ne yaptığını özetle.

**Kontrol:** `docker compose up` çalışıyor, `localhost:8000/health` cevap veriyor.

---

## Adım 1 — Veri modeli

> CLAUDE.md'deki veri modeline göre SQLAlchemy modellerini ve ilk Alembic migration'ını
> oluştur. pgvector eklentisini migration içinde etkinleştir. Embedding boyutunu ayardan
> okut. Modeller için basit testler yaz.

---

## Adım 2a — Başlangıç listesini yükle

> data/seed/danistay_ibk.json dosyasını oku (yapısı CLAUDE.md'de). Bu listeyi
> decisions tablosuna yükleyen bir komut yaz: `python -m data.pipeline.load_seed`.
> Tüm kayıtlar dogrulandi=false olarak girsin. "kunyesiz" bölümündeki kayıtlar da
> künye alanları boş, kategori dolu olarak yüklensin. Komut tekrar çalıştırıldığında
> çift kayıt oluşturmasın (esas_no + karar_no, yoksa özet metni üzerinden eşleştir).
> Yükleme sonunda durum alanına göre bir özet tablo yazdır.

**Kontrol:** 76 künyeli + 51 künyesiz kayıt yüklendi mi?

---

## Adım 2b — Tam metinleri topla ve doğrula (en kritik adım)

> Künyeli kararların tam metinlerini resmi kaynaklardan (Resmî Gazete, Danıştay)
> bulmak için bir plan sun; kodu yazmadan önce kaynakların yapısını incele.
> Kurallar: istekler arasında bekleme, önbellek, kaldığı yerden devam edebilme.
> Ham veriyi data/raw altına kaydet. Önce "tam" durumundaki 10 kararla dene.
> Her karar için: tam metni kaydet, künyeyi (tarih, esas, karar no, RG tarih ve sayısı)
> resmi metinden doğrula, listedeki özetin karar metniyle uyuşup uyuşmadığını kontrol et.
> Uyuşanları dogrulandi=true yap; uyuşmayanları docs/dogrulama_raporu.md içine yaz.

**Not:** Kaynakların kullanım koşullarını sen kontrol et. Otomatik çekmeye izin
yoksa kararların PDF'lerini elle indirip `data/raw` klasörüne koy ve Claude Code'a
"bu dosyaları işle" de.

---

## Adım 2c — Eksikleri tamamla

> docs/dogrulama_raporu.md ve veritabanındaki durum alanlarını kullanarak şu işleri yap:
> 1. "ozet_eksik" ve "hukum_yonu_eksik" kararlar için tam metinden kısa bir öz çıkar
>    (yalnızca metne dayanarak, uydurma yok) ve bana onaya sun.
> 2. "kunyesiz" kayıtları tam metinlerle eşleştir; bunların bir kısmı özeti eksik
>    künyeli kararlardır. Eşleşme önerilerini güven skoruyla listele, ben onaylayayım.
> 3. "eslestirme_belirsiz", "numara_supheli" ve notlarında çelişki olan kayıtlar
>    (sıra 4, 15, 41, 52, 55, 60, 63) için resmi kaynaktaki doğru bilgiyi raporla.
> Onaylamadığım hiçbir değişikliği veritabanına yazma.

**Kontrol:** Raporu sen (hukukçu gözüyle) incele; liste ancak bundan sonra "güvenilir" sayılır.

---

## Adım 3 — Ayrıştırma ve temizleme

> data/raw içindeki kararları ayrıştır: mahkeme, kurul/daire, esas no, karar no, karar
> tarihi, Resmî Gazete tarih ve sayısı, konu, tam metin, metinde geçen kanun maddeleri.
> Sonucu data/processed altına JSON olarak yaz ve veritabanına yükleyen bir komut ekle.
> 5 örnek karar için beklenen çıktıyla test yaz. Ayrıştırılamayan kararları ayrı bir
> rapora dök.

**Kontrol:** Rastgele 10 kararı elle aç, künyeler doğru mu bak.

---

## Adım 4 — Vektörleştirme ve anlamsal arama

> Kararları anlamlı parçalara böl (paragraf bazlı, örtüşmeli), embedding üret ve
> decision_chunks tablosuna yaz. Ardından POST /search uç noktasını yaz: olay özetini
> alır, en yakın parçaları bulur, karar bazında gruplar, en iyi 10 kararı skorlarıyla
> döner. Embedding servisini değiştirilebilir bir arayüz arkasına koy.
> Kalite ölçümü için docs/test_cases.json içinde, doğrulanmış kararlardan en az 20
> örnek olay-beklenen karar çifti oluştur. Olayları karar özetini kopyalamadan, bir
> avukatın müvekkilinden dinleyeceği gibi gündelik dille yaz (ör. sıra 66 için:
> "Limited şirketin vergi borcu için vergi dairesi doğrudan ortağa ödeme emri gönderdi").
> Ardından bir değerlendirme betiği yaz (ilk 5'te doğru karar var mı?).

**Not:** Test vakalarını sen (avukat gözüyle) gözden geçir ve düzelt. Arama kalitesinin
ölçüsü bu dosya olacak.

---

## Adım 5 — Açıklama katmanı (LLM)

> /search sonuçlarına, her karar için "bu karar olaya neden uygun" açıklaması ekle.
> Anthropic Claude API kullan. Açıklama yalnızca karar metnine dayanmalı, ilgili
> paragrafı alıntılamalı ve uydurma bilgi içermemeli. İstemleri prompts.py içinde tut.
> Uygun karar bulunamazsa bunu açıkça söylesin.

---

## Adım 6 — Arayüz

> Next.js ile şu sayfaları yap: ana sayfa (tanıtım), giriş/kayıt, arama sayfası (büyük
> metin kutusu + sonuç kartları: künye, skor, açıklama, tam metne bağlantı), karar detay
> sayfası. Sade, profesyonel, mobil uyumlu bir tasarım olsun.

---

## Adım 7 — Üyelik ve abonelik

> Kullanıcı kaydı, e-posta doğrulama, giriş (JWT veya oturum çerezi) ve şifre sıfırlama
> ekle. Ardından iyzico abonelik entegrasyonunu soyut bir payments modülü arkasında yap;
> önce sandbox ortamıyla çalıştır. Aboneliği olmayan kullanıcı ayda 3 ücretsiz arama
> yapabilsin.

---

## Adım 8 — KVKK ve güvenlik

> Projeyi güvenlik açısından gözden geçir: rate limiting, girdi doğrulama, şifre
> hash'leme, CORS, loglarda olay metni olmaması. Aydınlatma metni ve kullanım koşulları
> için taslak sayfalar ekle (hukuki metinleri ben düzenleyeceğim).

---

## Adım 9 — Yayına alma

> Projeyi tek bir Linux sunucuya Docker Compose ile kurmak için üretim yapılandırması
> hazırla: Nginx ters vekil, Let's Encrypt SSL, veritabanı yedekleme betiği. Adım adım
> kurulum rehberini docs/DEPLOY.md olarak yaz.

---

## Claude Code ile çalışma ipuçları

- Her adımın başında "CLAUDE.md ve docs/PLAN.md'yi oku, Adım X'i yap" demen yeterli.
- Büyük adımlarda önce plan modunu kullan (Shift+Tab), planı onayla, sonra yazdır.
- Her adım sonunda: "testleri çalıştır, sonra değişiklikleri açıklayıcı bir mesajla commit et."
- Bir şey yanlış giderse `git` ile geri dönebilirsin; bu yüzden sık commit et.
- Bir kuralı tekrar tekrar söylüyorsan, onu CLAUDE.md'ye ekle.
