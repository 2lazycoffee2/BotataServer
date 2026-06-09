import http.server
from martypy import Marty
import urllib
import random
import string 
robots = {}

 
def generer_rid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

class Handling(http.server.BaseHTTPRequestHandler):

    def _lire_body(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length).decode('utf-8')
        parsed = urllib.parse.parse_qs(raw)
        return {k: v[0] for k, v in parsed.items()}
    
    def _repondre(self, code, corps) :
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(str(corps).encode('utf-8'))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
   
        if parsed.path == "/": 
            self._repondre(200, 1.2)

        elif parsed.path == "/score":
            params = urllib.parse.parse_qs(parsed.query)
            rid = params.get('rid', [''])[0]
            if rid not in robots:
                self._repondre(404, f"Robot inconnu : {rid}" )           
                return
            
            score = robots.get(rid, {}).get('score', 0)
            self._repondre(200, f"Score : {score}")
            

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        body = self._lire_body()
        
        if parsed.path == "/hello" :
            rid = generer_rid()
            while rid in robots :
                rid = generer_rid()
            robots[rid] = {'score': 0, 'steps': 0}
            print(f"[HELLO] Nouveau robot enregistré : {rid}")
            self._repondre(200, rid)
        
        elif parsed.path == "/start" :
            rid = body.get('rid', '')
            if rid not in robots:
                self._repondre(404, f"Robot inconnu : {rid}")
                return
            nb_pas = 10  
            print(f"[START] Robot {rid} démarre")
            self._repondre(200, nb_pas)

        
def run(server_class=http.server.HTTPServer, handler_class=http.server.BaseHTTPRequestHandler):
    server_address = ('', 8080)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

 
if __name__ == '__main__' :
    server_address = ('', 8080)
    httpd = http.server.HTTPServer(server_address, Handling)

    httpd.serve_forever()

