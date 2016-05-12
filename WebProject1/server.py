import asyncio
import logging
import http.cookies
import autobahn
import json
import base64
import redis
import os
import pickle

from io import BytesIO
from autobahn.util import newid, utcnow
from configparser import SafeConfigParser
from enum import Enum, unique
from PIL import Image, ImageOps
from autobahn.asyncio.websocket import (WebSocketServerProtocol,
                                        WebSocketServerFactory)

config = SafeConfigParser()
config.read("server.ini")
clients = set()
r = redis.StrictRedis(host=config.get("redis","host"),port=config.getint("redis","port"),db=0)
r.set("user_index",0)
logging.basicConfig(level=logging.INFO)

@unique
class MessageTypes(Enum):
    img = 1
    text = 2
    login = 3

class ChatProtocol(WebSocketServerProtocol):
    def onConnect(self, request):
        clients.add(self)
        protocol, headers = None, {}
        self._cbtid = None

        if "cookie" in request.headers:
            try:
                cookie = http.cookies.SimpleCookie()
                cookie.load(str(request.headers["cookie"]))
            except http.cookies.CookieError:
                pass
            else:
                if "cbtid" in cookie:
                    cbtid = cookie["cbtid"].value
                    if cbtid in self.factory._cookies:
                        self._cbtid = cbtid
                        print("Cookie already set: %s" % self._cbtid)

        if self._cbtid is None:

            self._cbtid = newid()
            maxAge = self.factory.session_max_age
            user_index = r.incr("user_index")
            r.hmset(self._cbtid,{"login":"user%s" % user_index})
            cbtData = {"created": utcnow(),
                       "maxAge": maxAge,
                       "connections": set() }

            self.factory._cookies[self._cbtid] = cbtData
            headers["Set-Cookie"] = "cbtid=%s;max-age=%d" % (self._cbtid, maxAge)
            print("Setting new cookie: %s" % self._cbtid)
        self.factory._cookies[self._cbtid]["connections"].add(self)
        return (protocol, headers)

    def onOpen(self):
        
        self.sendMessage(json.dumps({
            "msg":r.hmget(self._cbtid,"login")[0].decode("utf8"),
            "type":MessageTypes.login.value}).encode("utf8"))
        messages = r.lrange("messages",0,self.factory.restored_messages)[::-1]
        for data in messages:
            cbtid,type,msg,full,thumb = pickle.loads(data)
            if type == MessageTypes.img.value:
                file_name,file_ext = os.path.splitext(thumb)
                with open(thumb,"rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read())
                    msg = "data:image/%s;base64,%s" % (file_ext,encoded_string.decode("utf8"))
            self.sendMessage(json.dumps({"msg":msg,
                                         "isFromRemote":self._cbtid != cbtid,
                                         "type":type,
                                         "login":r.hmget(cbtid,"login")[0].decode("utf8")}).encode("utf8"))

    def onMessage(self, payload, is_binary):
        inData = json.loads(payload.decode("utf8"))
        msg = inData["msg"]
        type = inData["type"]
        full = None
        thumb = None
        msg_dict = {
            "msg":msg,
            "isFromRemote":False,
            "type":type,
            "login":r.hmget(self._cbtid,"login")[0].decode("utf8")}
        if type == MessageTypes.img.value:
            msg,full,thumb = self.save_image(msg)
            msg_dict["msg"] = msg
            self.sendMessage(json.dumps(msg_dict).encode("utf8"))
        r.lpush("messages",pickle.dumps((self._cbtid,type,msg,full,thumb)))
        msg_dict["isFromRemote"] = True
        payload = json.dumps(msg_dict).encode("utf8")
        for c in clients.copy():
            if c is not self:
                try:
                    c.sendMessage(payload)
                except Exception as e:
                    print(e)
                    clients.remove(c)

    def onClose(self, was_clean, code, reason):
        clients.remove(self)
        self.factory._cookies[self._cbtid]["connections"].remove(self)
        if not self.factory._cookies[self._cbtid]["connections"]:
            print("All connections for {} gone".format(self._cbtid))

    def save_image(self, data_url):
        list = data_url.split(";")
        img = list[1].split(",")[1]
        file_ext = list[0].split("/")[1]
        file_dir = self.factory.image_dir+"\\"
        file_name = newid()
        full_path = file_dir + file_name + "." + file_ext
        with open(full_path,"wb") as image_file:
           image_file.write(base64.b64decode(img))
        thumb = ImageOps.fit(Image.open(full_path),(128,128),Image.ANTIALIAS)
        thumb_path = file_dir + file_name + ".thumb" + "." + file_ext
        thumb.save(thumb_path)
        buffered = BytesIO()
        thumb.save(buffered,file_ext)
        encoded_string = base64.b64encode(buffered.getvalue())
        msg = "data:image/%s;base64,%s" % (file_ext,encoded_string.decode("utf-8"))
        return (msg,full_path,thumb_path)


class ChatServerFactory(WebSocketServerFactory):
    protocol = ChatProtocol
    def __init__(self, url, image_dir, session_age, restored_messages):
        WebSocketServerFactory.__init__(self, url)
        self._cookies = {}
        self.image_dir = image_dir
        self.session_max_age = session_age
        self.restored_messages = restored_messages


if __name__ == "__main__":

    factory = ChatServerFactory(config.get("server","url"), 
                                config.get("server","image_dir"),
                                config.getint("server","session_age"),
                                config.getint("server","restored_messages"))
    factory.protocol = ChatProtocol

    loop = asyncio.get_event_loop()
    asyncio.Task(loop.create_server(factory, port=config.getint("server","port")))
    loop.run_forever()