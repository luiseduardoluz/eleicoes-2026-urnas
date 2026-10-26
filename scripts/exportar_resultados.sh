#!/usr/bin/env bash
# Copia de data/ (fora do git) para resultados/ (versionado) os resumos que podem ser publicados.
# Ficam de fora os BUs e logs brutos e qualquer arquivo com registro voto a voto: o log traz o título de
# eleitor dos mesários. CSVs grandes vão comprimidos (gzip -n: sem data no cabeçalho, cópia reprodutível).
set -euo pipefail
cd "$(dirname "$0")/.."
D=data
R=resultados

mkdir -p "$R/brasil" "$R/logs_ba"
cp "$D/relatorios/fase0_2t.md" "$R/brasil/conferencia_bu_x_oficial_2t.md"
cp "$D/analise/decomposicao_ufs.csv" "$R/brasil/"
cp "$D/analise/fluxos/decomposicao_brasil.csv" "$D/analise/fluxos/fluxos_zonas.csv" "$R/brasil/"
cp "$D/analise/brasil/resumo_brasil.csv" "$R/brasil/resumo_urna_a_urna.csv"
gzip -n -c "$D/analise/brasil/sinalizadas_brasil.csv" > "$R/brasil/urnas_sinalizadas.csv.gz"

cp "$D/relatorios/fase0_1t.md" "$R/brasil/conferencia_bu_x_oficial_1t.md"  # só as UFs com o 1º turno coletado

for uf in ac ba rr; do
  mkdir -p "$R/$uf"
  cp "$D/analise/$uf/relatorio_$uf.html" "$D/analise/$uf/sensibilidade_$uf.csv" "$D/analise/$uf/transferencias_$uf.csv" "$R/$uf/"
  gzip -n -c "$D/analise/$uf/urnas_$uf.csv" > "$R/$uf/urnas_$uf.csv.gz"
done

cp "$D/analise/logs/ba/perfil_horas.csv" "$R/logs_ba/"
gzip -n -c "$D/analise/logs/ba/fim_do_dia.csv" > "$R/logs_ba/fim_do_dia.csv.gz"

du -sh "$R"
