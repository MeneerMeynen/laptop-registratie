function photoApp() {
    return {
        step: 1,
        scanMode: 'manual',  // start with manual, offer camera
        serialInput: '',
        serialNumber: '',
        laptopStudent: '',
        statusMsg: { text: '', type: '' },
        scanningBarcode: false,

        sessionPhotos: [],   // photos taken this session (already uploaded)
        existingPhotos: [],  // photos from before

        cameraMode: 'native',  // 'stream' or 'native' — detected at runtime

        _scannerStream: null,
        _cameraStream: null,
        _codeReader: null,
        _scannerActive: false,
        _hasGetUserMedia: false,

        init() {
            // Detect getUserMedia support (requires HTTPS on iOS)
            this._hasGetUserMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

            // Start with manual input, focus the field
            this.$nextTick(() => {
                const inp = document.getElementById('serial-input');
                if (inp) inp.focus();
            });
        },

        // ── Scanner ──────────────────────────────────────────
        async startScanner() {
            this.scanMode = 'camera';
            this.statusMsg = { text: '', type: '' };

            await this.$nextTick();
            const video = document.getElementById('scanner-video');
            if (!video) return;

            try {
                // Step 1: request a temporary stream to trigger iOS camera permission prompt
                // — iOS won't reveal device labels until permission is granted
                let tempStream = null;
                try {
                    console.log('[camera] requesting temp stream for permission...');
                    tempStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
                    console.log('[camera] permission granted');
                } catch(e) {
                    console.warn('[camera] temp stream failed:', e.message);
                }

                // Step 2: enumerate devices now that labels are available
                let deviceId = null;
                try {
                    const devices = await navigator.mediaDevices.enumerateDevices();
                    const cams = devices.filter(d => d.kind === 'videoinput');
                    console.log('[camera] cameras:', cams.map(c => c.label || '(no label)').join(' | '));
                    // iOS labels vary by language:
                    //   English: 'Back Camera' (1x), 'Back Dual Wide Camera', 'Back Ultra Wide Camera'
                    //   Dutch:   'Camera aan achterzijde', 'Back Dual Wide Camera', 'Ultragroothoekcamera aan achterzijde'
                    // Prefer the main 1x back camera; exclude wide/ultra/tele variants
                    const isWide = c => /wide|ultra|tele|groot|breed/i.test(c.label);
                    const main = cams.find(c => c.label === 'Back Camera')
                               || cams.find(c => c.label === 'Camera aan achterzijde')
                               || cams.find(c => /back camera/i.test(c.label) && !isWide(c))
                               || cams.find(c => /^camera aan achterzijde/i.test(c.label) && !isWide(c))
                               || cams.find(c => /achterzijde/i.test(c.label) && !isWide(c))
                               || cams.find(c => /back/i.test(c.label) && !isWide(c));
                    if (main) {
                        deviceId = main.deviceId;
                        console.log('[camera] selected:', main.label);
                    } else {
                        console.log('[camera] no suitable back camera found, using facingMode');
                    }
                } catch(e) {
                    console.warn('[camera] enumerate failed:', e.message);
                }

                // Step 3: stop temp stream before starting the real one
                if (tempStream) {
                    tempStream.getTracks().forEach(t => t.stop());
                }

                // Step 4: start real stream with the chosen device
                const constraints = deviceId
                    ? { video: { deviceId: { exact: deviceId }, width: { ideal: 1920 }, height: { ideal: 1440 } } }
                    : { video: { facingMode: { exact: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1440 } } };

                console.log('[camera] starting stream:', JSON.stringify(constraints));
                this._scannerStream = await navigator.mediaDevices.getUserMedia(constraints);
                video.srcObject = this._scannerStream;
                video.play().catch(e => console.warn('[camera] play failed:', e.message));

                const track = this._scannerStream.getVideoTracks()[0];
                const settings = track?.getSettings();
                console.log('[camera] active:', track?.label, '| w:', settings?.width, 'h:', settings?.height);

                // Step 5: start decode loop — priority: BarcodeDetector → zxing-wasm → ZXing JS
                this._scannerActive = true;
                let frameCount = 0;

                if ('BarcodeDetector' in window) {
                    // Native browser API (Chrome, Android, desktop)
                    console.log('[scanner] decoder: BarcodeDetector (native)');
                    const supported = await BarcodeDetector.getSupportedFormats().catch(() => []);
                    const formats = supported.length
                        ? supported.filter(f => ['data_matrix','qr_code','code_128','code_39','ean_13'].includes(f))
                        : ['data_matrix', 'qr_code', 'code_128', 'code_39'];
                    console.log('[BarcodeDetector] formats:', formats.join(', '));
                    const detector = new BarcodeDetector({ formats });
                    const scan = async () => {
                        if (!this._scannerActive) return;
                        try {
                            const results = await detector.detect(video);
                            frameCount++;
                            if (frameCount % 30 === 0) console.log(`[BarcodeDetector] frame=${frameCount}`);
                            if (results.length > 0) {
                                this._scannerActive = false;
                                const val = results[0].rawValue;
                                console.log('[BarcodeDetector] ✅', val, '| format:', results[0].format);
                                this.serialInput = val;
                                this.confirmSerial();
                                return;
                            }
                        } catch(e) {
                            if (frameCount % 30 === 0) console.warn('[BarcodeDetector] err:', e.message);
                        }
                        requestAnimationFrame(scan);
                    };
                    requestAnimationFrame(scan);

                } else if (window.__zxingReadBarcodes) {
                    // zxing-wasm: WebAssembly port with proper Data Matrix support (iOS Safari)
                    console.log('[scanner] decoder: zxing-wasm (WebAssembly)');
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d', { willReadFrequently: true });
                    const scan = async () => {
                        if (!this._scannerActive) return;
                        frameCount++;
                        try {
                            if (video.readyState >= video.HAVE_CURRENT_DATA && video.videoWidth > 0) {
                                if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
                                    canvas.width = video.videoWidth;
                                    canvas.height = video.videoHeight;
                                }
                                ctx.drawImage(video, 0, 0);
                                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                                const results = await window.__zxingReadBarcodes(imageData, {
                                    formats: ['DataMatrix', 'QRCode', 'Code128', 'Code39', 'EAN-13'],
                                    tryHarder: true,
                                });
                                if (frameCount % 30 === 0) console.log(`[zxing-wasm] frame=${frameCount}, found=${results.length}`);
                                if (results.length > 0) {
                                    this._scannerActive = false;
                                    const val = results[0].text;
                                    console.log('[zxing-wasm] ✅', val, '| format:', results[0].format);
                                    this.serialInput = val;
                                    this.confirmSerial();
                                    return;
                                }
                            }
                        } catch(e) {
                            if (frameCount % 30 === 0) console.warn('[zxing-wasm] err:', e.message);
                        }
                        requestAnimationFrame(scan);
                    };
                    requestAnimationFrame(scan);

                } else if (typeof ZXing !== 'undefined') {
                    // Last resort: ZXing JS (pure JS, limited Data Matrix support)
                    console.warn('[scanner] decoder: ZXing JS (beperkte Data Matrix ondersteuning)');
                    const hints = new Map();
                    hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [
                        ZXing.BarcodeFormat.DATA_MATRIX,
                        ZXing.BarcodeFormat.QR_CODE,
                        ZXing.BarcodeFormat.CODE_128,
                        ZXing.BarcodeFormat.CODE_39,
                        ZXing.BarcodeFormat.EAN_13,
                    ]);
                    hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
                    this._codeReader = new ZXing.BrowserMultiFormatReader(hints);
                    this._codeReader.decodeFromVideoDevice(null, 'scanner-video', (result, err) => {
                        frameCount++;
                        if (frameCount % 30 === 0) console.log(`[ZXing] frame=${frameCount}, err=${err?.name || 'none'}`);
                        if (result && this._scannerActive) {
                            this._scannerActive = false;
                            console.log('[ZXing] ✅', result.getText(), '| format:', result.getBarcodeFormat());
                            this.serialInput = result.getText();
                            this.confirmSerial();
                        }
                    });

                } else {
                    console.warn('[scanner] geen decoder beschikbaar');
                    this.statusMsg = { text: 'Decoder niet beschikbaar. Voer serienummer handmatig in.', type: 'error' };
                    this.scanMode = 'manual';
                }

            } catch (e) {
                console.error('[camera] fout:', e.name, e.message);
                this.statusMsg = { text: 'Camera niet beschikbaar. Voer serienummer handmatig in.', type: 'error' };
                this.scanMode = 'manual';
            }
        },

        stopScanner() {
            this._scannerActive = false;
            if (this._codeReader) {
                this._codeReader.reset();
                this._codeReader = null;
            }
            if (this._scannerStream) {
                this._scannerStream.getTracks().forEach(t => t.stop());
                this._scannerStream = null;
            }
            const video = document.getElementById('scanner-video');
            if (video) video.srcObject = null;
        },

        switchToManual() {
            this.stopScanner();
            this.scanMode = 'manual';
            this.$nextTick(() => {
                const inp = document.getElementById('serial-input');
                if (inp) inp.focus();
            });
        },

        // ── Native barcode scan (photo → decode) ────────────
        async handleBarcodeScan(event) {
            const file = event.target.files[0];
            if (!file) return;

            this.scanningBarcode = true;
            this.statusMsg = { text: '', type: '' };

            try {
                // Load image into an HTMLImageElement
                const img = new Image();
                const url = URL.createObjectURL(file);
                await new Promise((resolve, reject) => {
                    img.onload = resolve;
                    img.onerror = reject;
                    img.src = url;
                });

                // Draw to canvas for ZXing
                const canvas = document.createElement('canvas');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                URL.revokeObjectURL(url);

                // Decode with ZXing
                const luminance = new ZXing.HTMLCanvasElementLuminanceSource(canvas);
                const binarizer = new ZXing.HybridBinarizer(luminance);
                const bitmap = new ZXing.BinaryBitmap(binarizer);

                // Try multiple barcode formats
                const hints = new Map();
                hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
                const reader = new ZXing.MultiFormatReader();
                reader.setHints(hints);

                const result = reader.decode(bitmap);
                const text = result.getText().trim();

                if (text) {
                    this.serialInput = text;
                    this.statusMsg = { text: `Barcode herkend: ${text}`, type: 'success' };
                    // Auto-confirm after short delay so user sees the result
                    setTimeout(() => this.confirmSerial(), 600);
                } else {
                    this.statusMsg = { text: 'Geen barcode gevonden in de foto.', type: 'error' };
                }
            } catch (e) {
                this.statusMsg = { text: 'Geen barcode gevonden. Probeer opnieuw of voer handmatig in.', type: 'error' };
            }

            this.scanningBarcode = false;
            event.target.value = '';
        },

        // ── Confirm serial ───────────────────────────────────
        async confirmSerial() {
            const serial = this.serialInput.trim();
            if (!serial) {
                this.statusMsg = { text: 'Voer een serienummer in.', type: 'error' };
                return;
            }

            this.stopScanner();
            this.serialNumber = serial;
            this.statusMsg = { text: '', type: '' };

            // Fetch laptop info
            try {
                const res = await fetch(`/api/laptops/search?q=${encodeURIComponent(serial)}`);
                if (res.ok) {
                    const results = await res.json();
                    const match = results.find(r => r.serial_number.toLowerCase() === serial.toLowerCase());
                    if (match) {
                        this.laptopStudent = `${match.voornaam || ''} ${match.naam || ''}`.trim();
                    }
                }
            } catch (e) { /* non-critical */ }

            // Fetch existing photos
            try {
                const res = await fetch(`/api/photos/${encodeURIComponent(serial)}`);
                if (res.ok) {
                    this.existingPhotos = await res.json();
                }
            } catch (e) { /* non-critical */ }

            this.sessionPhotos = [];
            this.step = 2;
            this.startCamera();
        },

        // ── Camera for photo capture ─────────────────────────
        async startCamera() {
            // Try getUserMedia (stream mode) first
            if (this._hasGetUserMedia) {
                try {
                    this.cameraMode = 'stream';
                    await this.$nextTick();
                    const video = document.getElementById('camera-video');
                    if (video) {
                        this._cameraStream = await navigator.mediaDevices.getUserMedia({
                            video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1440 } }
                        });
                        video.srcObject = this._cameraStream;
                        return; // stream mode works
                    }
                } catch (e) {
                    // getUserMedia failed (HTTP on iOS, permission denied, etc.)
                    this.stopCamera();
                }
            }

            // Fallback: native file capture (works on iOS without HTTPS)
            this.cameraMode = 'native';
        },

        stopCamera() {
            if (this._cameraStream) {
                this._cameraStream.getTracks().forEach(t => t.stop());
                this._cameraStream = null;
            }
        },

        // ── Capture photo (stream mode) ─────────────────────
        async capturePhoto() {
            const video = document.getElementById('camera-video');
            if (!video || !video.videoWidth) return;

            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);

            const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
            await this._uploadBase64(dataUrl);
        },

        // ── Capture photo (native file input mode) ──────────
        async handleNativeCapture(event) {
            const file = event.target.files[0];
            if (!file) return;

            this.statusMsg = { text: 'Uploaden...', type: 'info' };

            try {
                const formData = new FormData();
                formData.append('file', file);

                const res = await fetch(`/api/photos?serial_number=${encodeURIComponent(this.serialNumber)}`, {
                    method: 'POST',
                    body: formData,
                });

                if (!res.ok) {
                    const data = await res.json();
                    this.statusMsg = { text: data.detail || 'Upload mislukt.', type: 'error' };
                    return;
                }

                const photo = await res.json();
                this.sessionPhotos.push(photo);
                this.statusMsg = { text: `Foto ${this.sessionPhotos.length} opgeslagen.`, type: 'success' };
            } catch (e) {
                this.statusMsg = { text: 'Upload mislukt. Controleer verbinding.', type: 'error' };
            }

            // Reset input so the same file can be selected again
            event.target.value = '';
        },

        // ── Upload helper (base64, for stream mode) ─────────
        async _uploadBase64(dataUrl) {
            this.statusMsg = { text: 'Uploaden...', type: 'info' };

            try {
                const res = await fetch('/api/photos/base64', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        serial_number: this.serialNumber,
                        image_data: dataUrl,
                    }),
                });

                if (!res.ok) {
                    const data = await res.json();
                    this.statusMsg = { text: data.detail || 'Upload mislukt.', type: 'error' };
                    return;
                }

                const photo = await res.json();
                this.sessionPhotos.push(photo);
                this.statusMsg = { text: `Foto ${this.sessionPhotos.length} opgeslagen.`, type: 'success' };
            } catch (e) {
                this.statusMsg = { text: 'Upload mislukt. Controleer verbinding.', type: 'error' };
            }
        },

        // ── Delete photos ────────────────────────────────────
        async deleteSessionPhoto(photo, idx) {
            try {
                await fetch(`/api/photos/${photo.id}`, { method: 'DELETE' });
            } catch (e) { /* best effort */ }
            this.sessionPhotos.splice(idx, 1);
        },

        async deleteExistingPhoto(photo) {
            if (!confirm('Bestaande foto verwijderen?')) return;
            try {
                await fetch(`/api/photos/${photo.id}`, { method: 'DELETE' });
                this.existingPhotos = this.existingPhotos.filter(p => p.id !== photo.id);
            } catch (e) {
                this.statusMsg = { text: 'Verwijderen mislukt.', type: 'error' };
            }
        },

        // ── Finish ───────────────────────────────────────────
        finish() {
            this.stopCamera();
            this.step = 3;
        },

        goBackToScan() {
            this.stopCamera();
            this.serialInput = '';
            this.serialNumber = '';
            this.laptopStudent = '';
            this.sessionPhotos = [];
            this.existingPhotos = [];
            this.statusMsg = { text: '', type: '' };
            this.step = 1;
            this.$nextTick(() => {
                const inp = document.getElementById('serial-input');
                if (inp) inp.focus();
            });
        },

        reset() {
            this.goBackToScan();
        },
    };
}
