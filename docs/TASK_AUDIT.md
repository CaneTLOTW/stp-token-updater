# STP Token Updater – Aufgabenabgleich

Stand: 2026-08-24

Dieses Dokument trennt Code-Abdeckung von realer Live-Abnahme. Maßgeblich für die beim ersten Review gefundenen Fehler ist zusätzlich `REVIEW_2026-08-24.md`.

## Im aktuellen Code vorhanden

- eigenständige Home-Assistant-Custom-Integration;
- HACS-Metadaten und UI-Config-Flow;
- API-Key oder Administrator-Passwort/Session;
- lokale Statusabfrage des Token-Providers;
- Sponsor-/Trial-Ablaufzeit aus dem Provider-State;
- Trial-JWT-Parser mit `iss`, `sub`, `iat`, `exp` und Fingerprint;
- keine Persistenz vollständiger Trial-JWTs;
- Scheduler `T-48h / T-12h / T-6h / T-1h / expired +6h`;
- getrennte Source-Polling-Intervalle;
- kein Write für gleichen/älteren Kandidaten;
- Dry-Run als sicherer Default;
- Single-POST + verzögerte Read-after-write-Verifikation;
- Erkennung einer dateibasierten Token-Konfiguration;
- HA-Entitäten, Buttons, Events und Repairs;
- Diagnostics ohne Credentials/vollständigen JWT;
- Dashboard- und Push-Beispiel;
- pytest-, HACS- und hassfest-Workflows.

## Im Review korrigierte Fehler

- fehlender Passwort-Konstantenimport im Config Flow;
- inkompatible `SensorEntityDescription`-Positionsargumente;
- falscher Repairs-/Issue-Registry-Import;
- wiederholtes Ausführen desselben Renewal-Checkpoints bei jedem 5-Minuten-Poll;
- Source-Fehler ohne Fortschreiben des Source-Check-Zeitpunkts;
- definite Auth-/Rate-Limit-Fehler wurden in der Write-Verifikation zu stark als unklarer Write behandelt;
- dateibasierte Tokenquelle wurde fälschlich als ungültiger aktiver Token bewertet;
- CI/HACS/Hassfest waren dokumentiert, aber im ersten Commit nicht vorhanden.

## Noch nicht als vollständig abgenommen markieren

1. alle GitHub Actions grün;
2. Installation als realer Config Entry in Home Assistant;
3. Entity Registry und Übersetzungen korrekt;
4. API-Key-Auth live;
5. Passwort-/Session-Auth live;
6. Restart-Verhalten innerhalb der Scheduler-Fenster;
7. Source-Fehler/Recovery ohne Polling-Sturm;
8. ein kontrollierter echter Write mit strikt neuerem Kandidaten;
9. erfolgreicher Readback und automatisches Aufräumen der Repairs.

## Live-Write-Sicherheit

Automatisierte Tests dürfen keinen echten Sponsor-/Trial-Token-Write erzeugen. Ein Live-Test darf nur einmal bewusst erfolgen, wenn der Candidate nachweislich später abläuft als der aktive Token. Bei einem Transport-Timeout wird zuerst der Status gelesen und niemals sofort blind ein zweites POST gesendet.

## Branding

Die sichtbare Produktbezeichnung ist **STP Token Updater** (`Sponsor Token Provider`). Provider-spezifische interne Identifikatoren bleiben nur dort bestehen, wo sie Protokollanforderung oder Home-Assistant-Kompatibilitätsbestandteil sind.
