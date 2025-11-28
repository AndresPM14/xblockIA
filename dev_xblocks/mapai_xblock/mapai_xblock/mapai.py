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


# ==============================================================
# Decorador json_handler
# ==============================================================
def json_handler(func):
    func.is_json_handler = True
    func.handler_name = func.__name__

    def wrapper(self, request, suffix=''):
        try:
            # Intentamos obtener un dict desde el request (WebOb Request)
            # Primero, si el objeto ya expone 'json', úsalo (compatibilidad)
            if hasattr(request, "json"):
                data = request.json
            else:
                # Si no, intentamos parsear el body como JSON
                try:
                    body = request.body if hasattr(request, 'body') else None
                    if body:
                        # body viene como bytes
                        data = json.loads(body.decode('utf-8'))
                    else:
                        # Fallback a parámetros (form/query)
                        data = {}
                        if hasattr(request, 'params'):
                            # request.params es un dict-like
                            data.update({k: request.params.get(k) for k in request.params})
                except Exception:
                    # No se pudo parsear: pasamos un dict vacío para evitar fallos
                    data = {}

            result = func(self, data, suffix)
            return Response(
                json.dumps(result),
                content_type="application/json",
                status=200
            )
        except Exception as e:
            # Registrar y devolver error JSON
            print("ERROR en handler:", str(e))
            return Response(
                json.dumps({"error": str(e)}),
                content_type="application/json",
                status=500
            )

    wrapper.is_json_handler = True
    wrapper.handler_name = func.__name__
    return wrapper


# ==============================================================
# XBLOCK PRINCIPAL
# ==============================================================
class MapAiXBlock(XBlock):

    loader = ResourceLoader(__name__)

    display_name = String(
        default="MapAI Evaluador de Mapas",
        scope=Scope.settings,
        help="Nombre visible en Studio"
    )

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
        frag = Fragment()
        frag.add_content(self.loader.load_unicode("static/mapai/public/mapai.html"))
        frag.add_css(self.loader.load_unicode("static/mapai/public/mapai.css"))
        frag.add_javascript(self.loader.load_unicode("static/mapai/public/mapai.js"))
        frag.initialize_js('MapAiXBlock')
        return frag

    def author_view(self, context=None):
        html = "<div><strong>MapAI:</strong> Vista del autor.</div>"
        return Fragment(html)

    # ==============================================================
    # HANDLERS
    # ==============================================================
    @json_handler
    def upload_image(self, data, suffix=''):
        image_b64 = data.get('image_b64')
        if not image_b64:
            return {"error": "No se recibió imagen"}
        self.student_image = image_b64
        self.runtime.save_state(self)
        return {"ok": True}

    @json_handler
    def evaluate(self, data, suffix=''):
        print("=== Handler evaluate() iniciado ===")

        api_key = data.get("api_key")
        if not api_key:
            return {"error": "Falta API key"}

        if not self.student_image:
            return {"error": "No hay imagen cargada"}

        result = self._call_model(self.student_image, api_key)
        self.ai_feedback = result
        self.average_score = result.get("average", 0.0)
        self.runtime.save_state(self)
        print("=== Evaluación completada ===")
        return result

    # ==============================================================
    # LLAMADA A GEMINI (ACTUALIZADO A 2.0 FLASH)
    # ==============================================================
    def _call_model(self, image_b64, api_key):

        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )

        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Evalúa este mapa conceptual según: "
                                "coverage, precision, structure, relations, clarity. "
                                "Devuelve SOLO JSON con {scores:{}, average: , comment:\"\"}"
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_b64
                            }
                        }
                    ]
                }
            ]
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            print("Respuesta cruda GEMINI:", json.dumps(data, indent=2))

            # Nuevo formato
            candidates = data.get("candidates", [])
            if not candidates:
                return {"scores": {}, "comment": "Gemini no devolvió respuesta", "average": 0.0}

            # Gemini 2.x → content es lista
            parts = candidates[0].get("content", [])

            text_output = ""
            for p in parts:
                if isinstance(p, dict) and "text" in p:
                    text_output += p["text"]

            print("Texto extraído:", text_output)

            # Intentar parsear JSON directamente
            try:
                parsed = json.loads(text_output)
                return parsed
            except:
                # Si no es JSON → normalizamos lo que tengamos
                return self._normalize_gemini_response({"comment": text_output})

        except Exception as e:
            print("ERROR en _call_model:", str(e))
            return {"scores": {}, "comment": f"Error al llamar a Gemini: {str(e)}", "average": 0.0}

    # ==============================================================
    # NORMALIZACIÓN
    # ==============================================================
    def _normalize_gemini_response(self, resp):

        text = resp.get("comment", "")

        nums = re.findall(r"\d+(?:\.\d+)?", text)
        nums = [float(n) for n in nums]

        # Si el modelo devolvió 5 valores numéricos
        if len(nums) >= 5:
            vals = nums[:5]
            scores = dict(zip(["coverage", "precision", "structure", "relations", "clarity"], vals))
            avg = sum(vals) / 5.0
            return {"scores": scores, "average": avg, "comment": text}

        return {"scores": {}, "average": 0.0, "comment": text}

    # ==============================================================
    # HELPERS
    # ==============================================================
    def _render_template(self, name):
        data = resource_string(__name__, f"static/mapai/{name}")
        return data.decode("utf-8")

