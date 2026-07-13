import reflex as rx
from groq import Groq
import meshlib.mrmeshpy as mr

# Initialize Groq (Ensure export GROQ_API_KEY="your_key" is set in terminal)
client = Groq()

class State(rx.State):
    user_prompt: str = ""
    ai_generated_markdown: str = "### Click 'Generate Architecture' to begin..."
    raw_code_block: str = ""  
    execution_status: str = ""
    is_loading: bool = False
    is_compiling: bool = False

    def update_prompt(self, val: str):
        self.user_prompt = val

    def generate_design_code(self):
        self.is_loading = True
        self.execution_status = ""
        yield
        system_instructions = (
            "You are an expert computational geometry engineer writing Python code for MeshLib. "
            "CRITICAL RULES:\n"
            "1. Instantiate vectors using `Vector3f(x, y, z)`.\n"
            "2. To make a box or cube, use makeCube with either a positional or keyword size parameter:\n"
            "   final_mesh = makeCube(Vector3f(30.0, 30.0, 30.0))\n"
            "3. To make a cylinder, use makeCylinder with these parameters: radius (float), length (float), resolution (int):\n"
            "   final_mesh = makeCylinder(10.0, 20.0, 64)\n"
            "4. To make a sphere, use makeSphere with parameters: radius (float), resolution (int):\n"
            "   final_mesh = makeSphere(10.0, 64)\n"
            "5. Always ensure the final output shape object is explicitly assigned to a variable named `final_mesh`.\n"
            "6. Do not include any mesh saving, exporting, or loading commands in your script.\n"
            "7. Output ONLY the raw Python block inside standard ```python blocks."
        )
        try:
            completion = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": f"Write a MeshLib script for: {self.user_prompt}"}
                ]
            )
            response = completion.choices[0].message.content
            self.ai_generated_markdown = response
            
            if "```python" in response:
                clean_block = response.split("```python")[1].split("```")[0]
            elif "```" in response:
                clean_block = response.split("```")[1].split("```")[0]
            else:
                clean_block = response

            cleaned_lines = []
            for line in clean_block.splitlines():
                stripped = line.strip()
                stripped = stripped.replace("`", "")
                if "meshlib" in stripped.lower() or not stripped:
                    continue
                cleaned_lines.append(stripped)
            self.raw_code_block = "\n".join(cleaned_lines).strip()
        
        except Exception as e:
            self.ai_generated_markdown = f"API Connection Error: {str(e)}"
        self.is_loading = False

    def compile_stl_locally(self):
        """Executes the AI-generated code directly in memory on the local server"""
        if not self.raw_code_block:
            self.execution_status = "❌ No code available to compile!"
            return
        self.is_compiling = True
        yield
        try:
            local_vars = {
                'mr': mr,
                'mm': mr,
                'Vector3f': mr.Vector3f,
                'Box3f': mr.Box3f,
                'makeCube': mr.makeCube,
                'makeCylinder': mr.makeCylinder,
                'makeSphere': mr.makeSphere
            }
            exec(self.raw_code_block, globals(), local_vars)
            
            if 'final_mesh' in local_vars:
                final_mesh = local_vars['final_mesh']
                # FIX: Pass the file path string directly to the exporter
                mr.saveMesh(final_mesh, "output_design.stl")
                self.execution_status = "✅ Success! 'output_design.stl' generated in your root folder."
            else:
                self.execution_status = "❌ Error: The AI code failed to define a 'final_mesh' object."
        except Exception as e:
            self.execution_status = f"❌ Runtime Error:\n{str(e)}"
        self.is_compiling = False

def index() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Autonomous Mesh AI Core", size="7", margin_bottom="1em"),
            rx.text_area(
                placeholder="Describe the physical component layout (e.g., A 40mm cube with a 5mm hole)...",
                on_change=State.update_prompt,
                width="100%",
                height="100px",
            ),
            rx.hstack(
                rx.button(
                    "Generate Architecture", 
                    on_click=State.generate_design_code, 
                    loading=State.is_loading,
                ),
                rx.button(
                    "Compile & Generate STL", 
                    on_click=State.compile_stl_locally, 
                    loading=State.is_compiling,
                    color_scheme="green",
                ),
                margin_top="10px",
                spacing="3"
            ),
            rx.cond(
                State.execution_status != "",
                rx.box(
                    rx.text(State.execution_status, font_family="monospace", white_space="pre-wrap"),
                    padding="1em",
                    margin_top="10px",
                    background_color="var(--gray-3)",
                    border_radius="6px",
                    width="100%"
                )
            ),
            rx.divider(margin_y="1.5em"),
            rx.box(
                rx.markdown(State.ai_generated_markdown),
                padding="1.5em",
                border_radius="8px",
                background_color="var(--gray-2)",
                border="1px solid var(--gray-5)",
                width="100%",
                min_height="300px",
                overflow_x="auto"
            ),
            width="600px",
            align_items="stretch"
        ),
        padding_y="4em",
    )

app = rx.App()
app.add_page(index)