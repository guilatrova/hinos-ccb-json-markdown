#!/usr/bin/env bash
set -euo pipefail

# fetch_ccb.sh - Retorna o conteúdo JSON de um hino CCB pelo número.
# Uso: ./fetch_ccb.sh <numero>

if [ "$#" -ne 1 ]; then
  echo "Uso: $0 <numero>" >&2
  exit 1
fi

NUMERO="$1"

if ! [[ "$NUMERO" =~ ^[0-9]+$ ]]; then
  echo "Erro: '$NUMERO' não é um número válido." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JSON_FILE="$SCRIPT_DIR/output/ccb_json/${NUMERO}.json"

if [ ! -f "$JSON_FILE" ]; then
  echo "Erro: hino $NUMERO não encontrado ($JSON_FILE)." >&2
  exit 1
fi

cat "$JSON_FILE"
