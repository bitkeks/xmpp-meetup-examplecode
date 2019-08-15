# XMPP-Meetup Dresden "Bots mit XMPP" (2019-08-15)

In diesem Repo findet ihr einigen Beispielcode zum Thema "Bots in XMPP", basierend auf existierenden Bots in vier Sprachen: Go, Java, JavaScript, Python!

## Go

Der Beispielcode für Go ist ein einfacher Bot, der auf einem HTTP-Interface einen Parameter entgegennimmt und diesen an eine Liste von Empfängern und MUCs weiterleitet. Beispiel: `curl 'localhost:27001/?text=Textnachricht'` würde an die konfigurierten Empfänger die Nachricht *Textnachricht* senden.

Im Verzeichnis `hermes-go` (setzt mind. Go 1.11 für `go mod` voraus):

  1. `go mod tidy` (initialisiert go-xmpp)
  2. `go build -o bin/hermes hermes.go` (baut das binary in `bin/hermes`)
  3. Kopieren der `config.example.json` zu `config.json` und entsprechend anpassen. Hier kann der eigene, existierende Account genutzt werden (hermes nutzt dann `hermes` als Ressource)
  3. `./bin/hermes -v -http`

## Java


## JavaScript


## Python

Im Verzeichnis `tooter-python` findet ihr einen Python-Bot, der zwischen einem XMPP-MUC und einer Mastodon-API kommuniziert. Hierzu wird `asyncio` verwendet, zusammen mit den `aioxmpp` und `aiohttp` libraries, um asynchron gleichzeitig sowohl Events von der Mastodon-API zu parsen, als auch Nachrichten aus dem MUC an den Bot zu verarbeiten. In dieser vereinfachten Version funktioniert der `stats`-Befehl im MUC, d. h. die Nachricht `tooter: stats` im MUC wird vom Bot verarbeitet und ein Reply gesendet.

  * [Mastodon-API docs](https://docs.joinmastodon.org/api)
  * [aioxmpp docs](https://docs.zombofant.net/aioxmpp/0.10/)

Zum Setup im Unterordner:

  1. `pipenv sync`
  2. `pipenv shell`
  3. Kopieren der `config.example.json` zu `config.json` und entsprechend anpassen.
  4. `python3 bot.py --debug`

Wenn ihr den Bot selbst betreiben wollt, müsst ihr in Mastodon einen Token erzeugen (in den Settings), der eure Timeline lesen kann.
