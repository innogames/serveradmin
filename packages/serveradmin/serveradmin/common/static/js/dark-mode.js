const darkMode = {
    // Only an explicit choice of the user is persisted. Without one we keep
    // following the system preference, including later changes to it.
    current() {
        const stored = localStorage.getItem("darkMode");
        if (stored === "dark" || stored === "light") {
            return stored;
        }

        const prefersDark = window.matchMedia(
            "(prefers-color-scheme: dark)",
        ).matches;

        return prefersDark ? "dark" : "light";
    },

    apply(theme) {
        document.documentElement.setAttribute("data-theme", theme);

        // Runs from the document head as well where the checkbox of the
        // servershell search options does not exist yet.
        const checkbox = document.getElementById("dark_mode");
        if (checkbox) {
            checkbox.checked = theme === "dark";
        }
    },

    init() {
        darkMode.apply(darkMode.current());
    },

    toggle() {
        const checkbox = document.getElementById("dark_mode");
        const theme = checkbox.checked ? "dark" : "light";
        localStorage.setItem("darkMode", theme);
        darkMode.apply(theme);
    },
};

// The theme is applied from the head to avoid a flash of the light theme, this
// repeats it once the checkbox exists.
document.addEventListener("DOMContentLoaded", darkMode.init);

// Follow the system preference as long as the user did not pick a theme
window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
        if (localStorage.getItem("darkMode") === null) {
            darkMode.init();
        }
    });
