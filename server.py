import http.server
import urllib.parse
import random
import string
import json

robots = {}
battle_rules = {}

def generer_rid():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def charger_battle(chemin):
    """Lit le fichier .battle et remplit battle_rules."""
    global battle_rules
    battle_rules = {}
    couleur_courante = None

    with open(chemin, 'r') as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne:
                continue
            if ligne.startswith("MVS"):
                battle_rules["mvs"] = int(ligne.split()[1])
            elif ligne.startswith("[") and ligne.endswith("]"):
                couleur_courante = ligne[1:-1]
                battle_rules[couleur_courante] = []
            elif "=" in ligne and couleur_courante:
                gauche, droite = ligne.split("=")
                points = int(droite)
                if "+" in gauche:
                    op, elements = "AND", gauche.split("+")
                elif "," in gauche:
                    op, elements = "OR", gauche.split(",")
                else:
                    op, elements = "SINGLE", [gauche]
                battle_rules[couleur_courante].append({
                    "elements": elements,
                    "op": op,
                    "points": points
                })
    print(f"[BATTLE] Chargé : {battle_rules}")


def calculer_points(col, arm, exp):
    if not battle_rules:
        return 1
    if col not in battle_rules:
        return 0

    elements_presents = set(arm.split("+")) | {exp}
    total = 0

    for regle in battle_rules[col]:
        els = regle["elements"]
        op  = regle["op"]
        pts = regle["points"]
        if op == "AND":
            if all(e in elements_presents for e in els):
                total += pts
        elif op == "OR":
            if any(e in elements_presents for e in els):
                total += pts
        elif op == "SINGLE":
            if els[0] in elements_presents:
                total += pts
    return total


class Handling(http.server.BaseHTTPRequestHandler):

    def _lire_body(self):
        """Lit le corps JSON de la requête."""
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode('utf-8')
        try:
            return json.loads(raw)        # ← JSON maintenant
        except json.JSONDecodeError:
            return {}

    def _repondre(self, code, data):
        """Envoie une réponse JSON."""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')   # ← JSON
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))     # ← JSON

    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} {format % args}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/":
            self._repondre(200, {"version": "1.2"})            # ← clé "version"

        elif parsed.path == "/score":
            params = urllib.parse.parse_qs(parsed.query)
            rid = params.get('rid', [''])[0]
            if rid not in robots:
                self._repondre(404, {"error": f"Robot inconnu : {rid}"})
                return
            self._repondre(200, {"points": robots[rid]['score']})  # ← clé "points"

        else:
            self._repondre(404, {"error": "Route inconnue"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        body = self._lire_body()

        if parsed.path == "/hello":
            rid = generer_rid()
            while rid in robots:
                rid = generer_rid()
            robots[rid] = {'score': 0, 'steps': 0}
            print(f"[HELLO] Nouveau robot : {rid}")
            self._repondre(200, {"rid": rid})                  # ← clé "rid"

        elif parsed.path == "/start":
            rid = body.get('rid', '')
            if rid not in robots:
                self._repondre(404, {"error": f"Robot inconnu : {rid}"})
                return
            nb_pas = battle_rules.get("mvs", 10)
            print(f"[START] Robot {rid} démarre ({nb_pas} pas)")
            self._repondre(200, {"steps": nb_pas})             # ← clé "steps"

        elif parsed.path == "/step":
            rid = body.get('rid', '')
            col = body.get('col', '')
            arm = body.get('arm', '')
            exp = body.get('exp', '')
            if rid not in robots:
                self._repondre(404, {"error": f"Robot inconnu : {rid}"})
                return
            points = calculer_points(col, arm, exp)            # ← sans rid
            robots[rid]['score'] += points
            robots[rid]['steps'] += 1
            print(f"[STEP] Robot {rid} | col={col} arm={arm} exp={exp} -> +{points} pt(s)")
            self._repondre(200, {"points": points})            # ← clé "points"

        elif parsed.path == "/bye":
            rid = body.get('rid', '')
            if rid not in robots:
                self._repondre(404, {"error": f"Robot inconnu : {rid}"})
                return
            print(f"[BYE] Robot {rid} (score final : {robots[rid]['score']})")
            del robots[rid]
            self.send_response(200)
            self.end_headers()

        else:
            self._repondre(404, {"error": "Route inconnue"})


if __name__ == '__main__':
    charger_battle("regles.battle")   # ← charge les règles au démarrage

    server_address = ('', 8080)
    httpd = http.server.HTTPServer(server_address, Handling)
    print("[SERVER] Démarré sur le port 8080")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Arrêt.")
        httpd.server_close()