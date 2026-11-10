# Brückenversion für den Wechsel auf das Original V2.6.2

**Entwurf zum Testen, kein veröffentlichtes Release und keine Garantie für einen
fehlerfreien Hardwarebetrieb.** Ziel ist ausschließlich
`nussfuellung/paradigma-homeassistant` Tag **V2.6.2**, Commit
`5db9299fca3a67680a57e9ff0fa8e281ffe7717a`. Nicht ungeprüft auf spätere Tags wechseln.
Der PR geht zunächst gegen `tomquist/paradigma-homeassistant:main`, nicht upstream.

## Was diese Version übernimmt

Der ursprüngliche Fork speichert Konfigurationsversion 1. Das Original erwartet
Version 2, enthält im genannten Tag aber keinen Migrationshandler. Außerdem
ändert es die internen `unique_id`s. Die Brücke migriert diese IDs über die
öffentlichen Home-Assistant-Registry-APIs und hebt den bestehenden Eintrag erst
anschließend auf Konfigurationsversion 2 an. Es werden keine Modbus-Schreibzugriffe
ausgelöst und keine `.storage`-Dateien bearbeitet.

Die öffentlichen `entity_id`s (auch selbst gewählte Namen), Registry-Zeilen,
Benutzer-Metadaten und der Konfigurationseintrag bleiben bestehen. So bleiben
Referenzen in Automationen, Dashboards und Helfern sowie die bisherigen
Historien-Zuordnungen erhalten. Dies ist keine Konvertierung historischer Werte
oder Statistiken bei geänderter Zustandssemantik. Auch deaktivierte Entitäten und
inzwischen abgewählte Komponenten werden berücksichtigt.

Sensoren, HK1/HK2-Sollwertsteller und die EMS-Steuerungen erhalten die IDs des
Originals. Die Plattformen dieser Brücke erzeugen bereits dieselben IDs, auch
bei einer neuen Einrichtung. Nicht unterstützte/ unbekannte Entitäten sowie
Switch/Water-Heater-IDs bleiben unverändert. Ein Zahlenwert wird niemals in einen
Sensor umgewandelt. IP, Port, Name, normale Slave-ID, Komponentenflags,
Abfrageintervall und sonstige Daten/Optionen werden nicht verändert.

## Vorher prüfen und sichern

1. Notiere die bisherige Fork-Version bzw. deren Commit. Suche die Paradigma-
   Entitäten in Automationen, Skripten, Szenen, Dashboards und Helfern (auch
   Min/Max/UI-Gruppen sowie Node-RED/AppDaemon). Die IDs bleiben gleich, aber die
   folgenden Verhaltensunterschiede müssen geprüft werden.
2. Erstelle ein **vollständiges Home-Assistant-Backup vor der Brücke** und sichere
   es außerhalb des HA-Systems. Vergewissere dich, dass der bisherige
   `custom_components/paradigma`-Stand ebenfalls wiederherstellbar ist.
3. Falls bereits ein Original-Update versucht wurde: zur funktionierenden
   Ausgangslage zurückkehren. Sind alte UND neue Entitäten registriert, hält die
   Brücke bei ID-Kollisionen vor jeder Änderung an. Nicht einfach Duplikate mit
   Historie löschen. Erst nach Backup gezielt prüfen, welche Zeile erhalten
   werden soll. Dieser PR führt absichtlich keine automatische Zusammenführung
   von Registry-Zeilen oder Statistikreihen aus.

## PR-Stand installieren und Migration prüfen

1. PR/Code prüfen. Der PR erzeugt kein HACS-Release. Lade zum Testen das Archiv des
   **konkreten PR-Commits** aus dem Fork herunter (Commitansicht → Browse files →
   Code → Download ZIP; alternativ
   `https://github.com/tomquist/paradigma-homeassistant/archive/<commit-sha>.zip`).
   Nutze nicht einen später unbemerkt veränderten Branchstand.
2. Home Assistant stoppen. Den bisherigen Ordner `custom_components/paradigma`
   sichern und durch den gleichnamigen Ordner aus dem Archiv ersetzen. Nicht
   verschiedene Versionen vermischen. HA wieder starten. Diese Testversion ist
   als `1.1.0-beta.1` gekennzeichnet; das ist **nicht** die Konfigurationsversion.
   Nicht gleichzeitig über HACS ein anderes Update einspielen.
3. **Den bestehenden Integrationseintrag behalten, nicht löschen/neu anlegen.**
   Beim Start migriert HA den Eintrag von 1 auf 2. Die normale Slave-ID bleibt
   unverändert (üblich: 1); EMS-Zugriffe verwenden weiterhin separat Unit 2.
4. Unter Einstellungen → Geräte & Dienste sowie in den HA-Protokollen prüfen:
   erfolgreicher Start und Meldung `Migrated Paradigma config entry to version 2`.
   Bei einem frisch angelegten Eintrag oder bereits Version 2 gibt es keine
   erneute Migration. Bei Konflikt-/Fehlermeldungen hier stoppen.
5. Bisherige Entity-IDs, individuelle Namen, deaktivierte Entitäten und wichtige
   Automationen/Dashboards mit dem notierten Ausgangszustand vergleichen. Bei
   ungewollten neuen `_2`-Entitäten nicht mit dem Wechsel fortfahren.

## Danach auf das Original wechseln

Erst nach erfolgreicher Prüfung und bewusster Berücksichtigung der Unterschiede:

1. Für das Original im HACS-Standardkatalog **exakt V2.6.2** auswählen. Falls noch
   der Fork als Custom Repository eingetragen ist, nur die HACS-Repository-
   Zuordnung wechseln; den HA-Integrationseintrag nicht entfernen. Wenn HACS den
   Versionswechsel so nicht anbietet, HA stoppen und denselben Integrationsordner
   durch den aus dem Original-Tag ersetzen. Keine parallelen Installationen
   desselben Domains anlegen.
2. HA neu starten und Entitäten/Automationen erneut prüfen. Der bestehende Eintrag
   ist bereits Version 2; das Original muss ihn nicht mehr migrieren. Seine
   Entitäten mit Gegenstück verwenden die vorhandenen Registry-Zeilen.
3. Vorherige Schreibautomationen erst nach Prüfung gezielt wieder verwenden.
   Die Brücke schreibt sie nicht eigenmächtig um.

## Bekannte Grenzen: IDs kompatibel heißt nicht identisches Verhalten

Die Brücke behält den bisherigen Fork-Betrieb bei und importiert **nicht** alle
Änderungen des Originals. Erst beim anschließenden Wechsel gelten unter anderem:

| Bereich | Fork/Brücke | Original V2.6.2 |
| --- | --- | --- |
| EMS-PV-Überschuss | 0–65533 W, Schritt 1 W | 0–20000 W, Schritt 100 W |
| EMS-Leistungsbegrenzung | 0–65535 W, standardmäßig deaktiviert | 0–20000 W, Schritt 100 W; Standard für neue Zeilen aktiviert |
| Tarifoption | `no_control` | `no_tariff` (high/low bleiben gleich) |
| EMS-Register 0/2/3 | nur schreiben, kein Polling | werden auch gelesen; mögliche Modbus-Fehler/unknown bei Write-only-Registern |
| EMS-Firmware | formatierte Versionszeichenfolge | kombinierter 32-Bit-Zahlenwert |
| EMS-Modell | hexadezimale Zeichenfolge | numerischer Wert |
| Register 44/45, Puffer-/Kessel-Sollwert | Number-Steuerungen | nur Sensor-Gegenstücke; keine Number-Steuerungen |

Die alte `no_control`-Option bleibt in der Brücke bewusst erhalten. Bestehende
Automationen funktionieren damit in der Zwischenversion weiter; vor dem Wechsel
ins Original explizite `select.select_option`-Werte und Zustandsbedingungen auf
`no_tariff` prüfen/anpassen. PV-/Leistungsbegrenzungs-Automationen müssen dort
Wertebereich und Schrittweite einhalten. Registry-Einstellungen wie die bestehende
Deaktivierung der Leistungsbegrenzung bleiben bei migrierten Zeilen erhalten.

Die Number-Entitäten für 44/45 bleiben in der Brücke mit alter ID bestehen, werden
im Original aber nicht mehr bereitgestellt und damit dort nicht verfügbar.
Referenzen auf diese Schreibsteuerungen müssen separat entfernt/umgebaut werden;
ein lesender Sensor ist kein gleichwertiger Ersatz. Die Brücke legitimiert keine
Schreibzugriffe auf laut Reglerdokumentation nur lesbare Register.

## Fehler und Rückweg

Kollisionen werden vor allen Updates geprüft. Bei einer API-Ausnahme versucht die
Brücke bereits geänderte IDs und die Konfigurationsversion zurückzusetzen. Die
HA-Speicher für Registry und Konfiguration werden jedoch unabhängig persistiert:
Das ist **keine absturzsichere Transaktion**. Bei Stromausfall/Fehlerprotokollen
vollständig prüfen und nötigenfalls das Backup verwenden.

Ein bloßes Zurückkopieren des alten Version-1-Forks nach erfolgreicher Migration
reicht nicht: dieser kann den gespeicherten Version-2-Eintrag ablehnen. Der
zuverlässige Rückweg ist das **vor der Migration erstellte Backup samt altem
Integrationscode**. Eine vollständige Wiederherstellung verwirft auch sonstige
Änderungen seit dem Backup und startet HA neu; diese Auswirkungen vorab abwägen.
Keine manuelle Änderung in `.storage` vornehmen.

## Tests und spätere Upstream-Beiträge

Offline ausführbar ohne Home Assistant:

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components tests
```

Tests verwenden fokussierte Doubles der öffentlichen HA-APIs und eine auf den
obigen Commit fixierte Zielfixture. Sie prüfen IDs/Metadaten, Konfiguration,
Scope, Kollisionen, Wiederholbarkeit und Fehler-Rückabwicklung. Sie ersetzen
**keinen Test in einer echten HA-Instanz und keinen Modbus-/Heizungstest**.

Für spätere PRs gegen das Original trennen:

1. Konfiguration-v1→v2-/Registry-Migration mit Upstream-Altständen als zusätzlichen
   Fixtures und Tests; im Original ist die Runtime bereits auf dem Ziel-ID-Schema.
2. EMS-Verhalten (Write-only-Register, Tarifkompatibilität, Leistungsgrenzen,
   Firmware-Dekodierung) separat anhand der Protokolldokumentation klären.

Die Fork-Runtime-Anpassungen dieser Brücke sind nicht 1:1 ins Original zu kopieren.
