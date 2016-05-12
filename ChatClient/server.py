from http.server import HTTPServer, CGIHTTPRequestHandler
from configparser import SafeConfigParser

if __name__ == '__main__':
    config = SafeConfigParser()
    config.read("server.ini")
    server_address = (config.get("server","url"),config.getint("server","port"))
    httpd = HTTPServer(server_address,CGIHTTPRequestHandler)
    httpd.serve_forever()