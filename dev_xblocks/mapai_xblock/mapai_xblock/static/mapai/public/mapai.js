function MapAiXBlock(runtime, element) {

    const fileInput   = element.querySelector('#mapai-file');
    const uploadBtn   = element.querySelector('#mapai-upload');
    const preview     = element.querySelector('#preview');
    const img         = element.querySelector('#mapai-preview-img');
    const evalBtn     = element.querySelector('#mapai-eval');

    const result      = element.querySelector('#result');
    const scoresDiv   = element.querySelector('#mapai-scores');
    const gradeDiv    = element.querySelector('#mapai-grade');
    const commentDiv  = element.querySelector('#mapai-comment');
    const loading     = element.querySelector('#loading');

    const apiKeyInput = element.querySelector('#mapai-api-key');

    let imageBase64 = null;

    const uploadHandlerUrl   = runtime.handlerUrl(element, "upload_image");
    const evaluateHandlerUrl = runtime.handlerUrl(element, "evaluate");

    // =====================================================
    // 1. SUBIR IMAGEN
    // =====================================================
    uploadBtn.addEventListener('click', function () {

        const file = fileInput.files[0];

        if (!file) {
            showError("Selecciona una imagen.");
            return;
        }

        if (!file.type.startsWith("image/")) {
            showError("El archivo debe ser una imagen.");
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
                    uploadBtn.innerText = "Subir imagen";

                    if (response.error) {
                        showError("Error al guardar la imagen: " + response.error);
                    }
                },
                error: function () {
                    uploadBtn.disabled = false;
                    uploadBtn.innerText = "Subir imagen";
                    showError("Error de comunicación con el servidor.");
                }
            });
        };

        reader.readAsDataURL(file);
    });


    // =====================================================
    // 2. EVALUAR LA IMAGEN CON GEMINI
    // =====================================================
    evalBtn.addEventListener('click', function () {

        if (!imageBase64) {
            showError("Primero debes subir una imagen.");
            return;
        }

        const api_key = apiKeyInput.value.trim();
        if (!api_key) {
            showError("Debes ingresar la API key.");
            return;
        }

        evalBtn.disabled = true;
        evalBtn.innerText = "Evaluando...";
        loading.style.display = "block";
        result.style.display = "none";

        $.ajax({
            type: "POST",
            url: evaluateHandlerUrl,
            data: JSON.stringify({ image_b64: imageBase64, api_key: api_key }),
            contentType: "application/json",

            success: function (response) {

                evalBtn.disabled = false;
                evalBtn.innerText = "Evaluar con IA";
                loading.style.display = "none";
                result.style.display = "block";

                if (response.error) {
                    showError(response.error);
                    return;
                }

                const feedback = response.feedback || response;  // Compatibilidad
                const scores = feedback.scores || {};
                let html = "<ul>";
                for (const [name, val] of Object.entries(scores)) {
                    html += `<li><strong>${name}:</strong> ${val.toFixed(2)}</li>`;
                }
                html += "</ul>";
                scoresDiv.innerHTML = html;

                gradeDiv.innerHTML = `
                    <p><strong>Promedio:</strong> ${feedback.average.toFixed(2)}</p>
                `;

                commentDiv.innerHTML = `
                    <p><em>Comentario de la IA:</em></p>
                    <div style="white-space:pre-wrap; background:#f7f7f7; padding:8px; border-radius:6px;">
                        ${feedback.comment}
                    </div>
                `;
            },

            error: function (xhr, status, error) {
                evalBtn.disabled = false;
                evalBtn.innerText = "Evaluar con IA";
                loading.style.display = "none";
                result.style.display = "block";
                showError("Error del servidor: " + error);
            }
        });
    });

    function showError(msg) {
        result.style.display = 'block';
        commentDiv.innerHTML = `
            <p style="color:red; text-align:center;">${msg}</p>
        `;
    }
}

