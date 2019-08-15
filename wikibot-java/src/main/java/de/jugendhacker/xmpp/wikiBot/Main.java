package de.jugendhacker.xmpp.wikiBot;

import org.json.JSONArray;
import org.json.JSONObject;
import rocks.xmpp.addr.Jid;
import rocks.xmpp.core.XmppException;
import rocks.xmpp.core.session.XmppClient;
import rocks.xmpp.core.stanza.model.Message;
import rocks.xmpp.extensions.muc.ChatRoom;
import rocks.xmpp.extensions.muc.ChatService;
import rocks.xmpp.extensions.muc.MultiUserChatManager;
import rocks.xmpp.extensions.muc.model.DiscussionHistory;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.*;

public class Main {
    public static void main(String[] args){
        XmppClient xmppClient = XmppClient.create("jugendhacker.de");
        try {
            xmppClient.connect();
            xmppClient.login("bot2", "123456", "wikibot");
            MultiUserChatManager multiUserChatManager = xmppClient.getManager(MultiUserChatManager.class);
            ChatService chatService = multiUserChatManager.createChatService(Jid.of("conference.jugendhacker.de"));
            ChatRoom chatRoom = chatService.createRoom("bots");
            chatRoom.addInboundMessageListener(e -> {
                Message message = e.getMessage();
                System.out.println(message.getBody());
                if ((message.getBody() != null) && message.getBody().toLowerCase().matches("^\\?wiki .*")) {
                    String searchString = message.getBody().substring(6);
                    try {
                        System.out.println("https://de.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exlimit=1&explaintext&exintro&formatversion=2&redirects&exsentences=5&titles=" + URLEncoder.encode(searchString));
                        URL url = new URL("https://de.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exlimit=1&explaintext&exintro&formatversion=2&redirects&exsentences=5&titles=" + URLEncoder.encode(searchString));
                        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
                        connection.setRequestMethod("GET");
                        connection.connect();
                        BufferedReader in = new BufferedReader(new InputStreamReader(connection.getInputStream()));
                        String line;
                        StringBuffer body = new StringBuffer();
                        while ((line = in.readLine()) != null) {
                            body.append(line);
                        }
                        in.close();
                        JSONObject jsonObject = new JSONObject(body.toString());
                        JSONArray pages = jsonObject.getJSONObject("query").getJSONArray("pages");
                        JSONObject page = pages.getJSONObject(0);
                        if (!page.has("missing") || !(page.getBoolean("missing"))) {
                            chatRoom.sendMessage(page.getString("extract"));
                        } else {
                            chatRoom.sendMessage("Diese Seite existiert nicht");
                        }
                    } catch (MalformedURLException ex) {
                        ex.printStackTrace();
                    } catch (IOException ex) {
                        ex.printStackTrace();
                    }

                }
            });
            chatRoom.enter("wikibot2", DiscussionHistory.none());

            while (true){Thread.sleep(100);}
        } catch (XmppException e) {
            e.printStackTrace();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }
}
