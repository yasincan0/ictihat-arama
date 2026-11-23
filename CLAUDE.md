# CLAUDE.md — İçtihat Arama Projesi

Bu dosya Claude Code için proje bağlamıdır. Her oturumda önce bunu oku.

## Proje Özeti

Avukatlar abone olur, davalarındaki olayı serbest metinle özetler; sistem anlamsal arama ile
uygun **içtihadı birleştirme kararlarını** (Yargıtay, Danıştay vb.) bulur ve her kararın
neden uygun olduğunu kısaca açıklar.

## Kapsam ve Başlangıç Verisi

İlk sürümün kapsamı **Danıştay İçtihatları Birleştirme Kurulu kararlarıdır**. Yargıtay İBK
kararları sonraki aşamada eklenecektir; kod mahkemeden bağımsız yazılmalıdır.

Başlangıç listesi: `data/seed/danistay_ibk.json`

- `kunyeli`: künyesi (tarih, esas, karar no) bilinen 76 karar
- `kunyesiz`: Danıştay bülteninde özeti bulunan ama künyesi bilinmeyen 51 karar (konu kategorili).
  Bunların bir kısmı, `kunyeli` içinde özeti eksik olan kararlarla aynı olabilir.
- `durum` alanı:
  - `tam`: künye ve özet var (yine de resmi kaynaktan doğrulanmalı)
  - `ozet_eksik`: künye var, kararın özü/hükmü bilinmiyor
  - `eslestirme_belirsiz`: künye ile özetin aynı karara ait olduğu kesin değil
  - `numara_supheli`: esas/karar numaraları İBK kararına benzemiyor (daire kararı olabilir)
  - `hukum_yonu_eksik`: konu biliniyor, hükmün yönü bilinmiyor
  - `kunye_eksik`: tarih, esas veya karar numarası eksik
- `notlar`: kaynaklar arası çelişkiler (ör. farklı esas no veya tarih)
- `kaynak`: özetin alındığı ikincil kaynak (danistay, lexpera, alomaliye, memurlar, hukukcularevi)

**Bu liste ikincil kaynaklardan derlenmiştir. Hiçbir kayıt resmi kaynakla (Resmî Gazete
veya Danıştay) doğrulanmadan kullanıcıya "kesin" olarak gösterilmez.** Veritabanında
`dogrulandi` (bool) ve `dogrulama_kaynagi` alanları tutulur; doğrulanmamış kayıtlar
arayüzde uyarıyla gösterilir.

## Teknoloji Yığını (değiştirmeden önce sor)

- Arka uç: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- Veritabanı: PostgreSQL 16 + pgvector
- Embedding: çok dilli model (varsayılan `BAAI/bge-m3`, sentence-transformers ile); değiştirilebilir olmalı
- LLM açıklama katmanı: Anthropic Claude API (`anthropic` Python SDK)
- Ön yüz: Next.js (App Router), TypeScript, Tailwind CSS
- Ödeme: iyzico (soyutlanmış bir `payments` modülü arkasında)
- Çalıştırma: Docker Compose (db, backend, frontend)
- Test: pytest (backend), Playwright veya Vitest (frontend)

## Klasör Yapısı

```
backend/
  app/
    api/          # FastAPI router'ları
    core/         # ayarlar, güvenlik, bağımlılıklar
    models/       # SQLAlchemy modelleri
    schemas/      # Pydantic şemaları
    services/     # arama, embedding, llm, ödeme
  alembic/
  tests/
frontend/
data/
  seed/           # başlangıç listeleri (git'e girer): danistay_ibk.json
  scrapers/       # kaynak başına bir modül
  pipeline/       # temizleme, ayrıştırma, bölme, vektörleştirme
  raw/            # ham indirilen veri (git'e girmez)
  processed/      # işlenmiş JSON (git'e girmez)
docs/
docker-compose.yml
.env.example
```

## Veri Modeli (temel)

- `decisions`: id, mahkeme, daire/kurul, esas_no, karar_no, karar_tarihi, resmi_gazete_tarihi,
  resmi_gazete_sayisi, kategori, konu, ozet, tam_metin, ilgili_mevzuat (JSON), kaynak_url,
  durum, notlar (JSON), dogrulandi, dogrulama_kaynagi
- `decision_chunks`: id, decision_id, sira, metin, embedding (vector)
- `users`, `subscriptions`, `search_logs` (olay özetini şifreli veya hiç saklamadan; bkz. KVKK)

## Kurallar

- Kod yorumları ve kullanıcıya görünen metinler Türkçe; değişken/fonksiyon adları İngilizce.
- Her yeni özellik için test yaz; `pytest` geçmeden işi bitmiş sayma.
- Gizli anahtarlar yalnızca `.env` içinde; `.env.example` güncel tutulsun. `.env` asla commit edilmez.
- Scraper'lar nazik olsun: istekler arasında bekleme, robots.txt ve kullanım koşullarına uyum,
  User-Agent belirt, sonuçları önbelleğe al.
- KVKK: avukatın girdiği olay özeti varsayılan olarak kalıcı saklanmaz; saklanacaksa şifreli
  ve süre sınırlı. Loglara olay metni yazılmaz.
- LLM'e giden istemler `backend/app/services/llm/prompts.py` içinde tek yerde tutulur.
- LLM açıklamaları yalnızca bulunan karar metnine dayanmalı; karar metninde olmayan bilgi
  uydurulmamalı, her açıklama karar künyesine atıf yapmalı.
- Büyük değişikliklerden önce kısa bir plan yaz ve onay iste.

## Komutlar

```bash
docker compose up -d db                 # veritabanı
cd backend && uvicorn app.main:app --reload
cd backend && pytest
cd backend && alembic upgrade head
cd frontend && npm run dev
python -m data.pipeline.run             # veri hattını çalıştır
```

## Yol Haritası

Ayrıntılı adımlar ve her adım için verilecek komutlar: `docs/PLAN.md`
