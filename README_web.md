# FireBrush Web — تشغيل سريع

This folder contains a tiny web version of FireBrush using Three.js and Flask.

Backend (run locally):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

ثم افتح في المتصفح: http://localhost:8000

الواجهة تستخدم Three.js وتدعم اللمس: إصبع واحد للنحت أو للدوران، إصبعان للتكبير/التصغير والتحريك.
