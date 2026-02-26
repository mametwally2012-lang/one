from flask import Flask, send_from_directory, jsonify
import os

app = Flask(__name__, static_folder='../frontend', static_url_path='')

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/health')
def health():
    return jsonify({'status':'ok'})

if __name__ == '__main__':
    # يعمل محلياً على المنفذ 8000
    app.run(host='0.0.0.0', port=8000, debug=True)
