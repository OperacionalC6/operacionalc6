# A tag da imagem (v1.46.0) precisa bater EXATAMENTE com a versão do pacote
# `playwright` fixada em requirements.txt — essa imagem só tem os navegadores
# baixados pra essa versão específica. Se atualizar um, atualiza o outro
# junto (descoberto em produção: pip instalando playwright mais novo que a
# imagem quebra com "Executable doesn't exist").
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
