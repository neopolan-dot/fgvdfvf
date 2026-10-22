# Joybuy Happy Hour Cloud Scanner

Ein täglicher, lesender Playwright-Scan der öffentlichen Happy-Hour-Seite.
Der Browser läuft auf einem **Standard-Linux-Rechner von GitHub Actions**.
Ein eigener PC, VMware, ein LLM-API-Schlüssel oder ein Browser-Abo wird nicht benötigt.

## Ablauf

- Geplanter Start: täglich 19:00 Uhr, Europe/Berlin (Sommer-/Winterzeit berücksichtigt).
- Vorinstallierter Chrome mit dem Playwright-Geräteprofil iPhone 13, einschließlich Safari-User-Agent.
  Der Renderer bleibt Chrome; für die mobile Seitendarstellung werden iPhone-Kennung,
  Bildschirmgröße und Touch-Einstellungen verwendet. WebKit bleibt im Skript optional verfügbar.
- Die heutigen Reiter 20, 21 und 22 Uhr werden einzeln angeklickt.
- Die Auswahl muss über die sichtbare Markierung oder semantische Attribute bestätigt sein.
- Nach jedem Scrollschritt wird mindestens 5,5 Sekunden gewartet.
- Produkt-IDs werden während des Scrollens gesammelt. Drei stabile Runden am Listenende beenden die Erfassung.
- Ein Zeitlimit oder eine unbestätigte Auswahl wird als unvollständig gemeldet.

## Ergebnisse

Nach einem Lauf stehen unter `joybuy/results/` die Dateien `latest.json`,
`deals.csv` und `summary.md`. Sie enthalten öffentliche Produktdaten und einen
Prüfstatus je Zeitfenster. Eine stabile geladene Liste ist keine Garantie dafür,
dass Joybuy nicht später weitere Angebote ergänzt. UVP und WAR sind Angaben
von Joybuy, keine unabhängigen Marktpreise. Kaufbarkeit wird nicht geprüft.

Die erste Ausführung ist ein Live-Test. Erst dessen Ergebnis zeigt, ob Joybuy
die Seite aus dieser Cloud-Umgebung vollständig ausliefert und ob die
Auswahlmarkierungen zuverlässig erkannt werden.

## Kosten und Zeitplan

In einem **öffentlichen Repository** sind Standard-GitHub-Runner laut GitHub
kostenfrei. Dieser Workflow nutzt `ubuntu-24.04`, keine größeren Runner und
keine kostenpflichtigen Drittanbieter-APIs. Er lädt keine Actions-Artefakte hoch
und verwendet keinen Actions-Cache. Ergebnisse und Logs werden klein gehalten.

GitHub kann geplante Starts verzögern oder auslassen. 19:00 Uhr ist der
Sollstart, keine sekundengenaue Zusage. Änderungen am Skript und manuelle
Workflow-Ausführungen lösen ebenfalls einen Scan aus.

Code, Protokolle und Deal-Ergebnisse sind in einem öffentlichen Repository
einsehbar. Es werden keine Zugangsdaten benötigt oder veröffentlicht.

## Quellen

- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://playwright.dev/python/docs/emulation
- https://playwright.dev/python/docs/ci
