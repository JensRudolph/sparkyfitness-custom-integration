<p align="right">
  <strong>Deutsch</strong> · <a href="README.md">English</a>
</p>

<p align="center">
  <img src="custom_components/sparkyfitness/brand/icon.png" alt="SparkyFitness" width="150">
</p>

<h1 align="center">SparkyFitness für Home Assistant</h1>

<p align="center">
  Deine selbst gehosteten Fitnessdaten in Home Assistant — direkt über MCP,
  ohne Cloud-Relay und ohne LLM.
</p>

> [!IMPORTANT]
> API-Schlüssel und Gesundheitsdaten werden ausschließlich zwischen Home
> Assistant und dem von dir konfigurierten SparkyFitness-MCP-Endpunkt übertragen.
> Die Integration besitzt keine Telemetrie, kein Cloud-Backend und keinen
> Zugriff auf Datenbank oder private REST-Schnittstellen.

## Das bietet die Integration

- Sensoren für Ernährung, Wasser, Check-ins, Ziele, Trends und Fasten.
- Binärsensoren für aktives Fasten und tägliche Gewohnheiten.
- Einen schreibgeschützten Trainingskalender.
- Optionale Habit-Auswertungen für 7/30 Tage und Serien.
- Home-Assistant-Actions zum Erfassen und Korrigieren unterstützter Daten.
- Mehrere Benutzer oder Instanzen mit jeweils eigenem API-Schlüssel.
- Bedarfsgesteuertes Polling und getrennte Fehlerbehandlung je Datenbereich.
- Technische Diagnosen ohne persönliche Gesundheitswerte.
- Deutsche und englische UI- und Entitätsübersetzungen.

## Schnellstart

1. Erstelle in SparkyFitness unter
   **Settings → Developer & Integrations → API Key Management** einen API-Schlüssel.
2. Füge in HACS
   `https://github.com/JensRudolph/sparkyfitness-custom-integration`
   als benutzerdefiniertes Repository vom Typ **Integration** hinzu.
3. Installiere **SparkyFitness** und starte Home Assistant neu.
4. Öffne **Einstellungen → Geräte & Dienste → Integration hinzufügen** und
   suche nach **SparkyFitness**.
5. Trage die SparkyFitness-URL und den persönlichen API-Schlüssel ein.

## Vollständige Dokumentation

Die technische Referenz wird auf Englisch gepflegt:

- [Dokumentationsübersicht](docs/README.md)
- [Installation](docs/installation.md)
- [Konfiguration und mehrere API-Schlüssel](docs/configuration.md)
- [Entitäten](docs/entities.md)
- [Actions](docs/actions.md)
- [Automationsbeispiele](docs/automations.md)
- [Trainingskalender](docs/workout-calendar.md)
- [Gewohnheiten](docs/habits.md)
- [Sicherheit und Datenschutz](docs/security-and-privacy.md)
- [Fehlerbehebung](docs/troubleshooting.md)
- [Kompatibilität und Einschränkungen](docs/compatibility.md)
- [Changelog](CHANGELOG.md)

## Lizenz

[MIT](LICENSE)
