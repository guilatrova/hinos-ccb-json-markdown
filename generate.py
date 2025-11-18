import re
import json
import os
from typing import Dict, List, Optional
from rich.console import Console
from rich.progress import track

OUTPUT_DIR = "./output"
OUTPUT_JSON_DIR = "./output/json"
OUTPUT_MD_DIR = "./output/markdown"
INPUT_FILE = "./Hinario CCB 5 Cantado.txt"

console = Console()


def parse_hymn_block(block: str) -> Optional[Dict]:
    """Processa um bloco de texto cru contendo um único hino."""
    lines = [l.strip() for l in block.splitlines() if l.strip()]

    if not lines:
        return None

    # 1. Extrair Cabeçalho (Hino X – Título)
    header_pattern = r"Hino\s+(\d+)\s+[–-]\s+(.+)"
    header_match = re.search(header_pattern, lines[0], re.IGNORECASE)

    if not header_match:
        return None

    hino_id = int(header_match.group(1))
    titulo = header_match.group(2).strip()

    # 2. Processar Letra
    lyrics_parts = []
    current_label = ""
    current_buffer = []

    def flush_buffer():
        if current_label and current_buffer:
            text = "\n".join(current_buffer)
            lyrics_parts.append(f"[{current_label}]\n{text}")
        current_buffer.clear()

    # Pula a linha do título e itera sobre o corpo
    for line in lines[1:]:
        # Detecta Verso (ex: "1. Texto" ou "1 Texto")
        verse_match = re.match(r"^(\d+)\s*\.?(.*)", line)

        # Detecta Coro
        chorus_match = re.match(r"^(?:CORO|Coro)(?:\s*:)?\s*(.*)", line, re.IGNORECASE)

        if verse_match:
            flush_buffer()
            current_label = f"Verse {verse_match.group(1)}"
            content = verse_match.group(2).strip()
            if content:
                current_buffer.append(content)

        elif chorus_match:
            flush_buffer()
            current_label = "Chorus"
            content = chorus_match.group(1).strip()
            if content:
                current_buffer.append(content)

        else:
            # Linha de continuação da estrofe anterior
            if current_label:
                current_buffer.append(line)

    flush_buffer()  # Salva o último bloco

    return {"id": hino_id, "titulo": titulo, "lyrics": "\n\n".join(lyrics_parts)}


def main():
    if not os.path.exists(OUTPUT_JSON_DIR):
        os.makedirs(OUTPUT_JSON_DIR)

    if not os.path.exists(OUTPUT_MD_DIR):
        os.makedirs(OUTPUT_MD_DIR)

    if not os.path.exists(INPUT_FILE):
        console.print(f"[bold red]Arquivo {INPUT_FILE} não encontrado.[/bold red]")
        return

    console.print(f"[bold blue]Lendo arquivo:[/bold blue] {INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Divide o arquivo inteiro baseando-se no marcador de página/título
    # Regex busca o padrão "Hino X" precedido por form feed (\x0c) ou início de linha
    raw_hymns = re.split(r"(?=\f?Hino\s+\d+\s+[–-])", content)

    # Filtra strings vazias resultantes do split
    raw_hymns = [h for h in raw_hymns if h.strip()]

    for raw_block in track(raw_hymns, description="Processando hinos..."):
        hymn_data = parse_hymn_block(raw_block)

        if hymn_data:
            # Salva JSON
            json_file_name = f"{hymn_data['id']}.json"
            json_file_path = os.path.join(OUTPUT_JSON_DIR, json_file_name)

            # Salva com quebras de linha reais
            json_str = json.dumps(hymn_data, indent=2, ensure_ascii=False)
            # Substitui \n escapado por quebra de linha real
            json_str = json_str.replace("\\n", "\n")

            with open(json_file_path, "w", encoding="utf-8") as f:
                f.write(json_str)

            # Salva Markdown
            md_file_name = f"{hymn_data['id']}.md"
            md_file_path = os.path.join(OUTPUT_MD_DIR, md_file_name)

            md_content = f"""---
id: {hymn_data['id']}
titulo: {hymn_data['titulo']}
---

{hymn_data['lyrics']}
"""

            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(md_content)

    console.print(
        f"[bold green]Sucesso! {len(raw_hymns)} hinos exportados para JSON e Markdown[/bold green]"
    )


if __name__ == "__main__":
    main()
