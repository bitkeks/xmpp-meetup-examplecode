// Example code for XMPP meetup Dresden 2019-08-15
// Bot challenge - solution in Go
// Receives wikipedia request, looks up the page and responds with the teaser text
// Copyright 2019 bitkeks. Licenced as free software under the GPLv3
package main

import (
    "encoding/json"
    "flag"
    "io/ioutil"
    "log"
    "os"
    "os/signal"
    "strings"
    "time"
    "net/http"

    xmpp "github.com/mattn/go-xmpp"
)

type XMPPMucConfig struct {
    // XMPP MUC room
    Jid string
    Password string
}

type WikiPages struct {
    PageID int
    Ns int
    Title string
    Extract string
}

type Wikiquery struct {
    Batchcomplete bool
    Query struct {
        Pages []WikiPages
    }
}

var (
    joinedMucs []string
    verbose bool
    username string
    password string
)

func runXMPP() {
    var err error
    var client *xmpp.Client
    muc_jid := "dresden-meetup@conference.jugendhacker.de"
    xmpp_chan := make(chan string, 3)

    options := xmpp.Options{
        Host: "jugendhacker.de:65126",
        User: username,
        Password: password,
        Resource: "wikibot",
        NoTLS: true,
        StartTLS: true,
        Debug: false,
        Session: false,
    }

    client, err = options.NewClient()
    if err != nil {
        log.Fatal(err)
    }
    if !client.IsEncrypted() {
        log.Fatal("Connection not encrypted!")
    }
    defer client.Close()

    // Listener
    go func() {
        for {
            chat, err := client.Recv()
            if err != nil {
                log.Fatal("Error while receiving from connection", err)
            }

            switch v := chat.(type) {
            case xmpp.Chat:
                debug("Message: ", v.Remote, v.Text)
                if strings.HasPrefix(v.Remote, muc_jid) {
                    if strings.HasPrefix(v.Text, "!wikipedia") {
                        query := strings.TrimSpace(v.Text[10:])
                        debug("Received wikipedia request: ", query)

                        resp, err := http.Get("https://en.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exlimit=1&explaintext&exintro&formatversion=2&titles=" + query)
                        if err != nil {
                            log.Fatal("Error in HTTP request")
                        }
                        defer resp.Body.Close()
                        body, err := ioutil.ReadAll(resp.Body)

                        var content Wikiquery
                        json.Unmarshal(body, &content)

                        title := content.Query.Pages[0].Title
                        extract := content.Query.Pages[0].Extract
                        if len(extract) > 100 {
                            extract = extract[:99]
                        }

                        xmpp_chan <- title + ": " + extract

                    }
                }
            case xmpp.Presence:
                debug("Presence: ", v.From, v.Show)
            default:
                debug("Stanza: ");
            }
        }
    }()

    muc_nick := "wikigo"
    _, err = client.JoinMUC(muc_jid, muc_nick, xmpp.SecondsHistory, 0, nil)
    if err != nil {
        log.Fatal("Error joining MUC", muc_jid, err)
    } else {
        debug("Joined MUC", muc_jid)
        joinedMucs = append(joinedMucs, muc_jid)
    }

    for message := range xmpp_chan {
        client.Send(xmpp.Chat{
            Remote: muc_jid,
            Type: "groupchat",
            Text: message,
            Stamp: time.Now(),
        });
    }
}

func debug(message ...string) {
    if verbose {
        msg := []string{"DEBUG: "}
        msg = append(msg, message...)
        log.Println(msg)
    }
}

func main() {
    flag.BoolVar(&verbose, "verbose", false, "Enable verbose output")
    flag.StringVar(&username, "username", "", "Username to use on login")
    flag.StringVar(&password, "password", "", "Password to use on login")
    flag.Parse()

    go runXMPP()

    // Handle CTRL+C / interrupt = syscall.SIGINT
    c := make(chan os.Signal, 1)
    signal.Notify(c, os.Interrupt)
    for range c {
        // Received interrupt, exit
        log.Println("Received SIGINT, exiting")
        os.Exit(0)
    }
}
