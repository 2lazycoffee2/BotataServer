import http.server
from martypy import Marty

def run(server_class=http.server.HTTPServer, handler_class=http.server.BaseHTTPRequestHandler):
    server_address = ('', 8080)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

#my_mart = Marty("wifi", "192.168.0.111")

run()