from flask import Flask, jsonify, request
import requests
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# -----------------------------
# Helpers
# -----------------------------
def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def parse_results_str(s: str):
    """
    Convierte "05-12-19-23-33" -> [5,12,19,23,33]
    """
    try:
        parts = s.split("-")
        nums = []
        for p in parts:
            p = p.strip()
            if p:
                nums.append(int(p))
        return nums
    except Exception:
        return None

def fetch_loto_draws_last_90_days():
    """
    Consume el Azure API que usa loteriasdepuertorico.pr.gov según tu captura:
    /api/ElectronicDrawing/ElectronicDrawingDateSearch/<gameId>/<start>/<end>

    IMPORTANTE:
    - Esta API espera fechas en formato YYYY-MM-DD (SIN HORA).
    - Si incluyes " 20:23:59" o parecido, devuelve 400 Bad Request.
    """
    game_id = 8  # Loto

    # Fechas SOLO YYYY-MM-DD (sin hora)
    today = datetime.now(timezone.utc).date()
    start_date = (today - timedelta(days=90)).isoformat()
    end_date = today.isoformat()

    url = (
        "https://wordpresswebapi.azurewebsites.net/api/ElectronicDrawing/"
        f"ElectronicDrawingDateSearch/{game_id}/{start_date}/{end_date}"
    )

    # A veces ayuda un User-Agent para evitar bloqueos raros
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers, timeout=30)

    # Si falla, devolvemos info clara para debug
    if not r.ok:
        return {
            "fuente": "Loterías PR (Azure API)",
            "rango": {"start": start_date, "end": end_date},
            "error": {
                "status_code": r.status_code,
                "url": url,
                "body": (r.text[:500] if r.text else "")
            },
            "draws": []
        }

    data = r.json()

    draws = []
    if isinstance(data, list):
        for item in data:
            results = item.get("results") or item.get("formattedResults")
            draw_date = item.get("drawingDate")

            mult = item.get("multiplier")  # a veces viene null
            formatted_mult = item.get("formattedMultiplier")  # a veces "2", "3"...
            plus = item.get("formattedPlus")

            nums = None
            if isinstance(results, str):
                nums = parse_results_str(results)

            multiplicador_final = None
            if formatted_mult is not None and str(formatted_mult).strip().isdigit():
                multiplicador_final = int(str(formatted_mult).strip())
            elif isinstance(mult, int):
                multiplicador_final = mult

            draws.append({
                "fecha": draw_date,
                "numeros": nums,
                "multiplicador": multiplicador_final,
                "plus": plus,
                "raw": item
            })

    return {
        "fuente": "Loterías PR (Azure API)",
        "rango": {"start": start_date, "end": end_date},
        "draws": draws
    }

def build_frequency(draws):
    """
    Conteo simple de frecuencias.
    """
    freq = {}
    for d in draws:
        nums = d.get("numeros")
        if not nums:
            continue
        for n in nums:
            freq[n] = freq.get(n, 0) + 1
    return freq

def generate_suggestions(draws, k=3, pick=5):
    """
    Genera k jugadas de 'pick' números.
    """
    freq = build_frequency(draws)
    if not freq:
        return [[1, 2, 3, 4, 5]]  # fallback

    sorted_nums = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    top = [n for n, _ in sorted_nums[:15]]               # top 15
    mid = [n for n, _ in sorted_nums[15:40]] or top[:]  # mid o fallback

    import random
    random.seed()

    suggestions = set()
    attempts = 0
    while len(suggestions) < k and attempts < 200:
        attempts += 1
        chosen = set()

        while len(chosen) < pick:
            if len(chosen) < max(1, pick - 2):
                chosen.add(random.choice(top))
            else:
                chosen.add(random.choice(mid))

        jugada = tuple(sorted(chosen))
        suggestions.add(jugada)

    return [list(x) for x in suggestions]

def infer_multiplier(draws):
    """
    Multiplicador:
    - usa el más reciente no-null si existe
    - si no hay, 1
    """
    for d in reversed(draws):
        m = d.get("multiplicador")
        if isinstance(m, int) and m >= 1:
            return m
    return 1


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Loteria backend online. Usa /resultados o /api/loto/sugerencias"
    })

@app.route("/resultados")
def resultados():
    """
    Devuelve sorteos últimos 90 días pero LIMPIO (no raw gigante).
    Query optional: ?limit=20
    """
    limit = request.args.get("limit", default="20")
    try:
        limit = int(limit)
    except:
        limit = 20

    data = fetch_loto_draws_last_90_days()

    # Si hubo error al llamar Azure, lo devolvemos tal cual
    if data.get("error"):
        return jsonify(data), 502

    clean = []
    for d in data["draws"]:
        if d.get("numeros"):
            clean.append({
                "fecha": d.get("fecha"),
                "numeros": d.get("numeros"),
                "multiplicador": d.get("multiplicador")
            })

    # últimos "limit"
    clean = list(reversed(clean))[:limit]

    return jsonify({
        "fuente": data["fuente"],
        "rango": data["rango"],
        "total": len(clean),
        "sorteos": clean
    })

@app.route("/api/loto/sugerencias")
def sugerencias():
    """
    Endpoint final para la app Android.
    """
    data = fetch_loto_draws_last_90_days()

    # Si hubo error al llamar Azure, lo devolvemos (así no ves 500 sin explicación)
    if data.get("error"):
        return jsonify(data), 502

    valid_draws = [d for d in data["draws"] if d.get("numeros")]

    # 2 sugerencias
    jugadas = generate_suggestions(valid_draws, k=2, pick=5)
    mult = infer_multiplier(valid_draws)

    hoy = datetime.now(timezone.utc).date().isoformat()

    return jsonify({
        "fecha": hoy,
        "fuente": data["fuente"],
        "multiplicador": mult,
        "jugadas": jugadas
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
