// Example code for XMPP meetup Dresden 2019-08-15
// This bot receives strings via HTTP calls and relays them towards
// a configured list of receivers. See config.example.json for details.

// Copyright 2017-2019 bitkeks. Licenced as free software under the GPLv3
package main

import (
    "encoding/json"
    "flag"
    "io/ioutil"
    "log"
    "net/http"
    "os"
    "os/signal"
    "strconv"
    "time"

    xmpp "github.com/mattn/go-xmpp"
)

type HTTPConfig struct {
    Port int
}

type XMPPMucConfig struct {
    // XMPP MUC room
    Jid string
    Password string
}

type XMPPConfig struct {
    // XMPP user as full JID
    User string
    // XMPP users password
    Password string
    // XMPP resource name
    Resource string
    // Nick for MUC rooms
    Nick string
    // XMPP receiver as full JID
    Receivers []string
    // XMPP MUCs to join
    Mucs []XMPPMucConfig
}

type Config struct {
    // HTTP API related config
    HTTP HTTPConfig
    // XMPP related config
    XMPP XMPPConfig
}

var (
    config Config
    joinedMucs []string
    verbose bool
    enableHTTP bool
)

func runXMPP(messageInput <-chan string) {
    var err error
    var client *xmpp.Client

    options := xmpp.Options{
        User: config.XMPP.User,
        Password: config.XMPP.Password,
        Resource: config.XMPP.Resource,
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
            case xmpp.Presence:
                debug("Presence: ", v.From, v.Show)
            default:
                debug("Stanza: ");
            }
        }
    }()

    if config.XMPP.Mucs != nil {
        debug("Joining MUCs..")
        // Handle MUC nickname
        var muc_nick string
        if muc_nick = config.XMPP.Nick; muc_nick == "" {
            muc_nick, err = os.Hostname()
        }
        debug("Using MUC nickname: ", muc_nick)

        // Join each MUC given in config
        for _, muc := range config.XMPP.Mucs {
            if muc.Password != "" {
                // Handle password protected MUCs
                _, err := client.JoinProtectedMUC(muc.Jid, muc_nick, muc.Password, xmpp.NoHistory, 0, nil)
                if err != nil {
                    log.Fatal("Error joining protected MUC", muc.Jid, err)
                } else {
                    debug("Joined protected MUC", muc.Jid)
                    joinedMucs = append(joinedMucs, muc.Jid)
                }
            } else {
                // Handle other MUCs
                _, err := client.JoinMUC(muc.Jid, muc_nick, xmpp.NoHistory, 0, nil)
                if err != nil {
                    log.Fatal("Error joining MUC", muc.Jid, err)
                } else {
                    debug("Joined MUC", muc.Jid)
                    joinedMucs = append(joinedMucs, muc.Jid)
                }
            }
        }
    }

    for message := range messageInput {
        debug("Received message on channel to be sent to receivers and MUCs")
        now := time.Now()

        // Send to single receivers
        for _, receiver := range config.XMPP.Receivers {
            client.Send(xmpp.Chat{
                Remote: receiver,
                Type: "chat",
                Text: message,
                Stamp: now,
            })
        }

        // Send to MUCs
        for _, muc := range joinedMucs {
            client.Send(xmpp.Chat{
                Remote: muc,
                Type: "groupchat",
                Text: message,
                Stamp: now,
            });
        }
    }
}

func runHTTP(messageChan chan<- string) {
    http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
        text := r.URL.Query().Get("text")
        debug("Received message at HTTP interface")
        messageChan <- text
    })

    port := strconv.Itoa(config.HTTP.Port)
    debug("Starting HTTP API at port ", port)

    log.Fatal(http.ListenAndServe(":" + port, nil))
}

func debug(message ...string) {
    if verbose {
        msg := []string{"DEBUG: "}
        msg = append(msg, message...)
        log.Println(msg)
    }
}

func main() {
    flag.BoolVar(&verbose, "v", false, "Enable verbose output")
    flag.BoolVar(&enableHTTP, "http", false, "Enable HTTP interface")
    flag.Parse()

    if !enableHTTP {
        log.Fatal("No input mode selected! Use -http.")
    }

    debug("Reading config file")
    config_file, err := ioutil.ReadFile("config.json")
    if err != nil {
        log.Fatal("Could not read config!", err)
    }
    json.Unmarshal(config_file, &config)

    // Create channel for incoming messages
    xmpp_chan := make(chan string, 3)
    debug("Created channel for incoming messages, starting runXMPP")
    go runXMPP(xmpp_chan)

    // HTTP API
    if enableHTTP {
        go runHTTP(xmpp_chan)
    }

    // Handle CTRL+C / interrupt = syscall.SIGINT
    c := make(chan os.Signal, 1)
    signal.Notify(c, os.Interrupt)
    for range c {
        // Received interrupt, exit
        log.Println("Received SIGINT, exiting")
        os.Exit(0)
    }
}
