document.addEventListener("DOMContentLoaded", function () {
    console.log("Lead Management System JavaScript loaded successfully.");
});
function prepareActivity(activityType) {

    const activitySelect = document.querySelector(
        'select[name="activity_type"]'
    );

    const descriptionField = document.querySelector(
        'textarea[name="description"]'
    );

    if (!activitySelect) {
        return;
    }

    activitySelect.value = activityType;

    if (descriptionField) {
        descriptionField.focus();
    }

    const activitySection = document.querySelector(
        '.timeline'
    );

    if (activitySection) {
        activitySection.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }
}
/* =========================================================
   GLOBAL SEARCH
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    const searchInput = document.getElementById("globalSearchInput");
    const searchResults = document.getElementById("globalSearchResults");
    const resultList = document.getElementById("globalSearchResultList");

    if (!searchInput || !searchResults || !resultList) {
        return;
    }

    let searchTimer = null;


    /* OPEN SEARCH WITH CTRL + K */

    document.addEventListener("keydown", function (event) {

        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {

            event.preventDefault();

            searchInput.focus();
            searchInput.select();

            searchResults.classList.add("show");
        }

        if (event.key === "Escape") {

            searchResults.classList.remove("show");

            searchInput.value = "";
        }
    });


    /* SEARCH */

    searchInput.addEventListener("input", function () {

        const query = searchInput.value.trim();

        searchResults.classList.add("show");

        clearTimeout(searchTimer);

        if (!query) {

            resultList.innerHTML = `
                <div class="search-empty">
                    Start typing to search leads...
                </div>
            `;

            return;
        }


        resultList.innerHTML = `
            <div class="search-empty">
                Searching...
            </div>
        `;


        searchTimer = setTimeout(function () {

            fetch(`/leads/global-search/?q=${encodeURIComponent(query)}`)

                .then(response => {

                    if (!response.ok) {
                        throw new Error("Search request failed");
                    }

                    return response.json();
                })

                .then(data => {

                    if (!data.results || data.results.length === 0) {

                        resultList.innerHTML = `
                            <div class="search-empty">
                                No leads found for
                                "<strong>${escapeSearchText(query)}</strong>"
                            </div>
                        `;

                        return;
                    }


                    resultList.innerHTML = data.results.map(function (lead) {

                        const firstLetter =
                            lead.name
                                ? lead.name.charAt(0).toUpperCase()
                                : "L";

                        return `
                            <a
                                href="${lead.url}"
                                class="global-search-result"
                            >

                                <div class="search-result-avatar">
                                    ${escapeSearchText(firstLetter)}
                                </div>

                                <div class="search-result-info">

                                    <span class="search-result-name">
                                        ${escapeSearchText(lead.name)}
                                    </span>

                                    <span class="search-result-company">
                                        ${escapeSearchText(lead.company || "No company")}
                                    </span>

                                </div>

                                <span class="search-result-id">
                                    ${escapeSearchText(lead.lead_id)}
                                </span>

                            </a>
                        `;

                    }).join("");

                })

                .catch(function () {

                    resultList.innerHTML = `
                        <div class="search-empty">
                            Unable to search right now.
                        </div>
                    `;

                });

        }, 250);

    });


    /* CLOSE WHEN CLICKING OUTSIDE */

    document.addEventListener("click", function (event) {

        const searchContainer =
            document.getElementById("globalSearch");

        if (
            searchContainer &&
            !searchContainer.contains(event.target) &&
            !searchResults.contains(event.target)
        ) {
            searchResults.classList.remove("show");
        }

    });


    /* ESCAPE HTML */

    function escapeSearchText(value) {

        const div = document.createElement("div");

        div.textContent = value;

        return div.innerHTML;
    }

});