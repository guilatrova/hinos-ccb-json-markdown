import re
import json
import os
from typing import Dict, List, Optional
from rich.console import Console
from rich.progress import track

OUTPUT_DIR = "./output"
OUTPUT_JSON_DIR = "./output/ccb_casteliano_json"
OUTPUT_MD_DIR = "./output/ccb_casteliano_markdown"
INPUT_FILE = "./Hinario CCB 5 Casteliano.txt"

console = Console()


def parse_hymn_block(block: str) -> Optional[Dict]:
    """Processa um bloco de texto cru contendo um único hino."""
    raw_lines = block.splitlines()

    # Encontra a linha do cabeçalho
    header_line_idx = -1
    # Pattern for "Number Title" (e.g. "1 Cristo, M aestro...")
    # Handles optional form feed at start of line
    # We use ^ to ensure it's at the start of the line (in the context of the block)
    # Note: block.splitlines() removes \n, so we check each line.

    for i, line in enumerate(raw_lines):
        # Check if line starts with Number + Space + Text
        # We allow optional form feed \f at the start
        match = re.match(r"^\f?(\d+)\s+(.+)", line)

        if match:
            # Extra check: ensure it's not a verse (verses usually have "1." or are indented)
            # If the line was indented, re.match with ^ would fail unless we stripped.
            # But we didn't strip 'line'. So indented verses won't match.
            # This is good. Headers are expected to be at the start of the line.

            header_line_idx = i
            hino_id = int(match.group(1))
            title = match.group(2).strip()
            break

    if header_line_idx == -1:
        return None

    # Verificar se o título continua na próxima linha
    body_start_idx = header_line_idx + 1

    if body_start_idx < len(raw_lines):
        next_line = raw_lines[body_start_idx].strip()

        # Verifica se há uma linha de continuação do título
        # Critérios: linha não vazia, não começa com número, não é CORO
        if (
            next_line
            and not re.match(r"^\d+\s*\.?", next_line)
            and not re.match(r"^(?:CORO|Coro)", next_line, re.IGNORECASE)
        ):
            # Verifica se após essa linha há linha vazia (confirma que é título)
            if (
                body_start_idx + 1 < len(raw_lines)
                and not raw_lines[body_start_idx + 1].strip()
            ):
                title += " " + next_line
                body_start_idx += 1

    # 2. Processar Letra
    raw_body_lines = raw_lines[body_start_idx:]

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

        if not stripped:
            if current_buffer:
                expecting_new_block = True
            continue

        # Calculate indentation
        indentation = len(line) - len(line.lstrip())

        # Detecta Verso (ex: "1. Texto")
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

        elif indentation >= 5:
            # Implicit Chorus based on indentation
            if current_label != "Chorus":
                flush_buffer()
                current_label = "Chorus"
            current_buffer.append(stripped)
            expecting_new_block = False

        else:
            if expecting_new_block:
                flush_buffer()
                current_label = f"Verse {next_verse_number}"
                next_verse_number += 1
                current_buffer.append(stripped)
                expecting_new_block = False
            elif current_label == "Chorus":
                # We were in Chorus, but now indentation dropped.
                # Assume new verse if we were expecting one, or just a new block.
                # Since we don't have a number, we auto-increment.
                flush_buffer()
                current_label = f"Verse {next_verse_number}"
                next_verse_number += 1
                current_buffer.append(stripped)
            elif current_label:
                current_buffer.append(stripped)
            else:
                current_label = "Verse 1"
                next_verse_number = 2
                current_buffer.append(stripped)
                expecting_new_block = False

    flush_buffer()

    if not lyrics_parts:
        return None

    title = re.sub(r"\s*\(.*?\)\s*", "", title).strip()
    title = title.rstrip(" –")
    # Clean up extra spaces in title
    title = re.sub(r"\s+", " ", title)

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

    # Split by "Number Title" at start of line (possibly with form feed)
    # Regex: Lookahead for (Optional Form Feed) + (Start of Line) + (Digits) + (Space)
    # We use re.MULTILINE so ^ matches start of line.
    raw_hymns = re.split(r"(?=^\f?\d+\s+)", content, flags=re.MULTILINE)

    # Filtra strings vazias
    raw_hymns = [h for h in raw_hymns if h.strip()]

    stop_processing = False
    count = 0
    for raw_block in track(raw_hymns, description="Processando hinos..."):
        if stop_processing:
            break

        # Check for Index marker
        if "Índice" in raw_block:
            # Truncate block at Índice
            raw_block = raw_block.split("Índice")[0]
            stop_processing = True

        hymn_data = parse_hymn_block(raw_block)

        if hymn_data:
            count += 1
            json_file_name = f"{hymn_data['no']}.json"
            json_file_path = os.path.join(OUTPUT_JSON_DIR, json_file_name)

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(hymn_data, f, indent=2, ensure_ascii=False)

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
        f"[bold green]Sucesso! {count} hinos exportados para JSON e Markdown[/bold green]"
    )


if __name__ == "__main__":
    main()
