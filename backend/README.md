# Zenith Watch — Backend

## Estrutura

```
backend/
├── astronomia.py     # Cálculos astronômicos (ephem)
├── main.py           # Cloud Functions + API
├── requirements.txt  # Dependências
└── README.md
```

## Teste local (sem Firebase)

```bash
# 1. Instalar dependências
pip install ephem

# 2. Rodar o módulo astronômico direto
python astronomia.py
```

Isso mostra no terminal os objetos visíveis, zênite e alertas agora.

## Setup Firebase

### 1. Criar projeto no Firebase
- Acessa: https://console.firebase.google.com
- Cria projeto: `zenith-watch`
- Ativa Firestore, Cloud Functions e Cloud Messaging

### 2. Instalar Firebase CLI
```bash
npm install -g firebase-tools
firebase login
firebase init functions
```

### 3. Deploy das funções
```bash
cd backend
pip install -r requirements.txt
firebase deploy --only functions
```

### 4. Configurar Cloud Scheduler
No Google Cloud Console:
- Novo job: a cada 5 minutos
- Target: URL da função `verificar_e_alertar`
- Frequência: `*/5 * * * *`

## Coleções Firestore

### `usuarios/{user_id}`
```json
{
  "token_fcm": "token_do_celular",
  "config": {
    "latitude": -3.7172,
    "longitude": -38.5433,
    "altitude_minima": 45,
    "altitude_alerta": 75,
    "silencio_inicio": "00:00",
    "silencio_fim": "06:00"
  }
}
```

### `alertas_enviados/{user_id}_{objeto_id}`
```json
{
  "timestamp": "2026-06-23T22:15:00",
  "user_id": "abc123",
  "objeto_id": "saturno"
}
```

### `config/catalogo`
O catálogo JSON completo (opcional — fallback pro arquivo local).

## Endpoints da API

| Endpoint             | Descrição                        |
|----------------------|----------------------------------|
| `GET /api_hoje`      | Todos os objetos visíveis agora  |
| `GET /api_zenite`    | Objetos próximos ao zênite       |
| `GET /api_melhor_agora` | Melhor alvo neste momento     |
| `GET /api_objeto?id=saturno` | Dados de um objeto      |
| `POST /verificar_e_alertar` | Verifica e envia alertas |
