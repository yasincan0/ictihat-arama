# Güvenlik ve KVKK gözden geçirmesi (Adım 8)

Tarih: 23.11.2026. Kapsam: backend (FastAPI), frontend (Next.js), ödeme ve üyelik akışları.
Arama (`/search`) ve LLM açıklama katmanı henüz yazılmadığı için bu uçlar kapsam dışıdır;
yazıldıklarında aşağıdaki "Bekleyenler" listesindeki maddeler uygulanmalıdır.

## Uygulananlar

| Konu | Durum |
|---|---|
| Şifre saklama | argon2id (argon2-cffi varsayılanları), girişte gerekirse yeniden hash |
| Oturum | JWT, HttpOnly + SameSite=Lax çerez; üretimde Secure zorunlu; şifre değişince eski oturumlar geçersiz |
| CSRF | Durum değiştiren isteklerde `Origin` izinli kökenlerden biri olmalı (`OriginCheckMiddleware`); ödeme dönüşü ve webhook muaf, kendi doğrulamaları var |
| CORS | Yalnızca `CORS_ORIGINS`; yöntemler GET/POST/OPTIONS, başlıklar Content-Type/Accept; üretimde `*` ve `http://` reddedilir |
| İstek sınırlama | Giriş (IP ve e-posta başına), kayıt, e-posta gönderen uçlar (IP ve adres başına), jeton denemeleri, ödeme başlatma; 429 + Retry-After |
| Girdi doğrulama | Pydantic şemaları (e-posta, şifre kuralları, TCKN algoritması, TR cep telefonu, alan uzunlukları); istek gövdesi en fazla 64 KB |
| Hesap varlığı sızıntısı | Kayıt, şifremi unuttum ve doğrulama yeniden gönderme aynı yanıtı verir; giriş hataları genel; kullanıcı yoksa da sahte hash doğrulaması yapılır |
| E-posta jetonları | Tek kullanımlık, süreli, amaca bağlı; yalnızca SHA-256 özeti saklanır |
| Güvenlik başlıkları | API: nosniff, X-Frame-Options DENY, Referrer-Policy no-referrer, Cache-Control no-store, (Secure ise) HSTS. Ön yüz: nosniff, DENY, Referrer-Policy, Permissions-Policy, X-Powered-By kapalı, isteğe bağlı HSTS |
| Günlükler | Olay metni ve istek gövdeleri günlüğe yazılmaz (test ile denetlenir); tüm günlük kayıtlarında TCKN, telefon ve kart numarası benzeri diziler maskelenir |
| Ödeme | Kart bilgisi sistemimize hiç gelmez (iyzico formu); TCKN/telefon/adres yalnızca iyzico'ya iletilir, saklanmaz; dönüş ve webhook'ta durum iyzico'dan sorgulanır; webhook imzası (X-IYZ-SIGNATURE-V3) doğrulanır |
| KVKK hakları | Şifre onaylı hesap silme (`POST /auth/delete-account`); abonelik, jetonlar ve ödeme oturumları silinir, arama sayaçları anonimleşir |
| Üretim koruması | Zayıf `SECRET_KEY`, Secure olmayan çerez, konsol e-postası, sahte ödeme sağlayıcısı, iyzico sandbox adresi veya güvensiz CORS ile uygulama açılmaz |
| Hukuki metinler | `/aydinlatma-metni` ve `/kullanim-kosullari` TASLAK olarak eklendi; kayıt formunda onay kutusu bu sayfalara bağlı |

## Bekleyenler / öneriler

1. **İstek sınırlayıcı tek süreçlidir.** Birden çok backend süreci veya sunucu çalıştırılacaksa
   `RateLimiter` arayüzü için Redis tabanlı bir uygulama eklenmeli.
2. **CSP (İçerik Güvenliği Politikası)** henüz yok. iyzico ödeme formunun yüklediği alan adları
   sandbox'ta tarayıcı ağ sekmesinden belirlenip `next.config.ts` içine eklenmeli.
3. **`/search` uç noktası (Adım 4) yazılırken:** olay metni yalnızca bellekte işlenmeli; `SearchLog`
   yalnızca uzunluk/sonuç sayısı tutar. Arama ucu için kullanıcı başına sınır ve kota denetimi
   (`get_quota`) uygulanmalı; olay metni uzunluğu 5000 karakterle sınırlanmalı.
4. **LLM katmanı (Adım 5):** olay özeti ve karar metni yurt dışındaki bir sağlayıcıya (Anthropic)
   gönderilecek. KVKK m.9 (yurt dışına aktarım) açısından hukuki dayanak netleştirilmeli; aydınlatma
   metninde bu madde hukuki inceleme notuyla işaretlendi. Kullanıcıya olay metnine kişisel veri
   yazmaması arama sayfasında hatırlatılıyor.
5. **Gerçek e-posta sağlayıcısı** (SMTP/SES vb.) eklenmeli; üretimde konsol göndericisi engelli.
6. **Mesafeli satış:** ön bilgilendirme formu ve mesafeli satış sözleşmesi hazırlanmalı (kullanım
   koşullarında not düşüldü).
7. **Bağımlılık taraması:** CI'da `pip-audit` ve `npm audit` çalıştırılması önerilir.
8. **Yedekleme ve şifreleme:** veritabanı yedeklerinin şifrelenmesi ve erişim kayıtları altyapı
   aşamasında ele alınmalı.
