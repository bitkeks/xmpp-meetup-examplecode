# XMPP-Meetup Dresden "Bots mit XMPP" (2019-08-15)

In diesem Repo findet ihr einigen Beispielcode zum Thema "Bots in XMPP", basierend auf existierenden Bots in vier Sprachen: Go, Java, JavaScript, Python!

## Go

Der Beispielcode für Go ist ein einfacher Bot, der auf einem HTTP-Interface einen Parameter entgegennimmt und diesen an eine Liste von Empfängern und MUCs weiterleitet. Beispiel: `curl 'localhost:27001/?text=Textnachricht'` würde an die konfigurierten Empfänger die Nachricht *Textnachricht* senden.

Im Verzeichnis `hermes-go` (setzt mind. Go 1.11 für `go mod` voraus):

  1. `go mod tidy` (initialisiert go-xmpp)
  2. `go build -o bin/hermes hermes.go` (baut das binary in `bin/hermes`)
  3. Kopieren der `config.example.json` zu `config.json` und Daten ausfüllen. Hier kann der eigene, existierende Account genutzt werden (hermes nutzt dann `hermes` als Ressource)
  3. `./bin/hermes -v -http`

## Java


## JavaScript


## Python


