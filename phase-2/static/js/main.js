/* Main Frontend Logic */

const API_BASE = '/api';

// State management
const state = {
    file: null,
    fileMeta: JSON.parse(localStorage.getItem('printFileMeta')) || null,
    options: {
        copies: 1,
        color: 'BW',
        sides: 'SINGLE',
        orientation: 'PORTRAIT'
    }
};

// --- Upload Page Logic ---
async function handleUpload(event) {
    event.preventDefault();
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    if (!file) {
        alert("Please select a file.");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    // Show loading UI
    const btn = event.target.querySelector('button');
    const originalText = btn.innerText;
    btn.innerText = "Uploading...";
    btn.disabled = true;

    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const loadingText = document.getElementById('loadingText');

    progressContainer.style.display = 'block';
    loadingText.style.display = 'block';
    progressBar.style.width = '0%';
    loadingText.innerText = 'Uploading... 0%';

    // Use XHR for progress tracking
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/upload`, true);

    xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
            const percentComplete = Math.round((e.loaded / e.total) * 100);

            // If it's too fast (localhost), giving it a visual "feel" isn't easy with just XHR
            // But we can ensure the text updates clearly.
            progressBar.style.width = percentComplete + '%';

            if (percentComplete < 100) {
                loadingText.innerText = `Uploading... ${percentComplete}%`;
            } else {
                loadingText.innerText = 'Upload complete. Processing file...';
                // Add a "pulse" effect or change color to indicate server-side work
                progressBar.style.backgroundColor = '#10b981'; // Greenish
            }
        }
    };

    xhr.onload = function () {
        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            localStorage.setItem('printFileMeta', JSON.stringify(data));
            loadingText.innerText = 'Success! Redirecting...';
            progressBar.style.width = '100%';
            setTimeout(() => {
                window.location.href = 'options.html';
            }, 500);
        } else {
            let errorMsg = "Upload failed";
            try {
                const errData = JSON.parse(xhr.responseText);
                errorMsg = errData.error || errorMsg;
            } catch (e) { }
            alert(`Error: ${errorMsg}`);
            resetUI();
        }
    };

    xhr.onerror = function () {
        alert("An error occurred during upload.");
        resetUI();
    };

    function resetUI() {
        btn.innerText = originalText;
        btn.disabled = false;
        progressContainer.style.display = 'none';
        loadingText.style.display = 'none';
        progressBar.style.width = '0%';
    }

    xhr.send(formData);
}

// --- Options Page Logic ---
function initOptionsPage() {
    if (!state.fileMeta) {
        alert("No file found. Redirecting to upload.");
        window.location.href = 'index.html';
        return;
    }

    // Display File Info
    document.getElementById('fileName').textContent = state.fileMeta.filename;
    document.getElementById('pageCount').textContent = `${state.fileMeta.pages} Page(s)`;

    // Image Handling Logic
    const sidesSelect = document.getElementById('sides');
    if (state.fileMeta.type === 'IMAGE') {
        state.fileMeta.pages = 1; // Force 1 page for images
        sidesSelect.value = 'SINGLE';
        sidesSelect.disabled = true;
        document.getElementById('imageNote').classList.remove('hidden');
    }

    // Attach Event Listeners
    document.getElementById('copies').addEventListener('input', updatePrice);
    document.getElementById('color').addEventListener('change', updatePrice);
    document.getElementById('sides').addEventListener('change', updatePrice);

    // Initial Calc
    updatePrice();
}

function selectOption(type, value, element) {
    // 1. Update Hidden Input
    const input = document.getElementById(type);
    if (input) {
        input.value = value;
    }

    // 2. Visual Feedback (Radio behavior)
    // Find all siblings in the grid and remove 'active'
    // element.parentNode is .option-grid
    const siblings = element.parentNode.querySelectorAll('.option-card');
    siblings.forEach(el => el.classList.remove('active'));

    // Add active to clicked
    element.classList.add('active');

    // 3. Trigger Price Update
    updatePrice();
}

async function updatePrice() {
    // Gather values
    const copiesEl = document.getElementById('copies');
    const colorEl = document.getElementById('color');
    const sidesEl = document.getElementById('sides');

    // Safety check if elements exist (in case of page structure change)
    if (!copiesEl || !colorEl || !sidesEl) return;

    const copies = parseInt(copiesEl.value) || 1;
    const color = colorEl.value;
    const sides = sidesEl.value;

    // Update local state
    state.options = { ...state.options, copies, color, sides };

    // Calculate (Backend authoritative, but we can do optimistic calc or just call API)
    // Calling API for correctness as per plan
    try {
        const res = await fetch(`${API_BASE}/calculate-price`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pages: state.fileMeta.pages,
                copies: copies,
                color: color,
                sides: sides
            })
        });
        const data = await res.json();

        // Render
        const totalSheetsEl = document.getElementById('totalSheets');
        const totalPriceEl = document.getElementById('totalPrice');

        if (totalSheetsEl) totalSheetsEl.textContent = data.total_sheets;
        if (totalPriceEl) totalPriceEl.textContent = `₹${data.price}`;

        // Save to local storage for checkout
        localStorage.setItem('printOptions', JSON.stringify(state.options));
        localStorage.setItem('printPrice', JSON.stringify(data));
    } catch (e) {
        console.error("Price calc error", e);
    }
}

function goToCheckout() {
    state.options.orientation = document.getElementById('orientation').value;
    localStorage.setItem('printOptions', JSON.stringify(state.options));
    window.location.href = 'checkout.html';
}

// --- Checkout Page Logic ---
function initCheckoutPage() {
    const meta = JSON.parse(localStorage.getItem('printFileMeta'));
    const priceData = JSON.parse(localStorage.getItem('printPrice'));
    const options = JSON.parse(localStorage.getItem('printOptions'));

    if (!meta || !priceData) {
        window.location.href = 'index.html';
        return;
    }

    // Render Summary
    document.getElementById('summaryFile').textContent = meta.filename;
    document.getElementById('summaryDetails').innerHTML = `
        ${meta.pages} Pages x ${options.copies} Copies <br>
        ${options.color} | ${options.sides} | ${options.orientation}
    `;
    document.getElementById('summaryTotal').textContent = `₹${priceData.price}`;
}

async function handleCheckout(event) {
    event.preventDefault();
    const name = document.getElementById('name').value;
    const phone = document.getElementById('phone').value;
    const paymentMethod = document.getElementById('paymentMethod').value;

    const meta = JSON.parse(localStorage.getItem('printFileMeta'));
    const options = JSON.parse(localStorage.getItem('printOptions'));

    const payload = {
        file_url: meta.url,
        file_name: meta.filename,
        file_type: meta.type,
        pages: meta.pages,
        copies: parseInt(options.copies),
        color: options.color,
        sides: options.sides,
        orientation: options.orientation,
        customer_name: name,
        customer_phone: phone,
        payment_method: paymentMethod,
        accepted_terms: document.getElementById('termsConsent').checked
    };

    const btn = event.target.querySelector('button');
    btn.disabled = true;
    btn.innerText = "Processing...";

    try {
        const res = await fetch(`${API_BASE}/create-order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (data.status === 'success') {
            localStorage.setItem('lastOrder', JSON.stringify(data.order));
            window.location.href = 'success.html';
        } else {
            console.error("Order failed!", data.error);
            btn.innerText = "Error: " + (data.error || "Failed");
            // Automatically reset button text after 3 seconds
            setTimeout(() => {
                btn.disabled = false;
                btn.innerText = "Place Order";
            }, 3000);
            return; // Exit early to prevent 'finally' block from resetting it immediately
        }
    } catch (e) {
        console.error("Error creating order.", e);
        btn.innerText = "Error Connecting";
        setTimeout(() => {
            btn.disabled = false;
            btn.innerText = "Place Order";
        }, 3000);
        return;
    } finally {
        // Only hits this if success (due to returns above), but navigation will happen anyway
        // Keeping it strictly for logic flow assurance
    }
}
