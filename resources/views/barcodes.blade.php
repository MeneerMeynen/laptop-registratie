<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Barcodes afdrukken – Laptop Registratie</title>
  <script src="https://cdn.jsdelivr.net/npm/bwip-js@3/dist/bwip-js-min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --accent: #3dc6b2;
      --ink:    #14161a;
      --dim:    #767b85;
      --line:   #e3e5e9;
      --paper:  #ffffff;
      --red:    #c0392b;
    }

    body {
      font-family: 'Instrument Sans', system-ui, sans-serif;
      background: #f4f5f7;
      color: var(--ink);
      padding: 32px;
      min-height: 100vh;
    }

    /* ── Screen header ── */
    .screen-header {
      max-width: 960px;
      margin: 0 auto 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .screen-header h1 {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .screen-header p {
      font-size: 13px;
      color: var(--dim);
      margin-top: 2px;
    }
    .btn-print {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--accent);
      color: #fff;
      font-size: 14px;
      font-weight: 600;
      border: none;
      border-radius: 8px;
      padding: 10px 20px;
      cursor: pointer;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .btn-print:hover { opacity: .88; }

    /* ── Section ── */
    .section {
      max-width: 960px;
      margin: 0 auto 28px;
    }
    .section-label {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--dim);
      margin-bottom: 12px;
    }

    /* ── Grid ── */
    .barcode-grid {
      display: grid;
      gap: 20px;
    }
    .barcode-grid.cols-2 { grid-template-columns: repeat(2, 1fr); }
    .barcode-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }

    /* ── Card ── */
    .bc-card {
      background: var(--paper);
      border: 2px solid var(--line);
      border-radius: 14px;
      padding: 32px 20px 24px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 14px;
      page-break-inside: avoid;
    }
    .bc-card.danger { border-color: #f5c6c6; }

    .bc-card canvas {
      display: block;
      /* padding rendered inside bwip-js; extra margin via gap */
      image-rendering: pixelated;
    }

    .bc-label {
      font-size: 17px;
      font-weight: 700;
      letter-spacing: .04em;
      text-transform: uppercase;
      color: var(--ink);
      text-align: center;
    }
    .bc-card.danger .bc-label { color: var(--red); }

    .bc-desc {
      font-size: 12px;
      color: var(--dim);
      text-align: center;
      line-height: 1.5;
    }

    /* ── Print ── */
    @media print {
      @page { size: A4 portrait; margin: 14mm 14mm 14mm 14mm; }

      body { background: white; padding: 0; }
      .screen-header { display: none; }
      .section { margin-bottom: 20px; }
      .section-label { margin-bottom: 8px; }
      .barcode-grid { gap: 14px; }
      .bc-card { padding: 20px 16px 16px; border-radius: 10px; gap: 10px; border-width: 1.5px; }
      .bc-label { font-size: 14px; }
      .bc-desc { font-size: 10px; }
    }
  </style>
</head>
<body>

  <div class="screen-header">
    <div>
      <h1>Barcodes afdrukken</h1>
      <p>Print op A4 en scan met de barcodescanner tijdens de laptop-registratie workflow.</p>
    </div>
    <button class="btn-print" onclick="window.print()">🖨 Afdrukken</button>
  </div>

  <!-- Rij 1: Navigatie -->
  <div class="section">
    <div class="section-label">Navigatie</div>
    <div class="barcode-grid cols-2">
      <div class="bc-card">
        <canvas data-barcode="1UP" data-scale="3"></canvas>
        <div class="bc-label">1UP</div>
        <div class="bc-desc">Selectie één omhoog</div>
      </div>
      <div class="bc-card">
        <canvas data-barcode="1DOWN" data-scale="3"></canvas>
        <div class="bc-label">1DOWN</div>
        <div class="bc-desc">Selectie één omlaag</div>
      </div>
    </div>
  </div>

  <!-- Rij 2: Acties -->
  <div class="section">
    <div class="section-label">Acties</div>
    <div class="barcode-grid cols-2">
      <div class="bc-card">
        <canvas data-barcode="eigen laptop" data-scale="3"></canvas>
        <div class="bc-label">Eigen laptop</div>
        <div class="bc-desc">Leerling heeft eigen toestel</div>
      </div>
      <div class="bc-card danger">
        <canvas data-barcode="INLEVEREN" data-scale="3"></canvas>
        <div class="bc-label">Inleveren</div>
        <div class="bc-desc">Koppel laptop los van leerling</div>
      </div>
    </div>
  </div>

  <!-- Rij 3: Clear (eigen rij) -->
  <div class="section">
    <div class="section-label">Clear</div>
    <div class="barcode-grid cols-3">
      <div class="bc-card" style="grid-column: 1 / -1;">
        <canvas data-barcode="CLEAR" data-scale="3"></canvas>
        <div class="bc-label">Clear</div>
        <div class="bc-desc">Wis het scanveld — scan bij foutieve invoer</div>
      </div>
    </div>
  </div>

  <script>
    document.querySelectorAll('canvas[data-barcode]').forEach(canvas => {
      const scale = parseInt(canvas.dataset.scale || '4', 10);
      bwipjs.toCanvas(canvas, {
        bcid:            'datamatrix',
        text:            canvas.dataset.barcode,
        scale:           scale,
        padding:         8,
        backgroundcolor: 'ffffff',
      });
    });
  </script>
</body>
</html>
