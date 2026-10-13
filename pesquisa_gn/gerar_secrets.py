"""
Gera o .streamlit/secrets.toml pronto a partir do .json da conta de serviço Google.

Uso:  python gerar_secrets.py
Depois copie TODO o conteúdo do arquivo gerado e cole em
Streamlit Cloud > Settings > Secrets.
"""

import json
import os
import sys
import tomllib
from pathlib import Path


def texto_toml(valor: str) -> str:
    # String JSON entre aspas duplas também é uma string TOML válida
    return json.dumps(valor, ensure_ascii=False)


def perguntar(msg: str) -> str:
    return input(msg).strip().strip('"').strip("'")


def main():
    caminho = perguntar("Caminho do arquivo .json (pode arrastar o arquivo para cá): ")
    try:
        cred = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Não consegui ler o .json: {e}")
    if cred.get("type") != "service_account":
        sys.exit("Esse .json não parece ser de uma conta de serviço (type != service_account).")

    url = perguntar("URL da planilha do Google Sheets: ")
    senha = perguntar("Senha do painel do gestor: ")

    linhas = [
        f"ADMIN_PASSWORD = {texto_toml(senha)}",
        "",
        "[gsheets]",
        f"spreadsheet_url = {texto_toml(url)}",
        'worksheet = "Respostas"',
        "",
        "[gcp_service_account]",
    ]
    linhas += [f"{k} = {texto_toml(str(v))}" for k, v in cred.items()]
    conteudo = "\n".join(linhas) + "\n"

    tomllib.loads(conteudo)  # garante que o TOML é válido

    destino = Path(__file__).parent / ".streamlit" / "secrets.toml"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")

    print(f"\nOK! Arquivo gerado: {destino}")
    print(f"Compartilhe a planilha como EDITOR com: {cred.get('client_email')}")
    print("Copie TODO o conteúdo do arquivo e cole em Streamlit Cloud > Settings > Secrets.")
    if os.name == "nt":
        os.startfile(destino)  # abre no Bloco de Notas


if __name__ == "__main__":
    main()
