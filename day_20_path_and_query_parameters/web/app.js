// File: web/app.js

const API_BASE_URL = "http://localhost:8000";

const form = document.querySelector("#search-form");
const results = document.querySelector("#results");
const errorMessage = document.querySelector("#error-message");
const resetButton = document.querySelector("#reset-button");

function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = false;
}

function clearError() {
    errorMessage.textContent = "";
    errorMessage.hidden = true;
}

function renderProducts(data) {
    results.replaceChildren();

    const heading = document.createElement("h2");
    heading.textContent = `Products (${data.total} matching records)`;
    results.appendChild(heading);

    if (data.items.length === 0) {
        const empty = document.createElement("p");
        empty.textContent = "No products matched the selected parameters.";
        results.appendChild(empty);
        return;
    }

    const list = document.createElement("ul");

    for (const product of data.items) {
        const item = document.createElement("li");
        item.textContent =
            `${product.name} | ${product.category} | ` +
            `$${product.price.toFixed(2)} | stock: ${product.stock}`;
        list.appendChild(item);
    }

    results.appendChild(list);
}

async function searchProducts(event) {
    event.preventDefault();
    clearError();

    const formData = new FormData(form);
    const parameters = new URLSearchParams();

    const category = formData.get("category").trim();
    const search = formData.get("search").trim();
    const minPrice = formData.get("min_price").trim();
    const maxPrice = formData.get("max_price").trim();
    const limit = formData.get("limit").trim();

    if (category) {
        parameters.set("category", category);
    }

    if (search) {
        parameters.set("search", search);
    }

    if (minPrice) {
        parameters.set("min_price", minPrice);
    }

    if (maxPrice) {
        parameters.set("max_price", maxPrice);
    }

    if (formData.get("in_stock") === "on") {
        parameters.set("in_stock", "true");
    }

    if (limit) {
        parameters.set("limit", limit);
    }

    try {
        const query = parameters.toString();
        const response = await fetch(
            `${API_BASE_URL}/products${query ? `?${query}` : ""}`
        );

        const body = await response.json();

        if (!response.ok) {
            const detail = Array.isArray(body.detail)
                ? body.detail.map((item) => item.msg).join("; ")
                : body.detail || "Request failed.";

            throw new Error(detail);
        }

        renderProducts(body);
    } catch (error) {
        showError(
            error instanceof Error
                ? error.message
                : "An unexpected request error occurred."
        );
    }
}

function resetForm() {
    form.reset();
    clearError();
    results.replaceChildren();
}

form.addEventListener("submit", searchProducts);
resetButton.addEventListener("click", resetForm);
