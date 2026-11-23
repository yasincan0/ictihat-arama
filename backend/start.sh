#!/bin/sh
# Konteyner açılışı: şema -> başlangıç listesi -> vektörleştirme -> API.
# Adımlar tekrar çalıştırılabilir; yalnızca eksik olan işler yapılır.
# İlk açılışta embedding modeli indirilir (~2,2 GB, /models biriminde saklanır).
set -e
cd /app/backend
alembic upgrade head
cd /app
python -m data.pipeline.load_seed
python -m data.pipeline.embed
cd /app/backend
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
