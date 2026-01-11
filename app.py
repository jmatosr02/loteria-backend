from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import requests
import os

app = Flask(__name__)

AZURE_BASE = "https://wordpresswebapi.azurewebsites.net/api/ElectronicDrawing/ElectronicDrawingDateSearch"
GAME_ID_LOTO = 8  # confirmado en tu request

def _date_range_last_days(days: int):
    end = datetime.now().replace(hour=23, minute=59, second=0, microsecond=0)
    start = end - timedelta(days=days)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d %H:%M").replace(" ", "%20")  # encode espacio
    return start_str, end_str

def fetch_historico(days: int = 90):
    start_str, end_str = _date_range_last_days(days)
    url = f"{AZURE_BASE}/{GAME_ID_LOTO}/{start_str}/{end_str}"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return {
        "fuente": "Loterías PR (Azure API)",
        "juego": "Loto",
        "gameId": GAME_ID_LOTO,
        "desde": start_str,
        "hasta": end_str.replace("%20", " "),
        "data": r.json()
    }

@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "service": "loteria-backend",
        "endpoints": ["/health", "/api/loto/historico?dias=90", "/api/loto/sugerencias"]
    })

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.get("/api/loto/historico")
def historico():
    dias = int(request.args.get("dias", 90))
    try:
        payload = fetch_historico(dias)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def pick_2_sugerencias_from_data(raw_json):
    """
    Placeholder simple:
    - Extrae los sorteos
    - Hace frecuencia de números
    - Sugiere 2 combinaciones con top frecuentes (sin repetir)
    Ajustaremos esto con tu lógica después.
    """
    # Esto depende del formato exacto del JSON.
    # Por seguridad, lo manejamos flexible:
    draws = []
    if isinstance(raw_json, list):
        draws = raw_json
    elif isinstance(raw_json, dict):
        # común: {"data": [...] } o {"electronicDrawings": [...]}
        for k in ["data", "electronicDrawings", "results", "drawings"]:
            if k in raw_json and isinstance(raw_json[k], list):
                draws = raw_json[k]
                break

    # Intentar sacar números y multiplicador de cada sorteo
    nums = []
    multipliers = []
    for d in draws:
        # posibles keys para números
        for key in ["numbers", "numeros", "winningNumbers", "WinningNumbers"]:
            if key in d:
                val = d[key]
                if isinstance(val, str):
                    # "01-15-16-30-34"
                    parts = [p for p in val.replace(" ", "").split("-") if p.isdigit()]
                    if parts:
                        nums.append([int(p) for p in parts])
                elif isinstance(val, list):
                    nums.append([int(x) for x in val if str(x).isdigit()])
                break

        # posibles keys para multiplicador
        for mkey in ["multiplier", "multiplicador", "Multiplier"]:
            if mkey in d:
                try:
                    multipliers.append(int(str(d[mkey]).replace("x", "").strip()))
                except:
                    pass
                break

    # si no logró extraer, devuelve algo seguro
    if not nums:
        return {
            "jugadas": [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]],
            "multiplicador": 1
        }

    # frecuencia simple
    freq = {}
    for arr in nums:
        for n in arr:
            freq[n] = freq.get(n, 0) + 1

    top = [n for n, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)]
    # construir 2 jugadas de 5 números
    j1 = sorted(top[:5])
    j2 = sorted(top[5:10]) if len(top) >= 10 else sorted(list(dict.fromkeys(top[:5] + top[:5]))[:5])

    mult = max(multipliers) if multipliers else 1
    return {"jugadas": [j1, j2], "multiplicador": mult}

@app.get("/api/loto/sugerencias")
def sugerencias():
    dias = int(request.args.get("dias", 90))
    try:
        hist = fetch_historico(dias)
        sug = pick_2_sugerencias_from_data(hist["data"])
        return jsonify({
            "fuente": hist["fuente"],
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "multiplicador": sug["multiplicador"],
            "jugadas": sug["jugadas"]
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
