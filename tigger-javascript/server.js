const fetch = require('node-fetch');
const XMPPClient = require('./xmpp_client');

process.on('SIGTERM', function() {
    process.exit(0);
});

if (process.argv.length != 5) {
    console.error("Parameters: <my-jid> <my-password> <full-muc-jid>");
    process.exit(1);
}
const jid = process.argv[2],
      pass = process.argv[3],
      muc_jid = process.argv[4];

const cl = new XMPPClient(jid, pass);
cl.joinRoom(muc_jid);

function sendElbePegel(muc) {
	fetch("https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/DRESDEN/W/measurements.json")
		.then(res => res.json())
		.then(json => {
			const pegel = json[json.length-1].value;
			cl.sendRoomMessage(muc, `Pegel: ${pegel} cm`)
		}).catch(() => {
			cl.sendRoomMessage(muc, `Der Pegelstand konnte leider nicht abgerufen werden, bitte versuch es später noch einmal!`)
		});
}

cl.on('muc:message', (muc, nick, text) => {
    if (/^hello/i.test(text) || /^hi$/i.test(text) || /^hallo/i.test(text)) {
        cl.sendRoomMessage(muc, `${nick}: Hi!`);
    } else if (/^[\+\?\!\/\\]elbe$/i.test(text)) {
		sendElbePegel(muc);
    }
});
