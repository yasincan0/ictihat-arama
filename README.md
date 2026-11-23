# İçtihat Arama

Avukatların davalarındaki olayı serbest metinle anlatıp uygun **içtihadı birleştirme
kararlarını** anlamsal arama ile bulabildiği abonelikli web uygulaması.
İlk kapsam: Danıştay İçtihatları Birleştirme Kurulu kararları.

Proje kuralları: [`CLAUDE.md`](CLAUDE.md) · Yol haritası: [`docs/PLAN.md`](docs/PLAN.md)

## Hızlı başlangıç

```bash
cp .env.example .env              # değerleri doldurun
docker compose up -d --build      # db + backend (8000) + frontend (3000)
curl localhost:8000/health        # {"status":"ok"}
```

## Docker olmadan geliştirme

```bash
docker compose up -d db
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
.venv/bin/pytest                  # veritabanı testleri için TEST_DATABASE_URL (varsayılan: ictihat_test)

cd ../frontend && npm install && npm run dev
npm test                          # ön yüz testleri (Vitest)
```

## Başlangıç listesini yükleme

```bash
# depo kökünden; önce: cd backend && alembic upgrade head
python -m data.pipeline.load_seed             # yeni kayıtları ekler, var olanlara dokunmaz
python -m data.pipeline.load_seed --dry-run   # yazmadan raporlar
python -m data.pipeline.load_seed --update    # doğrulanmamış kayıtları listeden günceller
```

## Resmî metinlerle doğrulama (Adım 2b)

Resmî Gazete sitesine otomatik erişim yok (geliştirme ortamından yanıt vermiyor); kararların
yayımlandığı sayılar elle indirilir. Ayrıntılar ve ilk 10 kararın listesi:
[`docs/indirilecekler.md`](docs/indirilecekler.md).

```bash
# OCR için (taranmış PDF'ler): apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-tur
# Dosyaları data/raw/resmigazete/ altına rg-YYYYMMDD-SAYI_sira-N.pdf adıyla koyun, sonra:
python -m data.pipeline.verify_official            # doğrula, docs/dogrulama_raporu.md üret
python -m data.pipeline.verify_official --dry-run  # yazmadan dene
python -m data.pipeline.verify_official --force    # işlenmiş dosyaları yeniden işle
python -m data.pipeline.verify_official --liste    # indirme listesini yeniden üret
```

Tüm denetimlerden (esas, karar, karar tarihi, Resmî Gazete tarih/sayısı, kurul adı, özet
uyumu, hüküm yönü) geçen kararlar `dogrulandi=true` yapılır; diğerleri gerekçeleriyle
`docs/dogrulama_raporu.md` içinde listelenir. Önceden doğrulanmış kayıtlara dokunulmaz.

## Üyelik (arka uç)

`/auth` altında: `register`, `verify-email`, `resend-verification`, `login`, `logout`, `me`,
`forgot-password`, `reset-password`. Şifreler argon2 ile saklanır; oturum HttpOnly,
SameSite=Lax çerezde JWT olarak taşınır. Geliştirmede e-postalar (doğrulama/sıfırlama
bağlantıları) backend günlüğüne yazılır (`EMAIL_BACKEND=console`). Aboneliği olmayan
kullanıcının aylık ücretsiz arama hakkı `FREE_SEARCHES_PER_MONTH` (varsayılan 3);
`GET /auth/me` kalan hakkı da döner. Üretimde (`APP_ENV=production`) uygulama, güçlü bir
`SECRET_KEY`, `COOKIE_SECURE=true` ve gerçek bir e-posta sağlayıcısı olmadan açılmaz.

## Arayüz (Adım 6)

Sayfalar: `/` (tanıtım), `/giris`, `/kayit`, `/eposta-dogrula`, `/sifremi-unuttum`,
`/sifre-sifirla`, `/ara`, `/karar/[id]`. Doğrulanmamış kararlar her yerde uyarı rozetiyle
gösterilir. Arama uç noktası (Adım 4) hazır olana kadar `/ara` açıkça işaretlenmiş örnek
sonuçlar gösterir; gerçek uca geçmek için `NEXT_PUBLIC_MOCK_SEARCH=false`.
