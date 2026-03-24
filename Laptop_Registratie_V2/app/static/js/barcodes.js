/**
 * Data Matrix barcode renderer using bwip-js.
 * Renders into any <canvas data-barcode="..."> element on the page.
 */

function renderBarcode(canvasEl, value) {
    bwipjs.toCanvas(canvasEl, {
        bcid:    "datamatrix",
        text:    value,
        scale:   3,
        padding: 4,
        backgroundcolor: "ffffff",
    });
}

// Auto-render every <canvas data-barcode="..."> on page load and after HTMX swaps.
function renderAllBarcodes() {
    document.querySelectorAll("canvas[data-barcode]").forEach(canvas => {
        renderBarcode(canvas, canvas.dataset.barcode);
    });
}

document.addEventListener("DOMContentLoaded", renderAllBarcodes);
document.addEventListener("htmx:afterSwap", renderAllBarcodes);
