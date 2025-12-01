import json
import base64
import requests
import re
from pkg_resources import resource_string
from xblock.core import XBlock
from xblock.fields import Scope, String, Float, Dict
from xblock.fragment import Fragment
from webob import Response
from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable import StudioEditableXBlockMixin


# ==============================================================
# XBLOCK PRINCIPAL
# ==============================================================
class MapAiXBlock(StudioEditableXBlockMixin, XBlock):

    loader = ResourceLoader(__name__)

    display_name = String(
        default="MapAI Evaluador de Mapas",
        scope=Scope.settings,
        help="Nombre visible en Studio"
    )

    # API Key - SOLO configurable desde Studio
    gemini_api_key = String(
        default="",
        scope=Scope.content,
        help="API Key de Google Gemini (configurar desde Studio)",
        display_name="Google Gemini API Key"
    )

    # Campos editables desde Studio
    editable_fields = ['display_name', 'gemini_api_key']

    icon_class = "other"
    has_author_view = True

    # Estado del estudiante
    student_image = String(default="", scope=Scope.user_state)
    ai_feedback = Dict(default={}, scope=Scope.user_state)
    average_score = Float(default=0.0, scope=Scope.user_state)

    # ==============================================================
    # VISTAS
    # ==============================================================
    def student_view(self, context=None):
        """Vista para estudiantes - SIN input de API Key"""
        frag = Fragment()

        # Verificar si hay API Key configurada
        has_api_key = bool(self.gemini_api_key.strip())

        # Cargar HTML y reemplazar placeholder
        html = self.loader.load_unicode("static/mapai/public/mapai.html")
        html = html.replace("{HAS_API_KEY}", "true" if has_api_key else "false")

        frag.add_content(html)
        frag.add_css(self.loader.load_unicode("static/mapai/public/mapai.css"))
        frag.add_javascript(self.loader.load_unicode("static/mapai/public/mapai.js"))
        frag.initialize_js('MapAiXBlock')
        return frag

    def author_view(self, context=None):
        """Vista de autor para mostrar estado"""
        has_key = bool(self.gemini_api_key.strip())
        html = f"""
        <div style="padding: 20px; background: #f0f0f0; border-radius: 8px;">
            <strong>MapAI - Evaluador de Mapas Conceptuales</strong>
            <p style="margin: 10px 0;">
                Estado de la API Key:
                {'<span style="color: green;">✅ Configurada</span>' if has_key else '<span style="color: red;">❌ No configurada</span>'}
            </p>
            <p style="font-size: 12px; color: #666;">
                Haz clic en "Editar" para configurar la API Key de Gemini.
            </p>
        </div>
        """
        return Fragment(html)

    # ==============================================================
    # HANDLERS
    # ==============================================================
    @XBlock.json_handler
    def upload_image(self, data, suffix=''):
        """Sube y guarda la imagen del estudiante"""
        try:
            image_b64 = data.get('image_b64')
            if not image_b64:
                return {"error": "No se recibió imagen"}

            self.student_image = image_b64
            print(f"✅ Imagen guardada ({len(image_b64)} caracteres)")
            return {"ok": True}
        except Exception as e:
            print(f"❌ Error en upload_image: {str(e)}")
            return {"error": str(e)}

    @XBlock.json_handler
    def evaluate(self, data, suffix=''):
        """Evalúa el mapa conceptual usando Gemini"""
        print("=" * 60)
        print("=== Handler evaluate() INICIADO ===")

        # Usar la API Key configurada desde Studio
        api_key = self.gemini_api_key.strip()

        if not api_key:
            return {
                "error": "⚠️ No hay API Key configurada. El profesor debe configurarla desde Studio.",
                "scores": {},
                "average": 0.0
            }

        if not self.student_image:
            return {
                "error": "No hay imagen cargada",
                "scores": {},
                "average": 0.0
            }

        print(f"Usando API Key configurada ({len(api_key)} caracteres)")
        print("Llamando al modelo de IA...")

        result = self._call_model(self.student_image, api_key)

        # Solo guardar si no hay error
        if not result.get("error"):
            self.ai_feedback = result
            self.average_score = result.get("average", 0.0)
            print(f"✅ Evaluación completada. Promedio: {self.average_score}")
        else:
            print(f"⚠️ Evaluación con error: {result.get('error')}")

        print("=" * 60)

        return result

    # ==============================================================
    # LLAMADA A GEMINI
    # ==============================================================
    def _call_model(self, image_b64, api_key):
        """Llama a la API de Gemini con la imagen"""
        
        # ✅ CORRECCIÓN 1: Usar modelo que SÍ existe
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent"  # ← CAMBIADO de gemini-2.5-flash
        )

        headers = {"Content-Type": "application/json"}
        url = f"{endpoint}?key={api_key}"

        # ✅ CORRECCIÓN 2: Prompt más corto y directo
        prompt_text = """Evalúa este mapa conceptual con estas 5 métricas (escala 0-5.0):

1. COVERAGE: ¿Incluye conceptos clave? (5=todos, 0=ninguno)
2. PRECISION: ¿Son correctos? (5=perfectos, 0=incorrectos)
3. STRUCTURE: ¿Jerarquía clara? (5=excelente, 0=sin estructura)
4. RELATIONS: ¿Enlaces bien etiquetados? (5=muy claros, 0=sin enlaces)
5. CLARITY: ¿Es legible? (5=muy claro, 0=ilegible)

Responde SOLO con este JSON (sin texto adicional):
{
  "scores": {
    "coverage": 4.5,
    "precision": 3.5,
    "structure": 4.0,
    "relations": 4.0,
    "clarity": 3.5
  },
  "average": 3.9,
  "comment": "Breve análisis de fortalezas y mejoras"
}"""

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 4096,  # ✅ CORRECCIÓN 3: Aumentado de 2048 a 4096
                "responseMimeType": "application/json"  # ✅ CORRECCIÓN 4: Forzar JSON
            }
        }

        try:
            print(f"Enviando petición a Gemini 1.5 Flash...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            print("=== Respuesta completa de Gemini ===")
            print(json.dumps(data, indent=2))

            candidates = data.get("candidates", [])
            if not candidates:
                print("⚠️ Gemini no devolvió candidatos")
                return {
                    "scores": {}, 
                    "comment": "Gemini no devolvió respuesta válida", 
                    "average": 0.0,
                    "error": "no_candidates"
                }

            # ✅ CORRECCIÓN 5: Verificar finish_reason
            finish_reason = candidates[0].get("finishReason", "")
            if finish_reason == "MAX_TOKENS":
                print("⚠️ Alcanzó el límite de tokens")
                return {
                    "scores": {},
                    "comment": "⚠️ La evaluación se cortó por límite de tokens. Intenta con una imagen más simple.",
                    "average": 0.0,
                    "error": "max_tokens"
                }

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            if not parts:
                print("⚠️ No se encontraron parts en la respuesta")
                return {
                    "scores": {}, 
                    "comment": "No se encontró contenido en la respuesta", 
                    "average": 0.0,
                    "error": "empty_parts"
                }

            text_output = parts[0].get("text", "")

            print("=== Texto extraído ===")
            print(text_output[:500])  # Mostrar primeros 500 chars

            # Limpiar el texto
            text_output = text_output.strip()
            if text_output.startswith("```json"):
                text_output = text_output[7:]
            if text_output.startswith("```"):
                text_output = text_output[3:]
            if text_output.endswith("```"):
                text_output = text_output[:-3]
            text_output = text_output.strip()

            # Parsear JSON
            try:
                parsed = json.loads(text_output)
                print("=== JSON parseado correctamente ===")
                print(json.dumps(parsed, indent=2))

                if "scores" in parsed and "average" in parsed:
                    # ✅ CORRECCIÓN 6: Validar que los scores estén en rango 0-5
                    for key, value in parsed.get("scores", {}).items():
                        if not (0 <= value <= 5.0):
                            print(f"⚠️ Score '{key}' fuera de rango: {value}")
                            parsed["scores"][key] = max(0, min(5.0, value))
                    
                    # Recalcular promedio
                    scores_list = list(parsed["scores"].values())
                    if scores_list:
                        parsed["average"] = round(sum(scores_list) / len(scores_list), 1)
                    
                    print(f"✅ Evaluación exitosa. Promedio: {parsed['average']}")
                    return parsed
                else:
                    print("⚠️ JSON no tiene la estructura esperada")
                    return self._normalize_gemini_response({"comment": text_output})

            except json.JSONDecodeError as je:
                print(f"⚠️ Error al parsear JSON: {je}")
                return self._normalize_gemini_response({"comment": text_output})

        except requests.exceptions.Timeout:
            print("❌ ERROR: Timeout")
            return {
                "scores": {}, 
                "comment": "⏱️ La petición tardó demasiado. Intenta nuevamente.", 
                "average": 0.0,
                "error": "timeout"
            }
        except requests.exceptions.HTTPError as e:
            print(f"❌ ERROR HTTP: {e.response.status_code}")
            error_detail = e.response.text if hasattr(e.response, 'text') else str(e)
            
            if e.response.status_code == 429:
                return {
                    "scores": {},
                    "comment": "⏳ Límite de peticiones alcanzado. Espera 1-2 minutos e intenta nuevamente.",
                    "average": 0.0,
                    "error": "rate_limit"
                }
            elif e.response.status_code == 403:
                return {
                    "scores": {},
                    "comment": "🔑 API Key inválida o sin permisos. Contacta al instructor.",
                    "average": 0.0,
                    "error": "invalid_api_key"
                }
            else:
                return {
                    "scores": {}, 
                    "comment": f"❌ Error HTTP {e.response.status_code}: {error_detail[:100]}", 
                    "average": 0.0,
                    "error": "http_error"
                }
        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR en petición HTTP: {str(e)}")
            return {
                "scores": {}, 
                "comment": f"❌ Error de conexión: {str(e)}", 
                "average": 0.0,
                "error": "connection_error"
            }
        except Exception as e:
            print(f"❌ ERROR inesperado: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "scores": {}, 
                "comment": f"❌ Error inesperado: {str(e)}", 
                "average": 0.0,
                "error": "unexpected_error"
            }

    # ==============================================================
    # NORMALIZACIÓN
    # ==============================================================
    def _normalize_gemini_response(self, resp):
        """Intenta extraer puntuaciones cuando Gemini no devuelve JSON válido"""
        text = resp.get("comment", "")
        nums = re.findall(r"\d+(?:\.\d+)?", text)
        nums = [float(n) for n in nums if float(n) <= 5.0]

        if len(nums) >= 5:
            vals = nums[:5]
            scores = dict(zip(["coverage", "precision", "structure", "relations", "clarity"], vals))
            avg = round(sum(vals) / 5.0, 1)
            print(f"✅ Normalización exitosa. Promedio: {avg}")
            return {"scores": scores, "average": avg, "comment": text}

        print("⚠️ No se pudo normalizar la respuesta")
        return {"scores": {}, "average": 0.0, "comment": text}

    # ==============================================================
    # HELPERS
    # ==============================================================
    def _render_template(self, name):
        data = resource_string(__name__, f"static/mapai/{name}")
        return data.decode("utf-8")

    @staticmethod
    def workbench_scenarios():
        return [("MapAI XBlock", """<mapai/>""")]
