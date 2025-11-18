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
    title = header_match.group(2).strip()

    # 2. Processar Letra (trabalha com linhas originais, não stripped)
    raw_body_lines = block.splitlines()[1:]  # Pula o cabeçalho

    lyrics_parts = []
    current_label = ""
    current_buffer = []
    next_verse_number = 1
    expecting_new_block = False

    def flush_buffer():
        if current_label and current_buffer:
            text = "\n".join(current_buffer)
            lyrics_parts.append(f"[{current_label}]\n{text}")
        current_buffer.clear()

    for line in raw_body_lines:
        stripped = line.strip()

        # Ignora linhas completamente vazias
        if not stripped:
            # Linha vazia indica fim do bloco atual
            if current_buffer:
                expecting_new_block = True
            continue

        # Detecta Verso (ex: "1. Texto" ou "1 Texto")
        verse_match = re.match(r"^(\d+)\s*\.?(.*)", stripped)

        # Detecta Coro
        chorus_match = re.match(
            r"^(?:CORO|Coro)(?:\s*:)?\s*(.*)", stripped, re.IGNORECASE
        )

        if verse_match:
            flush_buffer()
            verse_num = int(verse_match.group(1))
            next_verse_number = verse_num + 1
            current_label = f"Verse {verse_num}"
            content = verse_match.group(2).strip()
            if content:
                current_buffer.append(content)
            expecting_new_block = False

        elif chorus_match:
            flush_buffer()
            current_label = "Chorus"
            content = chorus_match.group(1).strip()
            if content:
                current_buffer.append(content)
            expecting_new_block = False

        else:
            # Linha de texto normal
            if expecting_new_block:
                # Novo bloco após linha vazia
                flush_buffer()
                current_label = f"Verse {next_verse_number}"
                next_verse_number += 1
                current_buffer.append(stripped)
                expecting_new_block = False
            elif current_label:
                # Continuação do bloco atual
                current_buffer.append(stripped)
            else:
                # Primeiro bloco sem numeração
                current_label = "Verse 1"
                next_verse_number = 2
                current_buffer.append(stripped)
                expecting_new_block = False

    flush_buffer()  # Salva o último bloco

    return {"no": hino_id, "title": title, "lyrics": "\n\n".join(lyrics_parts)}


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
            # Salva JSON (mantém \n escapado)
            json_file_name = f"{hymn_data['no']}.json"
            json_file_path = os.path.join(OUTPUT_JSON_DIR, json_file_name)

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(hymn_data, f, indent=2, ensure_ascii=False)

            # Salva Markdown (com quebras de linha reais)
            md_file_name = f"{hymn_data['no']}.md"
            md_file_path = os.path.join(OUTPUT_MD_DIR, md_file_name)

            md_content = f"""---
no: {hymn_data['no']}
title: {hymn_data['title']}
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
