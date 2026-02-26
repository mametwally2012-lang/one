import sys
import ctypes
import glfw
import glm
import numpy as np
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import dearpygui.dearpygui as dpg
from tkinter import messagebox, filedialog
import psutil
import os
import gc
import json

# --- 1. الهياكل البيانية (C-Structs) ---
class Vertex(ctypes.Structure):
    _fields_ = [
        ("position", ctypes.c_float * 4), # x, y, z, w
        ("normal", ctypes.c_float * 4)    # nx, ny, nz, nw
    ]

# --- 2. نظام الكاميرا (لربط مصفوفات العرض) ---
class Camera:
    def __init__(self):
        self.pos = glm.vec3(0, 0, 5)
        self.target = glm.vec3(0, 0, 0)
        self.up = glm.vec3(0, 1, 0)
        self.fov = 45.0
        self.near = 0.1
        self.far = 100.0
        self.width = 1280
        self.height = 720

# --- 3. النواة الرسومية (FireBrush Core) ---
class FireBrushCore:
    def __init__(self, max_verts=1000000):
        self.max_verts = max_verts
        self.vao = None
        self.ssbo = None
        self.compute_program = None
        self.relax_compute_shader = None # تمت إضافته لربط نظام الفرشاة
        
        self.init_gpu_memory()
        self.compile_all_shaders()

    def init_gpu_memory(self):
        """حجز مساحة VRAM"""
        initial_data = (Vertex * self.max_verts)()
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        self.ssbo = glGenBuffers(1)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, self.ssbo)
        glBufferData(GL_SHADER_STORAGE_BUFFER, ctypes.sizeof(initial_data), None, GL_DYNAMIC_DRAW)
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, self.ssbo)
        
        glBindBuffer(GL_ARRAY_BUFFER, self.ssbo)
        glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, ctypes.sizeof(Vertex), ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, ctypes.sizeof(Vertex), ctypes.c_void_p(16))
        glEnableVertexAttribArray(1)
        glBindVertexArray(0)

    def compile_all_shaders(self):
        """تجميع كافة الشيدرات اللازمة للمحرك"""
        # [Compute Shader] - النحت الأساسي
        cs_source = """#version 430 core
        layout(local_size_x = 256) in;
        struct Vertex { vec4 position; vec4 normal; };
        layout(std430, binding = 0) buffer MeshBuffer { Vertex vertices[]; };
        uniform vec3 brushPos; uniform float radius; uniform float strength; uniform bool isSculpting;
        void main() {
            uint id = gl_GlobalInvocationID.x;
            if (id >= vertices.length()) return;
            if (isSculpting) {
                vec3 p = vertices[id].position.xyz;
                float d = distance(p, brushPos);
                if (d < radius) {
                    float force = (1.0 - (d / radius)) * strength * 0.01;
                    vertices[id].position.xyz += normalize(p - brushPos) * force;
                }
            }
        }"""
        
        # [Relax Shader] - لتوزيع المضلعات ومنع التشويه
        relax_source = """#version 430 core
        layout(local_size_x = 256) in;
        struct Vertex { vec4 position; vec4 normal; };
        layout(std430, binding = 0) buffer MeshBuffer { Vertex vertices[]; };
        void main() {
            uint id = gl_GlobalInvocationID.x;
            if (id <= 0 || id >= vertices.length() - 1) return;
            // Laplacian Smoothing بسيط
            vec3 prev = vertices[id-1].position.xyz;
            vec3 next = vertices[id+1].position.xyz;
            vertices[id].position.xyz = mix(vertices[id].position.xyz, (prev + next) * 0.5, 0.1);
        }"""
        
        # [Vertex Shader] - رسم المجسمات
        vs_source = """#version 430 core
        layout(location = 0) in vec4 position;
        layout(location = 1) in vec4 normal;
        
        uniform mat4 view;
        uniform mat4 projection;
        
        out vec3 fragPos;
        out vec3 fragNormal;
        
        void main() {
            fragPos = position.xyz;
            fragNormal = normal.xyz;
            gl_Position = projection * view * position;
        }"""
        
        # [Fragment Shader] - الإضاءة والألوان
        fs_source = """#version 430 core
        in vec3 fragPos;
        in vec3 fragNormal;
        
        uniform vec4 baseColor;
        uniform float metallic;
        uniform float roughness;
        
        out vec4 FragColor;
        
        void main() {
            // إضاءة بسيطة
            vec3 light = normalize(vec3(1.0, 1.0, 1.0));
            float diff = max(dot(normalize(fragNormal), light), 0.0);
            vec3 result = baseColor.xyz * (0.3 + 0.7 * diff);
            FragColor = vec4(result, baseColor.a);
        }"""

        try:
            self.compute_program = compileProgram(compileShader(cs_source, GL_COMPUTE_SHADER))
            self.relax_compute_shader = compileProgram(compileShader(relax_source, GL_COMPUTE_SHADER))
            
            # محاولة تجميع شيدرات الرسم (اختيارية)
            try:
                vs = compileShader(vs_source, GL_VERTEX_SHADER)
                fs = compileShader(fs_source, GL_FRAGMENT_SHADER)
                self.render_program = compileProgram(vs, fs)
            except:
                self.render_program = None
                print("[Shader] تنبيه: لم يتم تجميع شيدرات الرسم")
        except Exception as e:
            print(f"Shader Compilation Error: {e}")

# --- 4. الأنظمة الفرعية (LOD, Material, Brush, Window) ---
class NaniteLODEngine:
    """نظام مستويات التفاصيل - بسيط وفعّال"""
    def __init__(self, core):
        self.core = core
        self.current_lod = 0
    
    def calculate_lod(self, camera_distance):
        """تحديد مستوى التفاصيل"""
        if camera_distance < 5:
            return 100000
        elif camera_distance < 15:
            return 50000
        else:
            return 25000

class PearlMaterialSystem:
    """نظام المواد البسيط"""
    def __init__(self):
        self.current_material = "Clay"
        self.materials = {
            "Clay": (0.8, 0.7, 0.6, 1.0),
            "Stone": (0.5, 0.5, 0.5, 1.0),
            "Metal": (0.9, 0.9, 0.9, 1.0),
        }
    
    def get_material(self, name):
        return self.materials.get(name, self.materials["Clay"])

class SculptBrushSystem:
    def __init__(self, core_engine):
        self.engine = core_engine
        self.brush_type = "Clay"
        self.strength = 1.0
        self.radius = 0.1
        self.relax_enabled = False
        
        # نظام بسيط: 5 فرش فقط
        self.brushes = {
            "Clay": {"strength_mult": 1.0, "icon": "🔨"},
            "Smooth": {"strength_mult": 0.5, "icon": "🎨"},
            "Grab": {"strength_mult": 0.8, "icon": "✋"},
            "Crease": {"strength_mult": 1.5, "icon": "📐"},
            "Flatten": {"strength_mult": 0.9, "icon": "📏"}
        }

    def apply_relax(self):
        if self.relax_enabled and self.engine.relax_compute_shader:
            glUseProgram(self.engine.relax_compute_shader)
            glDispatchCompute((self.engine.max_verts // 256), 1, 1)
            glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)

    def set_brush(self, name):
        if name in self.brushes:
            self.brush_type = name
            mult = self.brushes[name]["strength_mult"]
            icon = self.brushes[name]["icon"]
            print(f"[Brush] {icon} تم تفعيل: {name} (x{mult})")

class FireBrushWindowManager:
    def __init__(self):
        self.core = core
        self.ui_visible = True
        self.shortcuts_enabled = False
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 20

    def save_undo_state(self):
        """حفظ حالة النموذج الحالية للـ undo"""
        if len(self.undo_stack) >= self.max_undo_steps:
            self.undo_stack.pop(0)
        # في تطبيق حقيقي يتم حفظ نسخة من البياناتglBindBuffer(GL_COPY_READ_BUFFER, self.core.ssbo)
        # glBindBuffer(GL_COPY_WRITE_BUFFER, backup_buffer)
        # glCopyBufferSubData(...)
        self.undo_stack.append("checkpoint")
        self.redo_stack.clear()
        print("[Undo] حفظ نقطة تفتيش")

    def undo(self):
        """التراجع عن آخر تعديل"""
        if self.undo_stack:
            state = self.undo_stack.pop()
            self.redo_stack.append(state)
            print("[Undo] تراجع ✓")
        else:
            print("[Undo] لا توجد حالات للتراجع عنها")

    def redo(self):
        """إعادة آخر تعديل"""
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(state)
            print("[Redo] إعادة ✓")
        else:
            print("[Redo] لا توجد حالات للإعادة")

    def toggle_interface(self):
        self.ui_visible = not self.ui_visible
        # منطق التبديل...

# --- 5. بناء الواجهة الرسومية (Main UI) ---
def setup_firebrush_ui(core_engine):
    brush_sys = SculptBrushSystem(core_engine)
    win_mgr = FireBrushWindowManager(core_engine)

    dpg.create_context()
    with dpg.viewport_menu_bar():
        with dpg.menu(label="Sculpt"):
            dpg.add_slider_float(label="Strength", max_value=5000.0, callback=lambda s, a: setattr(brush_sys, 'strength', a))
            dpg.add_slider_float(label="Radius", max_value=10.0, callback=lambda s, a: setattr(brush_sys, 'radius', a))
            dpg.add_checkbox(label="Relax (Auto Fix)", callback=lambda s, a: setattr(brush_sys, 'relax_enabled', a))
            dpg.add_button(label="Brush Library...", callback=brush_sys.open_brush_library)
        
        with dpg.menu(label="Window"):
            dpg.add_menu_item(label="الواجهة (✓)", callback=win_mgr.toggle_interface)

    dpg.create_viewport(title='FireBrush Engine', width=1280, height=720)
    dpg.setup_dearpygui()
    dpg.show_viewport()

# --- 6. التشغيل التجريبي ---
if __name__ == "__main__":
    if not glfw.init():
        sys.exit()
    
    # نافذة مخفية لتهيئة OpenGL
    glfw.window_hint(glfw.VISIBLE, False)
    window = glfw.create_window(1280, 720, "Data Context", None, None)
    glfw.make_context_current(window)

    core = FireBrushCore()
    setup_firebrush_ui(core)
    
    print("[FireBrush] Engine Ready.")
    # dpg.start_dearpygui() # تفعيل هذا السطر عند اكتمال حلقة الرسم
    dpg.destroy_context()
    glfw.terminate()

# --- [الجزء #7 و #8 و #9 المدمج]: نظام الفرش المتقدمة، التلوين، و Dyntopo ---
class AdvancedSculptStudio:
    """نظام النحت المتقدم - بسيط وسهل"""
    def __init__(self, core):
        self.engine = core
        self.current_tool = "Clay"
        
        # الإعدادات الأساسية فقط
        self.strength = 1.0
        self.radius = 0.1
        self.dyntopo_enabled = True
        self.relax_enabled = False
        
        # نظام الفرش البسيط
        self.brushes = {
            "Clay": {"strength_mult": 1.0, "icon": "🔨"},
            "Smooth": {"strength_mult": 0.5, "icon": "🎨"},
            "Grab": {"strength_mult": 0.8, "icon": "✋"},
            "Crease": {"strength_mult": 1.5, "icon": "📐"},
            "Flatten": {"strength_mult": 0.9, "icon": "📏"}
        }

    def set_tool(self, name):
        """تعيين الأداة الحالية"""
        if name in self.brushes:
            self.current_tool = name
            info = self.brushes[name]
            print(f"[Sculpt] {info['icon']} {name} جاهز للاستخدام")

# --- [الجزء #10 و #11]: الحماية، القناع، والذاكرة ---
class FireBrushGuardian:
    def __init__(self, core):
        self.core = core
        self.process = psutil.Process(os.getpid())
        self.use_backface_mask = True
        self.optimize_system()

    def optimize_system(self):
        """رفع أولوية المعالج (الجزء #11)"""
        try:
            prio = psutil.HIGH_PRIORITY_CLASS if os.name == 'nt' else -15
            self.process.nice(prio)
        except: pass

    def monitor_and_mask(self, camera_dir):
        """إدارة الذاكرة (الجزء #11) وتحديث قناع الكاميرا (#10)"""
        # 1. مراقبة الرام
        if psutil.virtual_memory().percent > 90.0:
            glFinish()
            gc.collect()
        
        # 2. إرسال اتجاه الكاميرا للشيدر لمنع الاختراق (Backface Masking)
        if self.core.compute_program:
            glUseProgram(self.core.compute_program)
            glUniform3f(glGetUniformLocation(self.core.compute_program, "cameraDir"), *camera_dir)
            glUniform1i(glGetUniformLocation(self.core.compute_program, "useBackfaceMask"), self.use_backface_mask)

# --- دالة الربط النهائي للواجهة ---
# --- نظام الكاميرا الاحترافي (Orbit, Pan, Zoom) ---
class FireBrushCamera:
    def __init__(self):
        self.target = glm.vec3(0, 0, 0)
        self.radius = 10.0
        self.theta = 0.0 # دوران أفقي
        self.phi = 0.0   # دوران رأسي
        self.eye = glm.vec3(0, 0, 10)
        self.up = glm.vec3(0, 1, 0)
        self.sensitivity = 0.005
        self.zoom_speed = 0.5

    def update_orbit(self, dx, dy):
        self.theta -= dx * self.sensitivity
        self.phi = glm.clamp(self.phi + dy * self.sensitivity, -1.5, 1.5)
        self.update_vectors()

    def update_pan(self, dx, dy):
        forward = glm.normalize(self.target - self.eye)
        right = glm.normalize(glm.cross(forward, self.up))
        actual_up = glm.cross(right, forward)
        self.target += (right * -dx + actual_up * dy) * self.sensitivity
        self.update_vectors()

    def update_zoom(self, delta):
        self.radius = max(0.1, self.radius - delta * self.zoom_speed)
        self.update_vectors()

    def update_vectors(self):
        self.eye.x = self.target.x + self.radius * glm.cos(self.phi) * glm.sin(self.theta)
        self.eye.y = self.target.y + self.radius * glm.sin(self.phi)
        self.eye.z = self.target.z + self.radius * glm.cos(self.phi) * glm.cos(self.theta)

# --- [الجزء #12 و #14]: إدارة الملفات، المجسمات، والبيئة ---
class SceneManager:
    def __init__(self, core):
        self.core = core
        self.show_grid = True
        self.bg_color = [0.1, 0.1, 0.1, 1.0]
        self.camera = FireBrushCamera()

    def add_primitive(self, p_type):
        """المصنع الهندسي لإضافة (Sphere, Cube, Cylinder, Torus, Pyramid, Cone)"""
        print(f"[Primitive] Adding {p_type} at (0,0,0)")
        # منطق توليد النقاط في الـ SSBO يتم استدعاؤه هنا

    def file_operations(self, action):
        if action == "NEW":
            if messagebox.askyesno("تحذير", "إن ضغطت ستزيل كل شيء! هل أنت متأكد؟"):
                # تصفير الـ SSBO
                pass
        elif action == "IMPORT":
            # دعم صيغ متعددة
            filetypes = [
                ("جميع الملفات المدعومة", "*.obj *.fbx *.gltf *.glb *.ply *.stl"),
                ("Wavefront OBJ", "*.obj"),
                ("FBX Model", "*.fbx"),
                ("glTF", "*.gltf *.glb"),
                ("PLY", "*.ply"),
                ("STL", "*.stl"),
                ("جميع الملفات", "*.*")
            ]
            path = filedialog.askopenfilename(filetypes=filetypes)
            if path:
                ext = os.path.splitext(path)[1].lower()
                print(f"📂 جاري استيراد {ext}: {os.path.basename(path)}...")
                # يمكن إضافة معالج فعلي لاحقاً
        elif action == "EXPORT":
            # صيغ التصدير المدعومة
            filetypes = [
                ("Wavefront OBJ", "*.obj"),
                ("FBX Model", "*.fbx"),
                ("glTF Binary", "*.glb"),
                ("PLY", "*.ply"),
                ("STL", "*.stl"),
            ]
            path = filedialog.asksaveasfilename(filetypes=filetypes, defaultextension=".obj")
            if path:
                ext = os.path.splitext(path)[1].lower()
                print(f"💾 جاري تصدير إلى {ext}: {os.path.basename(path)}...")
                # يمكن إضافة معالج فعلي لاحقاً

# --- بناء القوائم العلوية الشاملة (The Final UI Header) ---

class AndroidWindowManager:
    """إدارة النوافذ البسيطة"""
    def __init__(self):
        self.window_stack = []
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 20

    def save_undo_state(self):
        """حفظ حالة النموذج الحالية"""
        if len(self.undo_stack) >= self.max_undo_steps:
            self.undo_stack.pop(0)
        self.undo_stack.append("checkpoint")
        self.redo_stack.clear()

    def undo(self):
        """التراجع"""
        if self.undo_stack:
            state = self.undo_stack.pop()
            self.redo_stack.append(state)
            print("[✓] تراجع")

    def redo(self):
        """إعادة"""
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(state)
            print("[✓] إعادة")

# --- التطبيق الرئيسي الكامل مع حلقة الرسم ---
class FireBrushApplication:
    def __init__(self):
        if not glfw.init():
            print("[ERROR] فشل تهيئة GLFW")
            sys.exit(1)
        
        # إعدادات النافذة
        glfw.window_hint(glfw.VISIBLE, True)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        
        self.window = glfw.create_window(1280, 720, "FireBrush Studio", None, None)
        if not self.window:
            print("[ERROR] فشل إنشاء النافذة")
            glfw.terminate()
            sys.exit(1)
        
        glfw.make_context_current(self.window)
        glfw.set_input_mode(self.window, glfw.CURSOR, glfw.CURSOR_NORMAL)
        
        # المتغيرات
        self.running = True
        self.last_x, self.last_y = 640, 360
        self.sculpting = False
        self.orbiting = False
        self.last_sculpt_time = 0
        
        # المحركات
        self.core = FireBrushCore()
        self.scene = SceneManager(self.core)
        self.studio = AdvancedSculptStudio(self.core)
        self.guardian = FireBrushGuardian(self.core)
        self.window_mgr = FireBrushWindowManager(self.core)
        
        # الواجهة
        dpg.create_context()
        self.setup_ui()
        dpg.create_viewport(title='FireBrush Viewport', width=1280, height=720)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        
        # ربط الإدخال
        glfw.set_cursor_pos_callback(self.window, self.mouse_callback)
        glfw.set_mouse_button_callback(self.window, self.mouse_button_callback)
        glfw.set_key_callback(self.window, self.key_callback)
        
        # Android touch-specific setup if running on Android
        if sys.platform.startswith('linux') and 'ANDROID_ROOT' in os.environ:
            # GLFW doesn't expose multitouch API; in a real Android build
            # we'd integrate with JNI or use a specialized touch library.
            # Here we stub handlers for demonstration.
            self.touches = {}          # id -> (x, y)
            self.last_distance = None
            self.pan_start = None
            print("[Android] touch system enabled")
        
        print("[FireBrush] التطبيق جاهز للعمل ✅")

    def setup_ui(self):
        """واجهة بسيطة وواضحة - بدون تعقيدات"""
        with dpg.viewport_menu_bar():
            with dpg.menu(label="📁 ملف"):
                dpg.add_menu_item(label="🆕 جديد", callback=self.new_project)
                dpg.add_menu_item(label="📂 استيراد", callback=self.import_model)
                dpg.add_menu_item(label="💾 تصدير", callback=self.export_model)
                dpg.add_separator()
                dpg.add_menu_item(label="❌ خروج", callback=lambda: setattr(self, 'running', False))
            
            with dpg.menu(label="🎨 الفرش"):
                for brush_name, brush_info in self.studio.brushes.items():
                    icon = brush_info["icon"]
                    dpg.add_menu_item(label=f"{icon} {brush_name}", 
                                     callback=lambda s, a, name=brush_name: self.studio.set_brush(name))
            
            with dpg.menu(label="⚙️ الإعدادات"):
                dpg.add_slider_float(label="💪 قوة", default_value=1.0, min_value=0.1, max_value=5.0,
                                    callback=lambda s, a: setattr(self.studio, 'strength', a))
                dpg.add_slider_float(label="🔵 حجم", default_value=0.1, min_value=0.05, max_value=2.0,
                                    callback=lambda s, a: setattr(self.studio, 'radius', a))
                dpg.add_checkbox(label="🧹 تمويه تلقائي",
                                callback=lambda s, a: setattr(self.studio, 'relax_enabled', a))
            
            with dpg.menu(label="👁️ العرض"):
                dpg.add_checkbox(label="شبكة", default_value=True,
                                callback=lambda s, a: setattr(self.scene, 'show_grid', a))
                dpg.add_color_edit(label="خلفية", default_value=self.scene.bg_color,
                                  callback=lambda s, a: setattr(self.scene, 'bg_color', a))

    def mouse_callback(self, window, xpos, ypos):
        """معالجة حركة الماوس/لمس (Android)"""
        dx = xpos - self.last_x
        dy = ypos - self.last_y
        
        # Android multitouch gestures
        if hasattr(self, 'touches') and self.touches:
            # سنعالج تحركات اللمس يدويًا عبر callback آخر
            pass
        else:
            # دوران بـ Alt+LMB
            if self.orbiting:
                self.scene.camera.update_orbit(dx, dy)
            # نحت بـ LMB عادي
            elif self.sculpting:
                pass
        self.last_x, self.last_y = xpos, ypos

    def mouse_button_callback(self, window, button, action, mods):
        """معالجة أزرار الماوس"""
        import time
        
        # Alt + LMB للدوران
        if button == glfw.MOUSE_BUTTON_LEFT and (mods & glfw.MOD_ALT):
            if action == glfw.PRESS:
                self.orbiting = True
            elif action == glfw.RELEASE:
                self.orbiting = False
        
        # LMB عادي للنحت
        elif button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS:
            self.sculpting = True
            self.last_sculpt_time = time.time()
            self.window_mgr.save_undo_state()
        elif button == glfw.MOUSE_BUTTON_LEFT and action == glfw.RELEASE:
            self.sculpting = False
        
        # عجلة التمرير للتكبير
        if button == glfw.MOUSE_BUTTON_MIDDLE and action == glfw.PRESS:
            self.scene.camera.update_zoom(1.0)

    def key_callback(self, window, key, scancode, action, mods):
        """معالجة لوحة المفاتيح"""
        if action != glfw.PRESS:
            return
        
        if key == glfw.KEY_ESCAPE:
            self.running = False
        elif key == glfw.KEY_SPACE:
            self.studio.set_tool("Smooth")
        elif key == glfw.KEY_G:
            self.studio.set_tool("Grab")
        elif key == glfw.KEY_R:
            self.studio.relax_enabled = not self.studio.relax_enabled
            print(f"[Relax] {'✅ فعّل' if self.studio.relax_enabled else '❌ عطّل'}")
        elif key == glfw.KEY_Z and (mods & glfw.MOD_CONTROL):
            self.window_mgr.undo()
        elif key == glfw.KEY_Y and (mods & glfw.MOD_CONTROL):
            self.window_mgr.redo()
        elif key == glfw.KEY_S and (mods & glfw.MOD_CONTROL):
            print("[Save] حفظ نقطة تفتيش...")

    # --- Android touch gesture helper methods ---
    def android_touch_begin(self, touch_id, x, y):
        # touch_id is a platform-specific identifier
        self.touches[touch_id] = (x, y)
        if len(self.touches) == 1:
            # first finger: decide later in move
            self.single_touch_active = True
        elif len(self.touches) == 2:
            pts = list(self.touches.values())
            self.last_distance = glm.distance(glm.vec2(*pts[0]), glm.vec2(*pts[1]))
            self.pan_start = ((pts[0][0]+pts[1][0])/2, (pts[0][1]+pts[1][1])/2)

    def android_touch_move(self, touch_id, x, y):
        if touch_id not in self.touches:
            return
        prev = self.touches[touch_id]
        self.touches[touch_id] = (x, y)
        if len(self.touches) == 1:
            # single finger; choose orbit or sculpt based on single_touch_active
            if self.single_touch_active:
                # when touching mesh, sculpt
                self.sculpting = True
            else:
                self.scene.camera.update_orbit(x - prev[0], y - prev[1])
        elif len(self.touches) == 2:
            pts = list(self.touches.values())
            dist = glm.distance(glm.vec2(*pts[0]), glm.vec2(*pts[1]))
            if self.last_distance is not None:
                if abs(dist - self.last_distance) < 5:
                    # pan
                    dx = ((pts[0][0]+pts[1][0])/2) - self.pan_start[0]
                    dy = ((pts[0][1]+pts[1][1])/2) - self.pan_start[1]
                    self.scene.camera.update_pan(dx, dy)
                    self.pan_start = ((pts[0][0]+pts[1][0])/2, (pts[0][1]+pts[1][1])/2)
                elif dist < self.last_distance:
                    self.scene.camera.update_zoom(1.0)
                else:
                    self.scene.camera.update_zoom(-1.0)
            self.last_distance = dist

    def android_touch_end(self, touch_id):
        if touch_id in self.touches:
            del self.touches[touch_id]
        self.sculpting = False
        self.single_touch_active = False

    def render_frame(self):
        """رسم إطار واحد مع المجسم"""
        # تحديد لون الخلفية
        glClearColor(*self.scene.bg_color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # تفعيل المضلعات
        glEnable(GL_DEPTH_TEST)
        
        # تحديث الكاميرا
        view = glm.lookAt(self.scene.camera.eye, self.scene.camera.target, self.scene.camera.up)
        proj = glm.perspective(glm.radians(45.0), 1280/720, 0.1, 100.0)
        
        # رسم الشبكة الأرضية إذا كانت مفعلة
        if self.scene.show_grid:
            self.draw_grid()
        
        # رسم المجسم/النموذج (الكرة الافتراضية الآن)
        self.draw_mesh(view, proj)
        
        # تطبيق النحت إذا كان يجري
        if self.sculpting and self.core.compute_program:
            glUseProgram(self.core.compute_program)
            
            # حساب موضع الفرشاة بناءً على موضع الماوس والكاميرا
            brush_pos = self.scene.camera.target  # موضع بسيط وسط النموذج
            
            glUniform3f(glGetUniformLocation(self.core.compute_program, "brushPos"), *brush_pos)
            glUniform1f(glGetUniformLocation(self.core.compute_program, "radius"), self.studio.radius)
            glUniform1f(glGetUniformLocation(self.core.compute_program, "strength"), self.studio.strength)
            glUniform1i(glGetUniformLocation(self.core.compute_program, "isSculpting"), True)
            
            glDispatchCompute((self.core.max_verts // 256), 1, 1)
            glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT | GL_VERTEX_ATTRIB_ARRAY_BARRIER_BIT)
            
            # تطبيق Relax إذا كان مفعلاً
            if self.studio.relax_enabled:
                self.studio.apply_relax()
        
        # تحديث مراقبة الذاكرة
        camera_dir = glm.normalize(self.scene.camera.target - self.scene.camera.eye)
        self.guardian.monitor_and_mask(tuple(camera_dir))

    def draw_mesh(self, view, proj):
        """رسم المجسم على الشاشة"""
        if self.core.render_program is None:
            return
        
        glUseProgram(self.core.render_program)
        glBindVertexArray(self.core.vao)
        
        # مصفوفات التحويل
        model = glm.mat4(1.0)
        view_loc = glGetUniformLocation(self.core.render_program, "view")
        proj_loc = glGetUniformLocation(self.core.render_program, "projection")
        
        glUniformMatrix4fv(view_loc, 1, GL_FALSE, glm.value_ptr(view))
        glUniformMatrix4fv(proj_loc, 1, GL_FALSE, glm.value_ptr(proj))
        
        # رسم المجسم
        glDrawArrays(GL_POINTS, 0, self.core.max_verts)
        glBindVertexArray(0)

    def draw_grid(self):
        """رسم شبكة مرجعية على الأرض"""
        glDisable(GL_DEPTH_TEST)
        glLineWidth(0.5)
        glColor3f(0.3, 0.3, 0.3)
        
        glBegin(GL_LINES)
        size = 10
        step = 1
        for i in range(-size, size+1, step):
            glVertex3f(i, -5, -size)
            glVertex3f(i, -5, size)
            glVertex3f(-size, -5, i)
            glVertex3f(size, -5, i)
        glEnd()
        
        glEnable(GL_DEPTH_TEST)

    def main_loop(self):
        """حلقة الرسم الرئيسية"""
        while self.running and not glfw.window_should_close(self.window):
            # معالجة أحداث GLFW
            glfw.poll_events()
            
            # رسم إطار OpenGL
            self.render_frame()
            
            # رسم واجهة dearpygui
            dpg.render_frame()
            
            # تبديل الـ buffers
            glfw.swap_buffers(self.window)
            
            # حد أقصى 60 FPS
            import time
            time.sleep(1/60)

    def cleanup(self):
        """تنظيف الموارد"""
        dpg.destroy_context()
        glfw.destroy_window(self.window)
        glfw.terminate()
        print("[FireBrush] تم الإغلاق بنجاح ✅")

    def new_project(self):
        """مشروع جديد"""
        print("[Project] مشروع جديد")

    def import_model(self):
        """استيراد نموذج"""
        print("[Import] استيراد نموذج")

    def export_model(self):
        """تصدير النموذج"""
        print("[Export] تصدير النموذج")


# --- نقطة الدخول الرئيسية ---
if __name__ == "__main__":
    app = FireBrushApplication()
    app.main_loop()
    app.cleanup()
