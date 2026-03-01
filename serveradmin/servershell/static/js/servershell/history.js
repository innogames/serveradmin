const historyStorageKey = "servershell_history"

servershell.history = {
    /**
     * @returns {[]}
     */
    get: function () {
        const history = localStorage.getItem(historyStorageKey);
        if (!history) {
            return []
        }

        return JSON.parse(history);
    },

    storeEntry: function (entry) {
        const history = servershell.history.get();

        const [matching] = servershell.history.findMatchingEntry(entry.term)
        if (matching !== -1) {
            history.splice(matching, 1);
        }

        const maxSize = parseInt($('#history_size').val())
        while (history.length >= maxSize) {
            history.pop();
        }

        history.unshift(entry);

        localStorage.setItem(historyStorageKey, JSON.stringify(history))
    },

    clear: function () {
        localStorage.setItem(historyStorageKey, "[]");
    },

    findMatchingEntry: function (term) {
        const history = servershell.history.get();
        const index = history.findIndex((i) => term === i.term)
        if (index === -1) {
            return [-1, undefined]
        }

        return [index, history[index]];
    }
}