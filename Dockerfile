FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 pump \
    && useradd --uid 10001 --gid pump --no-create-home pump \
    && mkdir /data && chown pump:pump /data
COPY --chown=pump:pump . .
USER pump
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
