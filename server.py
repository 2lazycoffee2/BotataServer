import http.server
from martypy import Marty
import urllib

robots = {}


class Handling(http.server.BaseHTTPRequestHandler):



    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
   
        if parsed.path == "/": 
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"1.2\n")

        elif parsed.path == "/score":
            params = urllib.parse.parse_qs(parsed.query)
            rid = params.get('rid', [''])[0]
            score = robots.get(rid, {}).get('score', 0)
            self._repondre(200, score)
            
            

    def do_POST(self):
        if self.parsed.path == "/hello" :
            print("hello")
        
def run(server_class=http.server.HTTPServer, handler_class=http.server.BaseHTTPRequestHandler):
    server_address = ('', 8080)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

#my_mart = Marty("wifi", "192.168.0.111")
#voir le /api

 
if __name__ == '__main__' :
    server_address = ('', 8080)
    httpd = http.server.HTTPServer(server_address, Handling)

    httpd.serve_forever()

