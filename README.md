# Kassetten-Planungs-System (KPS)

Hackathon-Projekt zur Optimierung der Kassettenplanung fuer Komax A650 CC-Maschinen mit IQC-Technologie.

## Problem

In einem Werk mit mehreren A650 Crimp-to-Crimp Maschinen muessen Produktionsauftraege so geplant werden, dass:
- **Ruestzeiten minimiert** werden (Kassettenwechsel)
- Die **Setup-Maschine** (shared resource, 10-15 min pro Kassette) nicht zum Engpass wird
- **Liefertermine** eingehalten werden
- Der **Durchsatz** maximiert wird

## Architektur

```
data/               # Beispielwerk-Konfiguration
simulator/          # Simulations-Engine
  models.py         # Datenmodell (Plant, Machine, Cassette, Order)
  engine.py         # Diskrete Event-Simulation
scheduler/          # Planungsalgorithmen
  base.py           # Scheduler-Interface
  naive.py          # Baseline: FIFO
  optimized.py      # Optimierter Scheduler (Kassetten-Clustering)
run_simulation.py   # CLI zum Vergleich der Scheduler
```

## Quickstart

```bash
python run_simulation.py
```

## Konzept

### Maschinen-Setup
- **A650 Maschinen**: CC-Maschinen mit IQC-Technologie, Kassettenwechsel < 1 Minute
- **Setup-Maschine**: Dedizierte Station zum Vorbereiten/Einrichten von Kassetten (10-15 min)
- **Kassetten-Pool**: Begrenzte Anzahl Kassetten verschiedener Typen

### Planungsoptimierung
1. **Kassetten-Clustering**: Auftraege gruppieren, die gleiche Kassetten benoetigen
2. **Setup-Pipeline**: Kassetten vorausschauend auf der Setup-Maschine vorbereiten
3. **Lastverteilung**: Auftraege optimal auf die 3 A650 verteilen
