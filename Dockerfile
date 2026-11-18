FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /srv/backend
COPY frontend /srv/frontend
COPY corpus_national /srv/corpus_national
COPY scripts /srv/scripts
COPY database /srv/database
ENV PYTHONPATH=/srv/backend
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
COPY frontend/auth-config.render.js /srv/frontend/auth-config.js
