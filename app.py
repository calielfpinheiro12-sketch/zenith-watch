from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'functions'))

from astronomia import analisar_catalogo, objetos_zenite, melhor_alvo_agora, verificar_alertas

def carregar_catalogo():
    caminho = os.path.join(os.path.dirname(__file__), 'catalogo', 'catalogo.json')
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        catalogo = carregar_catalogo()
        
        if self.path == '/hoje':
            dados = analisar_catalogo(catalogo)
        elif self.path == '/zenite':
            dados = objetos_zenite(catalogo)
        elif self.path == '/melhor':
            dados = melhor_alvo_agora(catalogo)
        elif self.path == '/alertas':
            dados = verificar_alertas(catalogo)
        else:
            dados = {"status": "Zenith Watch online 🔭"}

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(dados, ensure_ascii=False, default=str).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🔭 Zenith Watch rodando na porta {port}", flush=True)
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"✅ Servidor iniciado!", flush=True)
    server.serve_forever()
