import sys
import ctypes
import glfw
import glm
import numpy as np
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import dearpygui.dearpygui as dpg
from tkinter import messagebox

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

        try:
            self.compute_program = compileProgram(compileShader(cs_source, GL_COMPUTE_SHADER))
            self.relax_compute_shader = compileProgram(compileShader(relax_source, GL_COMPUTE_SHADER))
        except Exception as e:
            print(f"Shader Compilation Error: {e}")

# --- 4. الأنظمة الفرعية (LOD, Material, Brush, Window) ---
class NaniteLODEngine:
    def __init__(self, core):
        self.core = core
        # (كود شيدر LOD الذي قدمته في الجزء 3 يتم تعريفه هنا بنفس الطريقة)

class PearlMaterialSystem:
    def __init__(self):
        # (كود شيدر Pearl MatCap من الجزء 4 يتم تعريفه هنا)
        pass

class SculptBrushSystem:
    def __init__(self, core_engine):
        self.engine = core_engine
        self.brush_type = "Standard"
        self.strength = 1.0
        self.radius = 0.1
        self.relax_enabled = False

    def apply_relax(self):
        if self.relax_enabled and self.engine.relax_compute_shader:
            glUseProgram(self.engine.relax_compute_shader)
            glDispatchCompute((self.engine.max_verts // 256), 1, 1)
            glMemoryBarrier(GL_SHADER_STORAGE_BARRIER_BIT)

    def open_brush_library(self):
        with dpg.window(label="Brush Library", modal=True, width=400, height=300):
            dpg.add_button(label="Clay", width=-1, callback=lambda: self.set_brush("Clay"))
            dpg.add_button(label="Grab", width=-1, callback=lambda: self.set_brush("Grab"))
            dpg.add_button(label="Close", callback=lambda: dpg.delete_item(dpg.last_container()))

    def set_brush(self, name): self.brush_type = name

class FireBrushWindowManager:
    def __init__(self, core):
        self.core = core
        self.ui_visible = True
        self.shortcuts_enabled = False

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
      import psutil
import os
import gc
import numpy as np
import glm
from OpenGL.GL import *
import dearpygui.dearpygui as dpg
from tkinter import filedialog, messagebox

# --- [الجزء #7 و #8 و #9 المدمج]: نظام الفرش المتقدمة، التلوين، و Dyntopo ---
class AdvancedSculptStudio:
    def __init__(self, core):
        self.engine = core
        self.current_tool = "Clay"
        
        # إعدادات PBR و Skin (الجزء #8)
        self.paint_color = [1.0, 1.0, 1.0, 1.0]
        self.metallic = 0.0
        self.roughness = 0.5
        self.negative_mode = False
        
        # إعدادات Dyntopo (الجزء #9 المعدل)
        self.dyntopo_enabled = True
        self.poly_rate = 10 # من -100 إلى 100
        self.light_sculpt = False
        self.sculpt_color = [1.0, 0.8, 0.0, 1.0]

        # أدوات القياس والتحويل
        self.is_measuring = False
        self.measure_points = []

    def set_tool(self, name):
        self.current_tool = name
        # تفعيل الدقة العالية لفرش معينة تلقائياً
        if name in ["Inflate", "Smooth", "CC0"]:
            self.dyntopo_enabled = True
        print(f"[FireBrush] Active Tool: {name}")

    def open_studio_window(self):
        """نافذة Studio الشاملة لجميع الأدوات المتقدمة"""
        if dpg.does_item_exist("StudioWin"): dpg.delete_item("StudioWin")
        
        with dpg.window(label="FireBrush Advanced Studio", tag="StudioWin", width=500, height=650):
            with dpg.tab_bar():
                # تبويب الفرش والأدوات المتقدمة (#7)
                with dpg.tab(label="Tools & Brushes"):
                    with dpg.group(horizontal=True):
                        with dpg.child_window(width=230, height=400):
                            dpg.add_text("Sculpting", color=(0, 255, 255))
                            dpg.add_button(label="Clay (Safe)", width=-1, callback=lambda: self.set_tool("Clay"))
                            dpg.add_button(label="Inflate (Dyntopo)", width=-1, callback=lambda: self.set_tool("Inflate"))
                            dpg.add_button(label="Smooth (+Poly)", width=-1, callback=lambda: self.set_tool("Smooth"))
                            dpg.add_button(label="Crease", width=-1, callback=lambda: self.set_tool("Crease"))
                            dpg.add_separator()
                            dpg.add_text("Movement")
                            dpg.add_button(label="Drag (Path)", width=-1, callback=lambda: self.set_tool("Drag"))
                            dpg.add_button(label="Move (Vector)", width=-1, callback=lambda: self.set_tool("Move"))
                        
                        with dpg.child_window(width=230, height=400):
                            dpg.add_text("Advanced", color=(255, 100, 0))
                            dpg.add_button(label="Sculpt Rig", width=-1, callback=lambda: self.set_tool("SculptRig"))
                            dpg.add_button(label="Transform (Gizmo)", width=-1, callback=lambda: self.set_tool("Transform"))
                            dpg.add_button(label="Measure Tool (cm)", width=-1, callback=lambda: self.set_tool("Measure"))
                            dpg.add_separator()
                            dpg.add_text("Organic")
                            dpg.add_button(label="CC0 (Skin Surface)", width=-1, callback=lambda: self.set_tool("CC0"))
                            dpg.add_button(label="Kill (Flatten)", width=-1, callback=lambda: self.set_tool("Kill"))

                # تبويب Dyntopo والتلوين (#8 & #9)
                with dpg.tab(label="Dyntopo & PBR"):
                    dpg.add_text("DYNAMIC TOPOLOGY", color=(255, 255, 0))
                    dpg.add_checkbox(label="Enable Dyntopo", default_value=True, callback=lambda s, a: setattr(self, 'dyntopo_enabled', a))
                    dpg.add_slider_int(label="Poly Rate (+/-)", default_value=10, min_value=-100, max_value=100, callback=lambda s, a: setattr(self, 'poly_rate', a))
                    
                    dpg.add_separator()
                    dpg.add_text("PBR PAINT & LIGHT", color=(0, 255, 100))
                    dpg.add_color_picker(label="Base Color", default_value=self.paint_color, callback=lambda s, a: setattr(self, 'paint_color', a))
                    dpg.add_checkbox(label="Light with Sculpt", callback=lambda s, a: setattr(self, 'light_sculpt', a))
                    dpg.add_checkbox(label="NEGATIVE MODE", callback=lambda s, a: setattr(self, 'negative_mode', a))

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
def build_advanced_ui_system(app):
    app.studio = AdvancedSculptStudio(app.core)
    app.guardian = FireBrushGuardian(app.core)

    with dpg.viewport_menu_bar():
        with dpg.menu(label="Brushes"):
            dpg.add_menu_item(label="Open Studio...", callback=app.studio.open_studio_window)
import glm
import pyassimp
from tkinter import filedialog, messagebox

# --- [الجزء #13]: نظام الكاميرا الاحترافي (Orbit, Pan, Zoom) ---
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
            path = filedialog.askopenfilename() # تدعم +50 صيغة عبر Assimp
            if path: print(f"Importing {path}...")
        elif action == "EXPORT":
            path = filedialog.asksaveasfilename(defaultextension=".obj")
            if path: print(f"Exporting to {path}...")

# --- بناء القوائم العلوية الشاملة (The Final UI Header) ---
def build_ui_header(app):
    sm = SceneManager(app.core)
    app.scene = sm # ربط المشهد بالتطبيق
    
    with dpg.viewport_menu_bar():
        with dpg.menu(label="File"):
            dpg.add_menu_item(label="New Project", callback=lambda: sm.file_operations("NEW"))
            dpg.add_menu_item(label="Import (+50 Formats)", callback=lambda: sm.file_operations("IMPORT"))
            dpg.add_menu_item(label="Export...", callback=lambda: sm.file_operations("EXPORT"))
            dpg.add_separator()
            dpg.add_menu_item(label="FIX Topology", callback=lambda: print("Fixing..."))

        with dpg.menu(label="Edit"):
            with dpg.menu(label="Add Primitive"):
                for p in ["Sphere", "Cube", "Cylinder", "Torus", "Pyramid", "Cone"]:
                    dpg.add_menu_item(label=f"Add {p}", callback=lambda s, a, user_data=p: sm.add_primitive(user_data))
            dpg.add_separator()
            dpg.add_menu_item(label="Undo (Ctrl+Z)")
            dpg.add_menu_item(label="Redo (Ctrl+Y)")

        with dpg.menu(label="Window"):
            dpg.add_checkbox(label="Show Grid", default_value=True, callback=lambda s, a: setattr(sm, 'show_grid', a))
            dpg.add_color_edit(label="Background Color", default_value=sm.bg_color, callback=lambda s, a: setattr(sm, 'bg_color', a))
class AndroidWindowManager:
    def __init__(self):
        self.window_stack = []

    def create_mobile_window(self, title, tag, width=350, height=500):
        """إنشاء نافذة بمواصفات أندرويد: أزرار كبيرة وزر إغلاق [X]"""
        if dpg.does_item_exist(tag): dpg.show_item(tag)
        else:
            with dpg.window(label=title, tag=tag, width=width, height=height, 
                            no_collapse=True, no_resize=True):
                # شريط الإغلاق العلوي للأندرويد
                with dpg.group(horizontal=True):
                    dpg.add_button(label=" [ X ] ", callback=lambda: dpg.hide_item(tag), 
                                   color=(200, 50, 50), width=60, height=40)
                    dpg.add_text(f"  {title}", color=(255, 255, 255))
                
                dpg.add_separator()
                # هنا نضع محتوى النافذة (فرش، تلوين، إلخ)
  
