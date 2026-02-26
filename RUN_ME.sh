#!/bin/bash

# 🎨 FireBrush Studio - Script التشغيل

echo "🎨 ============================================"
echo "   FireBrush Studio - محرر النحت الذكي"
echo "============================================"
echo ""

# فحص Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 غير مثبت!"
    echo "📥 حمّل من: https://www.python.org"
    exit 1
fi

echo "✅ Python موجود"

# فحص المتطلبات
echo ""
echo "📦 جاري فحص المكتبات..."

pip_packages="numpy glfw PyOpenGL dearpygui glm psutil"

for package in $pip_packages; do
    if python3 -c "import $package" 2>/dev/null; then
        echo "   ✅ $package"
    else
        echo "   ⏳ جاري تثبيت $package..."
        pip3 install $package
    fi
done

echo ""
echo "🚀 جاهز للتشغيل!"
echo ""
echo "⚡ تلميحات للاستخدام:"
echo "   • Alt+الماوس اليسار = دوران الكاميرا"
echo "   • الماوس اليسار = نحت"
echo "   • Space = تمويه"
echo "   • Ctrl+Z = تراجع"
echo "   • ESC = خروج"
echo ""

# تشغيل البرنامج
python3 firebrush.py
