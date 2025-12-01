function MapAiXBlock(runtime, element) {

    const fileInput      = element.querySelector('#mapai-file');
    const uploadBtn      = element.querySelector('#mapai-upload');
    const preview        = element.querySelector('#preview');
    const img            = element.querySelector('#mapai-preview-img');
    const evalBtn        = element.querySelector('#mapai-eval');

    const result         = element.querySelector('#result');
    const scoresDiv      = element.querySelector('#mapai-scores');
    const gradeDiv       = element.querySelector('#mapai-grade');
    const commentDiv     = element.querySelector('#mapai-comment');
    const loading        = element.querySelector('#loading');

    let imageBase64 = null;

    const uploadHandlerUrl   = runtime.handlerUrl(element, "upload_image");
    const evaluateHandlerUrl = runtime.handlerUrl(element, "evaluate");

    // =====================================================
    // 1. SUBIR IMAGEN
    // =====================================================
    uploadBtn.addEventListener('click', function (e) {
        e.preventDefault();

        const file = fileInput.files[0];

        if (!file) {
            showError("⚠️ Selecciona una imagen primero.");
            return;
        }

        if (!file.type.startsWith("image/")) {
            showError("⚠️ El archivo debe ser una imagen (PNG, JPG, etc.)");
            return;
        }

        uploadBtn.disabled = true;
        uploadBtn.innerText = "Subiendo...";

        const reader = new FileReader();

        reader.onload = function (e) {

            imageBase64 = e.target.result.split(',')[1];

            img.src = e.target.result;
            preview.style.display = 'block';
            result.style.display = 'none';

            $.ajax({
                type: "POST",
                url: uploadHandlerUrl,
                data: JSON.stringify({ image_b64: imageBase64 }),
                contentType: "application/json",

                success: function (response) {
                    uploadBtn.disabled = false;
                    uploadBtn.innerText = "📤 Subir imagen";

                    if (response.error) {
                        showError("❌ Error al guardar la imagen: " + response.error);
                    } else {
                        console.log('✅ Imagen subida correctamente');
                    }
                },
                error: function () {
                    uploadBtn.disabled = false;
                    uploadBtn.innerText = "📤 Subir imagen";
                    showError("❌ Error de comunicación con el servidor.");
                }
            });
        };

        reader.readAsDataURL(file);
    });


    // =====================================================
    // 2. EVALUAR CON IA (usando API Key del servidor)
    // =====================================================
    evalBtn.addEventListener('click', function (e) {
        e.preventDefault();

        if (!imageBase64) {
            showError("⚠️ Primero debes subir una imagen.");
            return;
        }

        evalBtn.disabled = true;
        evalBtn.innerText = "Evaluando...";
        loading.style.display = "block";
        result.style.display = "none";

        console.log('=== Iniciando evaluación ===');

        $.ajax({
            type: "POST",
            url: evaluateHandlerUrl,
            data: JSON.stringify({ 
                image_b64: imageBase64
                // La API Key viene del servidor, configurada por el profesor
            }),
            contentType: "application/json",

            success: function (response) {
                console.log('=== Respuesta de evaluación ===', response);

                evalBtn.disabled = false;
                evalBtn.innerText = "🤖 Evaluar con IA";
                loading.style.display = "none";
                result.style.display = "block";

                if (response.error) {
                    showError(response.error);
                    return;
                }

                // Mostrar scores
                const scores = response.scores || {};
                let html = "<ul style='list-style:none; padding:0;'>";
                for (const [name, val] of Object.entries(scores)) {
                    const displayName = name.charAt(0).toUpperCase() + name.slice(1);
                    const color = val >= 4 ? '#28a745' : val >= 3 ? '#ffc107' : '#dc3545';
                    html += `<li style='padding:5px 0;'>
                        <strong>${displayName}:</strong> 
                        <span style='color:${color}; font-weight:bold;'>${val.toFixed(1)} / 5.0</span>
                    </li>`;
                }
                html += "</ul>";
                scoresDiv.innerHTML = html;

                // Mostrar promedio
                const avgScore = response.average || 0;
                const avgColor = avgScore >= 4 ? '#28a745' : avgScore >= 3 ? '#ffc107' : '#dc3545';
                
                gradeDiv.innerHTML = `
                    <p style="color:${avgColor}; font-weight:bold; font-size:1.4em; margin:0;">
                        ⭐ Promedio Final: ${avgScore.toFixed(2)} / 5.0
                    </p>
                `;

                // Mostrar comentario
                commentDiv.innerHTML = `
                    <p style="margin-bottom:8px;"><strong>💬 Retroalimentación de la IA:</strong></p>
                    <div style="white-space:pre-wrap; background:#ffffff; padding:15px; border-radius:6px; border:1px solid #ddd; line-height:1.6;">
                        ${response.comment || 'Sin comentarios'}
                    </div>
                `;
            },

            error: function (xhr, status, error) {
                console.error('=== Error en evaluación ===');
                console.error('Status:', status);
                console.error('Error:', error);
                
                evalBtn.disabled = false;
                evalBtn.innerText = "🤖 Evaluar con IA";
                loading.style.display = "none";
                result.style.display = "block";
                
                showError("❌ Error del servidor. Por favor, intenta de nuevo.");
            }
        });
    });

    function showError(msg) {
        result.style.display = 'block';
        scoresDiv.innerHTML = '';
        gradeDiv.innerHTML = '';
        commentDiv.innerHTML = `
            <p style="color:red; text-align:center; font-weight:bold; padding:20px; background:#fff; border-radius:6px;">
                ${msg}
            </p>
        `;
    }
}
