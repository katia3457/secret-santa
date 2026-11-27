
console.log("SCRIPT ЗАПУСТИЛСЯ!");

const form = document.querySelector(".registration-form");


form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = document.querySelector("#name").value.trim();
    const telegram = document.querySelector("#telegram").value.trim();
    const wishes = document.querySelector("#wishes").value.trim();

    const tg = window.Telegram?.WebApp;
    const initData = tg?.initData || "";

    if (!initData) {
        alert("Открой сайт через Telegram-бота, чтобы зарегистрироваться.");
        return;
    }

    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = "Отправляем...";

    try {
       const response = await fetch("https://secret-santa-backend-6iqc.onrender.com/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name,
                telegram,
                wishes,
                initData
            })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || "Ошибка регистрации");
        }

    document.querySelector(".registration-form").hidden = true;

    document.getElementById("success-card").hidden = false;

    document.getElementById("success-card").scrollIntoView({
        behavior: "smooth"
});
        form.reset();

    } catch (error) {
        alert("Не удалось зарегистрироваться: " + error.message);
    } finally {
        button.disabled = false;
        button.textContent = "Зарегистрироваться";
    }
});


const snowContainer = document.querySelector(".snow-container");

if (snowContainer) {
    for (let i = 0; i < 50; i++) {
        const snowflake = document.createElement("span");

        snowflake.classList.add("snowflake");
        snowflake.textContent = "❄";

        snowflake.style.left = Math.random() * 100 + "%";
        snowflake.style.fontSize = (Math.random() * 10 + 8) + "px";
        snowflake.style.opacity = Math.random() * 0.7 + 0.3;
        snowflake.style.animationDuration = (Math.random() * 8 + 7) + "s";
        snowflake.style.animationDelay = (Math.random() * 10) + "s";

        snowContainer.appendChild(snowflake);
    }
}

// Счётчик посещений сайта
fetch("https://secret-santa-backend-6iqc.onrender.com/visit", {
    method: "POST"
})
.then(response => response.json())
.then(data => {
    console.log("Посещение учтено!");
})
.catch(error => {
    console.log("Счётчик пока недоступен");
});

// Подключение Telegram Mini App
if (window.Telegram && window.Telegram.WebApp) {
    const tg = window.Telegram.WebApp;

    tg.ready();
    tg.expand();

    console.log("Telegram Mini App подключён!");
} else {
    console.log("Сайт открыт вне Telegram");
}

document.getElementById("back-home").addEventListener("click", function () {
    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
});
