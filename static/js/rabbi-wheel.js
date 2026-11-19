document.addEventListener("DOMContentLoaded", () => {
    const wheel = document.getElementById("rabbiWheel");
    const buttons = document.querySelectorAll("[data-rabbi-step]");
    const card = document.getElementById("rabbiStepCard");

    if (!wheel || !card || !buttons.length) return;

    const steps = [
        {
            title: "COME — Meet Jesus",
            icon: "🚪",
            color: "#f4c21b",
            message: "Jesus invites you to come to Him. You do not need to be perfect. Begin where you are.",
            verse: "Matthew 11:28",
            scripture: "Jesus invites those who are weary to find rest in Him.",
            reflect: "What would you like to bring to Jesus today?"
        },
        {
            title: "FOLLOW — Walk with Jesus",
            icon: "👣",
            color: "#1976d2",
            message: "Following Jesus means choosing His way each day, even in small things.",
            verse: "John 8:12",
            scripture: "Jesus calls us to follow Him and walk in His light.",
            reflect: "What is one faithful step you can take today?"
        },
        {
            title: "LEARN — Grow in God's Word",
            icon: "📖",
            color: "#8938c8",
            message: "Learn from Jesus through Scripture. Choose a learning path below to explore more.",
            verse: "2 Timothy 3:14",
            scripture: "Continue in what you have learned.",
            reflect: "What would you like to understand better about the Bible?"
        },
        {
            title: "REMAIN — Stay Connected",
            icon: "🌿",
            color: "#188a42",
            message: "Stay close to Jesus through prayer, worship, and a growing relationship with Him.",
            verse: "John 15:4",
            scripture: "Jesus teaches His followers to remain in Him.",
            reflect: "How can you make room for God today?"
        },
        {
            title: "SERVE — Show God's Love",
            icon: "🤝",
            color: "#e87918",
            message: "We can show the love of Jesus through kindness, compassion, and practical help.",
            verse: "Galatians 5:13",
            scripture: "Serve one another humbly in love.",
            reflect: "Who could you help or encourage this week?"
        },
        {
            title: "STAND — Be Strong in Faith",
            icon: "🛡️",
            color: "#c72e2e",
            message: "Stand firm in truth, with courage, patience, and trust in God.",
            verse: "Ephesians 6:13",
            scripture: "God calls us to stand firm.",
            reflect: "Where do you need courage to remain faithful?"
        },
        {
            title: "MULTIPLY — Share with Others",
            icon: "🌱",
            color: "#008f89",
            message: "Share what you are learning and invite others to discover Jesus.",
            verse: "Matthew 28:19",
            scripture: "Jesus sends His followers to make disciples.",
            reflect: "Who might need a word of hope from you?"
        }
    ];

    let currentStep = 0;
    let currentRotation = 0;

    function selectStep(index) {
        const step = steps[index];

        // Rotate using the shortest path.
        const anglePerStep = 360 / steps.length;
        const target = -index * anglePerStep;

        let difference = (target - currentRotation) % 360;

        if (difference > 180) difference -= 360;
        if (difference < -180) difference += 360;

        currentRotation += difference;

        wheel.style.transform = `rotate(${currentRotation}deg)`;

        // Match the information card to the selected step.
        card.style.setProperty("--step-color", step.color);

        card.innerHTML = `
            <p class="rabbi-step-count">STEP ${index + 1} OF 7</p>
            <h2>${step.title}</h2>

            <div class="rabbi-step-icon" aria-hidden="true">
                ${step.icon}
            </div>

            <p>${step.message}</p>

            <div class="rabbi-scripture">
                <strong>${step.verse}</strong>
                <p>${step.scripture}</p>
            </div>

            <p><strong>Reflect:</strong> ${step.reflect}</p>

            ${index === 2 ? `
                <div class="rabbi-learning-links">
                    <a href="/foundation">📖 Faith Foundations</a>
                    <a href="/study">📚 Study Hub</a>
                </div>
            ` : ""}
        `;

        buttons.forEach((button, buttonIndex) => {
            const active = buttonIndex === index;

            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", String(active));
        });

        currentStep = index;
    }

    buttons.forEach((button, index) => {
        button.addEventListener("click", () => selectStep(index));
    });

    document.getElementById("rabbiPrev")?.addEventListener("click", () => {
        selectStep((currentStep + 6) % 7);
    });

    document.getElementById("rabbiNext")?.addEventListener("click", () => {
        selectStep((currentStep + 1) % 7);
    });

    selectStep(0);
});