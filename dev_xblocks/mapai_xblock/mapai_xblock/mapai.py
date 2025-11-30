import json
import requests
from xblock.core import XBlock
from xblock.fields import Scope, String, Float, Dict
from xblock.fragment import Fragment
from webob import Response
from xblockutils.resources import ResourceLoader


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
    @XBlock.json_handler
    def upload_image(self, request):
        """Recibe imagen en base64 y la guarda en el estado"""
        try:
            data = request.json_body if hasattr(request, 'json_body') else {}
            image_b64 = data.get('image_b64', '')
            
            if not image_b64:
                return {'error': 'No image provided'}
            
            self.student_image = image_b64
            return {'success': True, 'message': 'Image uploaded successfully'}
        
        except Exception as e:
            return {'error': str(e)}

    @XBlock.json_handler
    def evaluate(self, request):
        """Evalúa el mapa conceptual usando Gemini"""
        try:
            data = request.json_body if hasattr(request, 'json_body') else {}
            api_key = data.get('api_key', '')
            image_b64 = data.get('image_b64') or self.student_image
            
            if not api_key:
                return {'error': 'API key is required'}
            
            if not image_b64:
                return {'error': 'No image to evaluate'}
            
            # Llamar a Gemini
            response = self._call_model(image_b64, api_key)
            
            # Normalizar respuesta
            normalized = self._normalize_gemini_response(response)
            
            # Guardar resultados
            self.ai_feedback = normalized
            self.average_score = normalized.get('average', 0.0)
            
            # Retornar directamente (sin 'success' ni 'feedback')
            return normalized
        
        except Exception as e:
            return {'error': str(e)}

    # ==============================================================
    # LLAMADA A GEMINI
    # ==============================================================
    def _call_model(self, image_b64, api_key):
        """Llamada HTTP directa a API de Gemini 2.0 Flash"""
        
        if not image_b64 or len(image_b64) < 100:
            raise Exception("Invalid or empty image")
        
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
                                "Evalúa este mapa conceptual según los siguientes criterios: "
                                "1. Coverage (cobertura de conceptos): 0-5 puntos. "
                                "2. Precision (precisión del contenido): 0-5 puntos. "
                                "3. Structure (estructura y organización): 0-5 puntos. "
                                "4. Relations (relaciones entre conceptos): 0-5 puntos. "
                                "5. Clarity (claridad visual): 0-5 puntos. "
                                "Devuelve SOLO JSON válido con esta estructura exacta: "
                                "{\"scores\": {\"coverage\": X, \"precision\": X, \"structure\": X, \"relations\": X, \"clarity\": X}, "
                                "\"average\": X.X, \"comment\": \"texto del comentario\"}"
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
            return response.json()
        
        except requests.exceptions.Timeout:
            raise Exception("API request timeout (60s)")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"API error {response.status_code}: {response.text}")
        except Exception as e:
            raise Exception(f"Failed to call Gemini API: {str(e)}")

    # ==============================================================
    # NORMALIZACIÓN
    # ==============================================================
    def _normalize_gemini_response(self, resp):
        """Extrae y normaliza la respuesta de Gemini"""
        try:
            # Gemini devuelve en candidates[0].content.parts[0].text
            if 'candidates' not in resp or not resp['candidates']:
                raise ValueError("No candidates in response")
            
            candidate = resp['candidates'][0]
            if 'content' not in candidate or 'parts' not in candidate['content']:
                raise ValueError("No content in candidate")
            
            text = candidate['content']['parts'][0].get('text', '')
            
            # Extraer JSON del texto (a veces viene con markdown)
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0]
            elif '```' in text:
                text = text.split('```')[1].split('```')[0]
            
            # Parsear JSON
            data = json.loads(text.strip())
            
            # Validar estructura
            if 'scores' not in data or 'average' not in data:
                raise ValueError("Invalid response structure")
            
            return {
                'scores': data.get('scores', {}),
                'average': float(data.get('average', 0.0)),
                'comment': data.get('comment', '')
            }
        
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Gemini response as JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to normalize response: {str(e)}")

