const storageKey = "servershell_history"

servershell.history = {
    /**
     * @returns {[]}
     */
    get: function () {
        const history = localStorage.getItem(storageKey);
        if (!history) {
            return []
        }

        return JSON.parse(history);
    },

    storeEntry: function (entry) {
        const history = servershell.history.get();

        const matching = servershell.history.findMatchingEntry(entry.term)
        if (matching !== -1) {
            history.splice(matching, 1);
        }

        // TODO: Dynamic max length
        while (history.length >= 20) {
            history.pop();
        }

        history.unshift(entry);

        localStorage.setItem(storageKey, JSON.stringify(history))
    },

    clear: function () {
        localStorage.setItem(storageKey, "[]");
    },

    findMatchingEntry: function (term) {
        const history = servershell.history.get();
        return history.findIndex((i) => term === i.term);
    }
}