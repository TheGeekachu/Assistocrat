import os
import re
import sys
import tempfile
import subprocess
import reflex as rx
from openrouter import OpenRouter

client = OpenRouter(
    api_key=os.getenv("HACKCLUB_API_KEY", ""),
    server_url="https://ai.hackclub.com/proxy/v1",
    timeout_ms=15000,
)

MESHLIB_SYSTEM_PROMPT = """You are an automated Python code generator specializing in the MeshLib library (`meshlib.mrmeshpy`).

### ABSOLUTE OUTPUT RULES:
1. Return ONLY executable Python code inside a single ```python code block.
2. DO NOT include explanations, reasoning, thought process, or extra text.
3. Always assign the final output object to a variable named `final_mesh`.
4. DO NOT import meshlib inside the block or call mesh saving/export commands; assume standard dependencies and helpers are injected globally.

### AVAILABLE PRIMITIVES & HELPERS:
- Vectors & Matrices:
  - `Vector3f(x, y, z)`
  - `Matrix3f.rotation(Vector3f(axis_x, axis_y, axis_z), angle_rad)`
- Transforms:
  - `AffineXf3f.translation(Vector3f(x, y, z))`
  - `AffineXf3f.rotation(Vector3f(axis_x, axis_y, axis_z), angle_rad)`
  - Transform mesh: `mesh.transform(xf)`
- Primitives:
  - `makeCube(Vector3f(size_x, size_y, size_z))`
  - `makeCylinder(radius, length, resolution)`
  - `makeUVSphere(radius, resolution_u, resolution_v)`
  - `makeCone(radius, height, resolution)`
  - `makeTorus(primaryRadius, secondaryRadius)`
- Boolean CSG Helpers:
  - `booleanSub(meshA, meshB)` -> Returns Difference (meshA minus meshB)
  - `booleanOr(meshA, meshB)` -> Returns Union
  - `booleanAnd(meshA, meshB)` -> Returns Intersection

### GEOMETRY RULES:
- Every boolean operation (`booleanOr`, `booleanSub`, `booleanAnd`) MUST take two valid Mesh objects.
- NEVER pass `None` or unassigned variables into boolean helper functions.
- Always initialize `final_mesh` as a valid primitive before performing boolean unions or subtractions.
"""

class CADState(rx.State):
    user_prompt: str = ""
    ai_generated_markdown: str = ""
    raw_code_block: str = ""
    execution_status: str = "Ready to generate."
    is_loading: bool = False
    is_compiling: bool = False

    def set_user_prompt(self, value: str):
        self.user_prompt = value

    def generate_design_code(self):
        if not self.user_prompt.strip():
            self.execution_status = "⚠️ Please enter a prompt first."
            return

        self.is_loading = True
        self.execution_status = "Requesting model code generation..."
        self.ai_generated_markdown = "Generating CAD code..."
        yield

        try:
            response = client.chat.send(
                model="google/gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": MESHLIB_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Generate a simple MeshLib python script for: {self.user_prompt}",
                    },
                ],
                stream=False,
            )

            raw_text = response.choices[0].message.content or ""
            self.ai_generated_markdown = raw_text

            match = re.search(r"```python\s*(.*?)\s*```", raw_text, re.DOTALL)
            if match:
                self.raw_code_block = match.group(1).strip()
            else:
                self.raw_code_block = raw_text.replace("```", "").strip()

            self.execution_status = "Code generated! Click 'Compile & Download STL'."

        except Exception as e:
            self.execution_status = f"Request Failed: {str(e)}"
            self.ai_generated_markdown = f"### Request Error\n`{str(e)}`"

        self.is_loading = False

    def compile_stl_locally(self):
        if not self.raw_code_block:
            self.execution_status = "No code available to compile!"
            return

        self.is_compiling = True
        self.execution_status = "⏳ Compiling STL geometry in subprocess..."
        yield

        output_stl_file = "output_design.stl"

        runner_script = f"""
import math
import meshlib.mrmeshpy as mr

Vector3f = mr.Vector3f
Matrix3f = mr.Matrix3f
AffineXf3f = mr.AffineXf3f
makeCube = mr.makeCube
makeCylinder = mr.makeCylinder
makeTorus = mr.makeTorus
makeCone = mr.makeCone
makeSphere = mr.makeSphere
SphereParams = mr.SphereParams

def rotate_transform(axis, angle):
    return mr.AffineXf3f.linear(mr.Matrix3f.rotation(axis, angle))

mr.AffineXf3f.rotation = staticmethod(rotate_transform)
AffineXf3f.rotation = staticmethod(rotate_transform)

if hasattr(mr, 'makeUVSphere'):
    makeUVSphere = mr.makeUVSphere
else:
    def makeUVSphere(radius=1.0, res_u=64, res_v=64):
        return mr.makeUVSphere(radius, res_u, res_v)

def booleanOr(meshA, meshB):
    if meshA is None: return meshB
    if meshB is None: return meshA
    res = mr.boolean(meshA, meshB, mr.BooleanOperation.Union)
    out_mesh = res.mesh if hasattr(res, 'mesh') else res
    return out_mesh if (out_mesh and hasattr(out_mesh, 'topology')) else meshA

def booleanSub(meshA, meshB):
    if meshA is None: return None
    if meshB is None: return meshA
    res = mr.boolean(meshA, meshB, mr.BooleanOperation.DifferenceAB)
    out_mesh = res.mesh if hasattr(res, 'mesh') else res
    return out_mesh if (out_mesh and hasattr(out_mesh, 'topology')) else meshA

def booleanAnd(meshA, meshB):
    if meshA is None or meshB is None: return None
    res = mr.boolean(meshA, meshB, mr.BooleanOperation.Intersection)
    out_mesh = res.mesh if hasattr(res, 'mesh') else res
    return out_mesh if (out_mesh and hasattr(out_mesh, 'topology')) else meshA

{self.raw_code_block}

if 'final_mesh' in locals() and final_mesh is not None:
    if hasattr(final_mesh, 'mesh'):
        final_mesh = final_mesh.mesh
        
    mr.saveMesh(final_mesh, "{output_stl_file}")
    print("SUCCESS")
else:
    print("ERROR: Variable 'final_mesh' was None or not assigned a valid Mesh object.")
"""

        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
                f.write(runner_script)
                temp_script_path = f.name

            result = subprocess.run(
                [sys.executable, temp_script_path],
                capture_output=True,
                text=True,
                timeout=20,
            )

            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)

            if result.returncode == 0 and os.path.exists(output_stl_file):
                self.execution_status = "✅ Success! Starting STL file download..."
                self.is_compiling = False

                with open(output_stl_file, "rb") as f:
                    file_bytes = f.read()

                os.remove(output_stl_file)

                return rx.download(
                    data=file_bytes,
                    filename="generated_model.stl",
                )
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                self.execution_status = f"Execution Error:\n{error_msg}"

        except subprocess.TimeoutExpired:
            self.execution_status = "⏱️ Error: Execution timed out (20s limit)."
        except Exception as e:
            self.execution_status = f"System Error:\n{str(e)}"

        self.is_compiling = False

def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.vstack(
                rx.badge("3D Generator", color_scheme="indigo", variant="soft", radius="full"),
                rx.heading("Assistocrat", size="8", weight="bold"),
                rx.text(
                    "Make very simple shapes with AI even though it's worse than if you do it yourself. Built with love by TheGeekachu",
                    color="gray",
                    size="3",
                    align="center",
                ),
                align_items="center",
                spacing="2",
                width="100%",
                padding_y="4",
            ),
            rx.card(
                rx.vstack(
                    rx.text("Prompt Design", weight="bold", size="3"),
                    rx.input(
                        placeholder="e.g. A 40mm cube",
                        value=CADState.user_prompt,
                        on_change=CADState.set_user_prompt,
                        width="100%",
                        size="3",
                        variant="surface",
                    ),
                    rx.vstack(
                        rx.button(
                            "1. Generate Code",
                            on_click=CADState.generate_design_code,
                            loading=CADState.is_loading,
                            color_scheme="indigo",
                            variant="solid",
                            size="3",
                            width="100%",
                        ),
                        rx.button(
                            "2. Compile & Download STL",
                            on_click=CADState.compile_stl_locally,
                            loading=CADState.is_compiling,
                            color_scheme="green",
                            variant="solid",
                            size="3",
                            width="100%",
                        ),
                        width="100%",
                        spacing="3",
                    ),
                    spacing="4",
                    width="100%",
                ),
                size="4",
                width="100%",
            ),
            rx.callout(
                CADState.execution_status,
                icon="info",
                width="100%",
                size="2",
            ),
            rx.cond(
                CADState.ai_generated_markdown != "",
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.text("Generated Python Payload", weight="bold", size="3"),
                            rx.badge("Python", color_scheme="blue", variant="soft"),
                            justify="between",
                            width="100%",
                        ),
                        rx.markdown(
                            CADState.ai_generated_markdown,
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    size="3",
                    width="100%",
                ),
            ),
            spacing="5",
            padding_y="8",
            width="100%",
        ),
        max_width="720px",
    )

app = rx.App()
app.add_page(index, title="Assistocrat - 3D CAD Generator")