from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/resultados')
def obtener_resultados():
    url = 'https://loteriatradicionalpr.net/confrontar/'
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        tabla = soup.find('table')
        if not tabla:
            return jsonify({"error": "No se encontró la tabla"}), 404

        rows = tabla.find_all('tr')[1:]  # omitir encabezado
        resultados = []

        for row in rows[:6]:  # últimos 6 sorteos
            cols = row.find_all('td')
            if len(cols) >= 3:
                fecha = cols[0].text.strip()
                combinacion = cols[1].text.strip()
                serie = cols[2].text.strip()
                resultados.append({
                    'fecha': fecha,
                    'combinacion': combinacion,
                    'serie': serie
                })

        return jsonify(resultados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
