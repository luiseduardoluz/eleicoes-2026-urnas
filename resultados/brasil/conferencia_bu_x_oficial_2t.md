# Fase 0 — 2º turno: integridade e reconciliação

UFs: ac, al, am, ap, ba, ce, df, es, go, ma, mg, ms, mt, pa, pb, pe, pi, pr, rj, rn, ro, rr, rs, sc, se, sp, to, zz

## Urnas por status

| status | urnas |
|---|---|
| ok | 499,178 |
| sem_bu_totalizado | 29 |
| sem_recebimento | 41 |

Seções representadas (principal + agregadas): 517,179

## Reconciliação: soma dos BUs × total oficial por zona

Zonas comparadas: 6,292 — **com divergência: 69**

| métrica | oficial | soma dos BUs | diferença |
|---|---:|---:|---:|
| aptos | 158,745,502 | 158,743,025 | -2,477 |
| comparecimento | 128,236,074 | 128,235,243 | -831 |
| votavel_13 | 64,256,232 | 64,255,787 | -445 |
| votavel_22 | 59,826,041 | 59,825,688 | -353 |
| votavel_95 | 1,430,496 | 1,430,484 | -12 |
| votavel_96 | 2,723,305 | 2,723,284 | -21 |

## Divergências (até 30)

```
shape: (30, 7)
┌─────┬──────────────┬─────────┬────────────────┬─────────┬─────┬───────────┐
│ uf  ┆ cd_municipio ┆ nr_zona ┆ metrica        ┆ oficial ┆ bus ┆ diferenca │
│ --- ┆ ---          ┆ ---     ┆ ---            ┆ ---     ┆ --- ┆ ---       │
│ str ┆ i64          ┆ i64     ┆ str            ┆ i64     ┆ i64 ┆ i64       │
╞═════╪══════════════╪═════════╪════════════════╪═════════╪═════╪═══════════╡
│ zz  ┆ 29173        ┆ 1       ┆ aptos          ┆ 32      ┆ 0   ┆ -32       │
│ zz  ┆ 29173        ┆ 1       ┆ comparecimento ┆ 13      ┆ 0   ┆ -13       │
│ zz  ┆ 29173        ┆ 1       ┆ votavel_22     ┆ 12      ┆ 0   ┆ -12       │
│ zz  ┆ 29173        ┆ 1       ┆ votavel_13     ┆ 1       ┆ 0   ┆ -1        │
│ zz  ┆ 29254        ┆ 1       ┆ aptos          ┆ 91      ┆ 0   ┆ -91       │
│ …   ┆ …            ┆ …       ┆ …              ┆ …       ┆ …   ┆ …         │
│ zz  ┆ 29394        ┆ 1       ┆ votavel_22     ┆ 22      ┆ 0   ┆ -22       │
│ zz  ┆ 29394        ┆ 1       ┆ votavel_13     ┆ 19      ┆ 0   ┆ -19       │
│ zz  ┆ 29424        ┆ 1       ┆ aptos          ┆ 22      ┆ 0   ┆ -22       │
│ zz  ┆ 29521        ┆ 1       ┆ aptos          ┆ 27      ┆ 0   ┆ -27       │
│ zz  ┆ 29564        ┆ 1       ┆ aptos          ┆ 72      ┆ 0   ┆ -72       │
└─────┴──────────────┴─────────┴────────────────┴─────────┴─────┴───────────┘
```

## Urnas fora de `ok` (até 30)

```
shape: (30, 6)
┌─────┬──────────────┬─────────┬──────────┬───────────────────┬───────────┐
│ uf  ┆ cd_municipio ┆ nr_zona ┆ nr_secao ┆ status            ┆ problemas │
│ --- ┆ ---          ┆ ---     ┆ ---      ┆ ---               ┆ ---       │
│ str ┆ i64          ┆ i64     ┆ i64      ┆ str               ┆ str       │
╞═════╪══════════════╪═════════╪══════════╪═══════════════════╪═══════════╡
│ zz  ┆ 29629        ┆ 1       ┆ 3014     ┆ sem_recebimento   ┆           │
│ zz  ┆ 29173        ┆ 1       ┆ 494      ┆ sem_bu_totalizado ┆           │
│ zz  ┆ 29297        ┆ 1       ┆ 495      ┆ sem_bu_totalizado ┆           │
│ zz  ┆ 29580        ┆ 1       ┆ 96       ┆ sem_bu_totalizado ┆           │
│ zz  ┆ 29777        ┆ 1       ┆ 127      ┆ sem_bu_totalizado ┆           │
│ …   ┆ …            ┆ …       ┆ …        ┆ …                 ┆ …         │
│ zz  ┆ 99341        ┆ 1       ┆ 1308     ┆ sem_recebimento   ┆           │
│ zz  ┆ 29300        ┆ 1       ┆ 6        ┆ sem_bu_totalizado ┆           │
│ zz  ┆ 29912        ┆ 1       ┆ 150      ┆ sem_bu_totalizado ┆           │
│ zz  ┆ 29521        ┆ 1       ┆ 83       ┆ sem_recebimento   ┆           │
│ zz  ┆ 29564        ┆ 1       ┆ 91       ┆ sem_bu_totalizado ┆           │
└─────┴──────────────┴─────────┴──────────┴───────────────────┴───────────┘
```
