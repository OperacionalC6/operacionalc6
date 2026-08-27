FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000

# Roda migrations + seed do admin antes de subir a API — necessário pra
# funcionar num serviço gerenciado (Render) sem precisar rodar comandos
# manualmente a cada deploy. A porta vem da variável $PORT (Render define
# a dele; localmente cai no 8000 do EXPOSE acima).
ENTRYPOINT ["./entrypoint.sh"]
