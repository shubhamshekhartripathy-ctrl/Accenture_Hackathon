FROM python:3.11-slim
WORKDIR /srv/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests
EXPOSE 8000
CMD ["sh", "-c", "alembic -c /srv/app/alembic.ini upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
