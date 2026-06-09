import http.server
from martypy import Marty
import urllib
import random
import string 
robots = {}
battle_rules = {}
 
def generer_rid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def calculer_points(rid, col, arm, exp):
    # Pas de .battle chargé → 1 point par défaut
    if not battle_rules:
        return 1

    # Couleur absente du .battle → 0 point
    if col not in battle_rules:
        return 0

    # On met tout ce que le robot a fait dans un set
    # "ALU+ARB" → {"ALU", "ARB"}   puis on ajoute exp → {"ALU", "ARB", "XSD"}
    elements_presents = set(arm.split("+")) | {exp}

    total = 0
    # On parcourt TOUTES les règles de la section [col]
    # peu importe combien il y en a, peu importe ce qu'elles contiennent
    for regle in battle_rules[col]:

        els = regle["elements"]   # ex: ["ALB", "ARB"] ou ["ALU", "ARU"] ou ["XSD"]
        op  = regle["op"]         # "AND", "OR", ou "SINGLE"
        pts = regle["points"]     # ex: 1, -1, 2...

        if op == "AND":
            # ALB+ARB=1 → les DEUX doivent être présents
            if all(e in elements_presents for e in els):
                total += pts

        elif op == "OR":
            # ALU,ARU=-1 → AU MOINS UN suffit (points comptés une seule fois)
            if any(e in elements_presents for e in els):
                total += pts

        elif op == "SINGLE":
            # XSD=1 → l'élément doit être présent
            if els[0] in elements_presents:
                total += pts

    return total

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

        elif parsed.path == "/step": 
            rid = body.get('rid', '')
            col = body.get('col', '')
            arm = body.get('arm', '')
            exp = body.get('exp', '')
 
            if rid not in robots:
                self._repondre(404, f"Robot inconnu : {rid}")
                return
 
            points = calculer_points(rid, col, arm, exp)
            robots[rid]['score'] += points
            robots[rid]['steps'] += 1
 
            print(f"[STEP] Robot {rid} | col={col} arm={arm} exp={exp} "
                  f"-> +{points} pt(s) (total={robots[rid]['score']})")
            self._repondre(200, points)   


        
def run(server_class=http.server.HTTPServer, handler_class=http.server.BaseHTTPRequestHandler):
    server_address = ('', 8080)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

 
if __name__ == '__main__' :
    server_address = ('', 8080)
    httpd = http.server.HTTPServer(server_address, Handling)

    httpd.serve_forever()

