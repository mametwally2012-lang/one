from flask import Flask, send_from_directory, jsonify, request
import os

app = Flask(__name__, static_folder='../frontend', template_folder='../frontend')

# مكونات النحت (مبدئي)
# في الواقع سنفعل العمليات على الGPU بواسطة شيدرات ويب،
# هذه الطبقة فقط لتسليم ملفات الواجهة وتخزين المشهد.

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

@app.route('/api/scene', methods=['GET', 'POST'])
def scene_api():
    if request.method == 'POST':
        data = request.json
        # يمكن حفظ حالة المشهد أو معالجة بسيطة
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'message': 'حالة المشهد افتراضية'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
