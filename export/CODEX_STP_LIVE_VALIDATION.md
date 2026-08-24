# STP Token Updater – Live-Validierung

Stand: 2026-08-25 (UTC)  
Repository: `CaneTLOTW/stp-token-updater`  
Startstand: `d673fe9fcd8d36cba09bbeb8b4bf51d21f91a324`

## Ergebnis

STP wurde im laufenden Home-Assistant-System als Custom Integration installiert
und mit aktivem **Dry-Run** eingerichtet. Die produktive Provider-Verbindung,
die API-Key-Authentifizierung, Statusabfrage, Trial-Quellenprüfung, Entitäten,
manuellen Buttons, Reconfigure, Options, Persistenz, Restart und Diagnostics
wurden ohne einen Sponsor-Token-POST validiert.

Der abschließende Schreibtest wurde korrekt **nicht ausgeführt**: Der frisch
beobachtete Trial-Kandidat läuft nicht später ab als der aktive Token. Ein POST
ohne strikt neueren Kandidaten wäre gegen die Sicherheitsvorgabe.

## Implementierte Korrekturen

| Commit | Änderung | Begründung |
| --- | --- | --- |
| `61a40ff` | Abgelaufene Retry-After-Gates werden nach ihrer fälligen Entscheidung sauber entfernt; ein manueller Apply umgeht kein aktives State/Auth-Rate-Limit. | Verhindert einen dauerhaft hängenden `rate_limit`-Repair bzw. ein Wiederholen vor Ablauf von Retry-After. |
| lokal `575e1a8` | GitHub-Actions-Pip-Cache entfernt, Manifest-Schlüssel HASSfest-konform sortiert und nicht benötigtes `async_setup` entfernt. | Behebt die zuvor beobachteten CI-/HASSfest-Befunde. Die Workflow-Datei selbst ist wegen GitHub-Scope noch nicht veröffentlichbar. |
| Client-Regressionstest | API-Key-Bearer-Header sowie Passwort-Cookie, ein 401 und genau ein Re-Login. | Sichert die Sicherheits- und Sessionlogik ohne einen Live-Fehler zu provozieren. |

### Rate-Limit-Regression

Die Regressionstests decken insbesondere diese zuvor fehleranfälligen Fälle ab:

1. Ein abgelaufenes Write-Retry-After mit gleichem/älterem Kandidaten entfernt
   Gate und Repair und verursacht keinen unmittelbaren zweiten Source-Request.
2. Ein abgelaufenes Write-Gate mit neuerem Kandidaten führt zuerst den frischen
   Quellencheck und die Dry-Run-Entscheidung aus.
3. Ein beim erneuten Quellencheck empfangenes, neues zukünftiges Retry-After
   bleibt erhalten.
4. Ein noch aktives State/Auth-Retry-After blockiert auch einen manuellen
   Apply-Button.

## Statische Validierung

| Prüfung | Ergebnis |
| --- | --- |
| `python -m compileall -q custom_components/stp_token_updater tests` | bestanden |
| JSON-Validierung von Manifest sowie deutscher und englischer Übersetzung | bestanden |
| `git diff --check` | bestanden |
| lokale `pytest`-Ausführung | nicht möglich: Das Live-System stellt weder `pytest` noch die HA-Testabhängigkeiten bereit. |
| CI-Workflow | Korrektur ist vorbereitet; erneuter GitHub-Lauf ist durch den Workflow-Scope-Blocker ausstehend. |

Die CI-Analyse vor der Korrektur zeigte einen ungültig konfigurierten Pip-Cache
im Testworkflow sowie zwei HASSfest-Befunde (Manifest-Reihenfolge und unnötiges
`async_setup`). Die genannten Codeänderungen adressieren diese Punkte.

## Live-Installation und Config Flow

| Prüffall | Ergebnis |
| --- | --- |
| Integration erkannt und geladen | bestanden |
| API-Key-Config-Flow, reale Verbindung | bestanden |
| Ungültige URL | erwarteter Fehler `invalid_url` |
| Nicht erreichbarer Testhost | erwarteter Fehler `cannot_connect` |
| Ungültiger API-Key gegen realen Provider | erwarteter Fehler `invalid_auth` |
| Doppelanlage derselben normalisierten URL | erwarteter Abbruch `already_configured` |
| Reconfigure mit bestehender URL | erwarteter Abschluss `reconfigure_successful` |
| Options Flow | bestanden; `automatic_updates=true`, `dry_run=true`, Statusintervall 5 Minuten |
| Passwort-/Cookie-Protokoll | bestanden: Login erzeugt Auth-Cookie, geschützter Status-Endpunkt akzeptiert die Session |
| Passwort-401-Re-Login | durch den neuen deterministischen Client-Regressionstest abgedeckt |
| Reauth-UI komplett durchlaufen | nicht automatisiert ausführbar über die verfügbare Core-REST-Schnittstelle; siehe Blocker. |

Der Config Entry enthält ausschließlich die erwarteten Konfigurationsschlüssel
(Provider-URL, Authentifizierungsmethode und das jeweils gewählte Credential).
Credentials wurden zu keinem Zeitpunkt ausgegeben oder exportiert.

## Laufzeit, Scheduler und Entitäten

Nach der ersten Prüfung sowie erneut nach einem vollständigen Home-Assistant-
Restart war der Config Entry geladen und die Provider-API erreichbar.

| Feld | Ergebnis |
| --- | --- |
| Updater-Status | `healthy` |
| Aktiver Ablauf | 2026-09-03T18:00:00+00:00 |
| Trial-Kandidat-Ablauf | 2026-09-03T18:00:00+00:00 |
| Kandidat neuer als aktiv | nein |
| Nächster regulärer Scheduler-Versuch | 2026-09-01T18:00:00+00:00 (T-48 h) |
| Reale Schreibversuche | 0 |

Alle erwarteten 21 Entitäten wurden erstellt: 13 Sensoren, 5 Binary Sensors
und 3 Buttons. Die Buttons wurden ohne Schreibvorgang geprüft:

* **Trial prüfen** aktualisierte die Quellenprüfung erfolgreich.
* **Aktiven Token verifizieren** aktualisierte die Providerprüfung erfolgreich.
* **Trial jetzt anwenden** erkannte `no_newer_candidate`; der Schreibzähler
  blieb bei `0`.

Es existiert aktuell kein berechtigter Warn-, Critical- oder Expired-Fall.
Deshalb wurden keine künstlichen Repairs oder Warn-Events im produktiven System
erzeugt. Die Status-/Scheduler- und Retry-After-Pfade dafür sind durch die
statischen Tests abgedeckt. Ein gesunder Zustand produziert erwartungsgemäß
keinen STP-Repair und kein Warn-Event.

## Restart, Übersetzungen und Diagnostics

* Vollständiger Home-Assistant-Core-Restart: bestanden.
* Nach dem Restart: STP-Entry wieder `loaded`, Status `healthy`, API erreichbar,
  Scheduler-Zeitpunkt erhalten.
* `ha core check`: bestanden.
* Deutsche und englische Übersetzungsdateien enthalten Config-, Options-,
  Entity- und Repairs-Abschnitte und sind valides JSON.
* Live-Diagnostics-Endpunkt: HTTP 200. Strukturell geprüft; keine API-Keys,
  Passwörter, Auth-Cookies oder JWT-Marker enthalten. Provider-Adresse und
  Credentials sind in den Diagnostics redigiert.
* Persistierter STP-Metadatenspeicher: nur Ablauf-, Fingerprint-, Retry- und
  Zeitmetadaten; keine Credential-Felder und keine JWT-artigen Werte.

## Echter Schreibtest (letzter Acceptance-Schritt)

**Status: SKIPPED – kein neuerer Kandidat.**

Der aktive Token und der frisch geprüfte Kandidat hatten dieselbe Ablaufzeit.
Die zwingende Bedingung `candidate.expires_at > active.expires_at` war daher
nicht erfüllt. Es wurde kein `POST /api/config/sponsortoken` gesendet, kein
Timeout-Retry ausgelöst und der Dry-Run blieb aktiviert.

Ein echter Write-Test ist erst zulässig, wenn eine erneute Quellenprüfung einen
strikt späteren Kandidaten ergibt. Dann Dry-Run bewusst deaktivieren, Kandidat
und aktiven Ablauf unmittelbar vorher erneut lesen, höchstens einmal anwenden,
Read-after-write prüfen und Dry-Run sofort wieder aktivieren. Bei einem
Timeout darf ausschließlich der Readback erfolgen, niemals ein blinder zweiter
POST.

## Sicherheitsprüfung

* Keine vollständigen JWTs, API-Keys, Passwörter oder Cookies wurden geloggt,
  in Entitäten, Diagnostics, Tests oder diesen Bericht geschrieben.
* Kein Sponsor-Token wurde testweise geschrieben.
* Die öffentliche Trial-Quelle wurde nur für die notwendige Setup-/Button-
  Prüfung abgefragt; es wurden keine aggressiven Wiederholungsabfragen
  durchgeführt.
* Die Runtime-Persistenz speichert nur gekürzte Fingerprints und Metadaten.

## Verbleibende menschliche Blocker

1. **GitHub OAuth-Workflow-Scope:** Die Workflow-Datei kann ohne einen Token
   mit `workflow` Scope nicht nach GitHub gepusht werden. Alle davon
   unabhängigen Code-, Test- und Berichtänderungen sind veröffentlicht.
2. **HACS-Repository-Metadaten:** Die HACS-Action beanstandet die fehlende
   GitHub-Repository-Beschreibung und gültige Topics. Das sind
   Repository-Einstellungen in GitHub, keine Codeänderung.
3. **Vollautomatische Reauth-UI:** Home Assistants Core-REST-Endpunkt kann
   User- und Reconfigure-Flows ausführen, aber keinen Reauth-Flow initiieren.
   Der reale Passwort-Login/Sessionpfad und der 401-Re-Login sind validiert;
   die vollständige Reauth-Dialognavigation sollte bei einer echten Credential-
   Ablehnung einmal manuell bestätigt werden.
