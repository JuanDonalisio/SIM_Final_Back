from flask import Flask, request, render_template
from simulador import Simulador
from flask_cors import CORS

app = Flask(__name__,
            static_folder='files/static',
            template_folder='files')
CORS(app)


@app.route('/simulacion', methods=['POST'])
def simular():
    return Simulador(**request.json).simular()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)
