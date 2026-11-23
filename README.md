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
```

## Başlangıç listesini yükleme

```bash
# depo kökünden; önce: cd backend && alembic upgrade head
python -m data.pipeline.load_seed             # yeni kayıtları ekler, var olanlara dokunmaz
python -m data.pipeline.load_seed --dry-run   # yazmadan raporlar
python -m data.pipeline.load_seed --update    # doğrulanmamış kayıtları listeden günceller
```
