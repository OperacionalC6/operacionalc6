"""
Gera o .streamlit/secrets.toml pronto a partir do .json da conta de serviço Google.

Uso:  python gerar_secrets.py
Depois copie TODO o conteúdo do arquivo gerado e cole em
Streamlit Cloud > Settings > Secrets.
"""

import json
import os
import tomllib
from pathlib import Path


def texto_toml(valor: str) -> str:
    # String JSON entre aspas duplas também é uma string TOML válida
    return json.dumps(valor, ensure_ascii=False)


def perguntar(msg: str) -> str:
    valor = input(msg).strip()
    if valor.startswith("& "):  # PowerShell às vezes adiciona "& " ao arrastar
        valor = valor[2:].strip()
    return valor.strip('"').strip("'")


def ler_credencial(caminho: Path) -> dict | None:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return dados if dados.get("type") == "service_account" else None
    except Exception:  # noqa: BLE001
        return None


def procurar_nos_downloads() -> list[Path]:
    pasta = Path.home() / "Downloads"
    if not pasta.is_dir():
        return []
    candidatos = sorted(pasta.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [f for f in candidatos if ler_credencial(f)]


def escolher_na_janela() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        raiz = tk.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo .json da conta de serviço",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        raiz.destroy()
        return caminho
    except Exception:  # noqa: BLE001
        return ""


def obter_credencial() -> dict:
    achados = procurar_nos_downloads()
    if achados:
        print(f"Encontrei a credencial em: {achados[0]}")
        if perguntar("Usar este arquivo? (S/n): ").lower() in ("", "s", "sim", "y"):
            return ler_credencial(achados[0])

    while True:
        caminho = perguntar(
            "Caminho do arquivo .json (arraste o arquivo para cá, "
            "ou aperte Enter para abrir uma janela): "
        )
        if not caminho:
            caminho = escolher_na_janela()
            if not caminho:
                print("Nenhum arquivo escolhido. Tente de novo.")
                continue
            print(f"Arquivo escolhido: {caminho}")
        arquivo = Path(caminho)
        if not arquivo.is_file():
            print(f"Arquivo não encontrado: {caminho}")
            continue
        cred = ler_credencial(arquivo)
        if cred:
            return cred
        print("Esse arquivo não é o .json de uma conta de serviço do Google. Tente outro.")


def main():
    cred = obter_credencial()

    url = ""
    while "docs.google.com/spreadsheets" not in url:
        url = perguntar("URL da planilha do Google Sheets (https://docs.google.com/spreadsheets/...): ")
    senha = ""
    while not senha:
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
