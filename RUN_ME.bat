@echo off
REM 🎨 FireBrush Studio - Windows Batch Script

echo.
echo 🎨 ============================================
echo    FireBrush Studio - محرر النحت الذكي
echo ============================================
echo.

REM فحص Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python غير مثبت!
    echo 📥 حمّل من: https://www.python.org
    pause
    exit /b 1
)

echo ✅ Python موجود

REM فحص المكتبات
echo.
echo 📦 جاري فحص المكتبات...

for %%p in (numpy glfw PyOpenGL dearpygui glm psutil) do (
    python -c "import %%p" >nul 2>&1
    if errorlevel 1 (
        echo    ⏳ جاري تثبيت %%p...
        pip install %%p
    ) else (
        echo    ✅ %%p
    )
)

echo.
echo 🚀 جاهز للتشغيل!
echo.
echo ⚡ تلميحات:
echo    • Alt + الماوس اليسار = دوران الكاميرا
echo    • الماوس اليسار = نحت
echo    • Space = تمويه
echo    • Ctrl+Z = تراجع
echo    • ESC = خروج
echo.

python firebrush.py
pause
