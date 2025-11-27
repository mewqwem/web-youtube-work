function updateCount() {
    const text = document.getElementById('story-text').value;
    document.getElementById('char-counter').innerText = text.length;
}

async function generateVideo() {
    const text = document.getElementById('story-text').value;
    const voice = document.getElementById('voice-select').value;
    const model = document.getElementById('model-select').value;
    const promptInstruction = document.getElementById('custom-prompt').value;
    
    const btn = document.getElementById('generate-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('loader');
    const timeDisplay = document.getElementById('execution-time'); // Отримуємо елемент часу

    if (!text) {
        alert("Будь ласка, введіть текст!");
        return;
    }

    // Скидаємо попередній час і блокуємо кнопку
    timeDisplay.innerText = '';
    btn.disabled = true;
    btnText.style.display = 'none';
    loader.style.display = 'block';

    // 1. Засікаємо час початку
    const startTime = Date.now();

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                text: text, 
                voice: voice, 
                model: model,
                instruction: promptInstruction 
            })
        });

        const data = await response.json();

        // 2. Засікаємо час кінця
        const endTime = Date.now();
        // Рахуємо різницю в секундах
        const duration = ((endTime - startTime) / 1000).toFixed(2);

        if (response.ok) {
            loader.style.display = 'none';
            btn.className = 'download-state'; 
            btn.innerHTML = '<i class="fa-solid fa-download"></i> Завантажити MP3';
            btn.disabled = false;
            
            // 3. Показуємо час під кнопкою
            timeDisplay.innerText = `⏱️ Генерація зайняла: ${duration} сек`;
            
            btn.onclick = function() {
                // Запускаємо скачування
                window.location.href = `/download/${data.filename}`;
                
                // Перезавантажуємо сторінку через 1.5 секунди після початку скачування
                // (затримка потрібна, щоб браузер встиг зрозуміти, що це скачування файлу)
                setTimeout(function() {
                    window.location.reload();
                }, 1500); 
            };
        } else {
            alert("Помилка: " + data.error);
            resetButton();
        }

    } catch (error) {
        console.error("Error:", error);
        alert("Помилка з'єднання!");
        resetButton();
    }
}

function resetButton() {
    const btn = document.getElementById('generate-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('loader');
    const timeDisplay = document.getElementById('execution-time');

    btn.className = ''; 
    btn.disabled = false;
    btnText.style.display = 'block';
    loader.style.display = 'none';
    
    // Очищаємо текст про час при скиданні
    timeDisplay.innerText = ''; 
    
    btn.innerHTML = '<span id="btn-text"><i class="fa-solid fa-music"></i> Generate Audio</span><div id="loader" class="loader" style="display: none;"></div>';
    btn.onclick = generateVideo;
}