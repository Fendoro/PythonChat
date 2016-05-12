var messageTypes;
(function (messageTypes) {
    messageTypes[messageTypes["img"] = 1] = "img";
    messageTypes[messageTypes["text"] = 2] = "text";
    messageTypes[messageTypes["login"] = 3] = "login";
})(messageTypes || (messageTypes = {}));
var connectState;
(function (connectState) {
    connectState[connectState["opening"] = 0] = "opening";
    connectState[connectState["open"] = 1] = "open";
    connectState[connectState["closing"] = 2] = "closing";
    connectState[connectState["closed"] = 3] = "closed";
})(connectState || (connectState = {}));

function ChatClient(url) {
    this.socket = null;
    this._statusNode = null;
    this._messagesNode = null;
    this.login = "you";
    this.status = connectState[connectState.closed];
    this.url = url;
    this.connected = false;
}

ChatClient.prototype.setLogin = function (login) {
    this.login = login;
    this.updateInfo();
}

ChatClient.prototype.getMessagesNode = function () {
    if (this._messagesNode == null) {
        this._messagesNode = document.getElementById("inbox");
    }
    return this._messagesNode;
}

ChatClient.prototype.showMessage = function (msg, type, isFromRemote, login) {
    var containerNode = document.createElement("div");
    containerNode.classList.add("msg");
    containerNode.classList.add(isFromRemote ? "remote" : "local");
    var loginNode = document.createElement("div");
    loginNode.classList.add("login");
    loginNode.textContent = login;
    var msgNode;
    switch (type) {
        case messageTypes.img:
            msgNode = document.createElement("img");
            msgNode.src = msg;
            break;
        default:
            msgNode = document.createElement("div");
            msgNode.classList.add("data");
            msgNode.textContent = msg;
            break;
    }
    containerNode.appendChild(loginNode);
    containerNode.appendChild(msgNode);
    this.getMessagesNode().appendChild(containerNode);
}

ChatClient.prototype.updateInfo = function () {
    if (this._statusNode == null) {
        this._statusNode = document.getElementById("status");
    }
    this._statusNode.innerHTML = this.login + ":" + this.status;
}

ChatClient.prototype.setStatus = function (status) {
    this.status = status;
    this.updateInfo();
}

ChatClient.prototype.start = function () {
    var chatClientRef = this;
    chatClientRef.setStatus(connectState[connectState.opening]);
    chatClientRef.connected = false;

    function poll() {
        if (chatClientRef.connected) {
            return;
        }
        var ws = new WebSocket(chatClientRef.url);
        ws.onopen = ws.onclose = ws.onerror = function (event) {
            var code = ws.readyState;
            chatClientRef.setStatus(connectState[code]);
            chatClientRef.connected = (code === connectState.opening || code === connectState.open);
            var node = chatClientRef.getMessagesNode();
            while (node.firstChild) {
                node.removeChild(node.firstChild);
            }
        };

        ws.onmessage = function (event) {
            var data = JSON.parse(event.data);
            switch (data.type) {
                case messageTypes.img:
                case messageTypes.text:
                    chatClientRef.showMessage(data.msg, data.type, data.isFromRemote, data.login);
                    break;
                case messageTypes.login:
                    chatClientRef.setLogin(data.msg);
                    break;
            }

        };

        chatClientRef.connected = true;
        chatClientRef.socket = ws;
    }

    setInterval(poll, 100);
}

function newImg(file) {

    setTimeout(function () {
        var reader = new FileReader();
        reader.onload = (function (upd) {
            return function (e) {
                var src = e.target.result;
                upd.socket.send(JSON.stringify({ msg: src, type: messageTypes.img }));
            };
        })(chatClientInstance);
        reader.readAsDataURL(file);

    }, 200);
}

function newMessage(form) {
    var msgInput = form.elements.msg;
    var msg = msgInput.value;
    chatClientInstance.showMessage(msg, messageTypes.text, false, chatClientInstance.login);
    msgInput.value = "";
    msgInput.select();

    setTimeout(function () {
        chatClientInstance.socket.send(JSON.stringify({ msg: msg, type: messageTypes.text }));
    }, 200);
}

function domReady() {
    var messageForm = document.getElementById("messageform");
    messageForm.addEventListener("submit", function (e) {
        e.preventDefault();
        newMessage(this);
        return false;
    });
    messageForm.addEventListener("keypress", function (e) {
        if (e.keyCode === 13) {
            e.preventDefault();
            newMessage(this);
            return false;
        }
    });
    messageForm.addEventListener("dragover", function (e) {
        this.classList.add("hover");
        return false;
    });
    messageForm.addEventListener("dragleave", function (e) {
        this.classList.remove("hover");
        return false;
    });
    messageForm.addEventListener("drop", function (e) {
        e.preventDefault();
        this.classList.remove("hover");
        var file = e.dataTransfer.files[0];
        newImg(file);
        return false;
    });
    var messageInput = document.getElementById("msg");
    messageInput.select();
    chatClientInstance.start();
}

var chatClientInstance = new ChatClient("ws://localhost:8765/");
document.addEventListener("DOMContentLoaded", domReady);