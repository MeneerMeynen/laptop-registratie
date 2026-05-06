function laptopApp() {
  return {
    // ── State ──────────────────────────────────────────────
    theme:              localStorage.getItem('theme') || 'dark',
    activeTab:          'laptops',
    selectedStamnummer: null,
    selectedLaptopId:   null,
    selectedLabel:      'Geen leerling geselecteerd.',
    laptopSearch:       '',
    serialValue:        '',
    linkStatus:         { text: '', type: '' },
    manageSearch:       '',
    showUitgeschreven:  false,
    manageStatus:       { text: '', type: '' },
    _visibleCount:      0,
    // Global scanbar
    globalScanValue:    '',
    // Laptop tracker
    ltSearch:           '',
    ltStatusFilter:     ['aangemeld', 'open'],
    ltSelectedSerial:   null,
    ltStudentInfo:      null,
    ltLaptopType:       null,
    issueStatus:        { text: '', type: '' },
    showNewIssueModal:  false,
    newIssueSerial:     '',
    newIssueDescription:'',
    newIssueDate:       new Date().toISOString().slice(0, 10),
    newIssueCategory:   '',
    newIssueSuggestions:[],
    showEditIssueModal: false,
    editIssueId:        null,
    editIssueSerial:    '',
    editIssueDescription:'',
    editIssueDate:      '',
    editIssueStatus:    'open',
    editIssueSolution:  '',
    editIssueCategory:  '',
    // Reserve laptop (issue modals)
    newIssueReserveLaptopId:  '',
    editIssueReserveLaptopId: '',
    availableReserves:        [],
    // Photo tab
    photoSearch:        '',
    photoSuggestions:   [],
    photoStatus:        { text: '', type: '' },
    // Recent links (session)
    recentLinks:        [],
    // Studenten sidebar
    stuSideFilter:      'all',
    stuCounts:          { all: null, met: null, zonder: null, eigen: null, oud: null },
    // Instellingen
    instellingenSection: 'laptops',
    laptopManageSearch: '',
    laptopManageFilter: 'all',
    laptopManageKind:   'all',
    showNewLaptopForm:  false,
    newLaptopSerial:    '',
    newLaptopStamnummer:'',
    newLaptopType:      'normal', // 'normal' | 'reserve' | 'cabinet'
    newLaptopAlias:     '',
    newLaptopCabinetId: '',
    newLaptopStatus:    { text: '', type: '' },
    // Studenten CRUD
    showNewStudentForm: false,
    newStudent:         { stamnummer: '', voornaam: '', naam: '', klas: '', klasnummer: '', klascode: '', gebruikersnaam: '', instellingsnummer: '' },
    newStudentStatus:   { text: '', type: '' },
    showEditStudentModal: false,
    editStudent:        { stamnummer: '', voornaam: '', naam: '', klas: '', klasnummer: '', klascode: '', gebruikersnaam: '', instellingsnummer: '', pointer: '' },
    editStudentStatus:  { text: '', type: '' },
    // Uitleenkasten CRUD
    cabinetSearch:        '',
    cabinetOptions:       [],
    showNewCabinetForm:   false,
    newCabinet:           { name: '', location: '', description: '', capacity: '' },
    newCabinetStatus:     { text: '', type: '' },
    showEditCabinetModal: false,
    editCabinet:          { id: null, name: '', location: '', description: '', capacity: '' },
    editCabinetStatus:    { text: '', type: '' },

    // ── Lifecycle ──────────────────────────────────────────
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', this.theme);
      document.documentElement.setAttribute('data-theme', this.theme);
    },

    init() {
      document.documentElement.setAttribute('data-theme', this.theme);
      this.activeTab         = sessionStorage.getItem('activeTab') || 'laptops';
      this.manageSearch      = sessionStorage.getItem('manageSearch') || '';
      this.showUitgeschreven = sessionStorage.getItem('showUitgeschreven') === 'true';

      this.$nextTick(() => {
        this._countVisible();
        this.filterManage();
        this._computeStuCounts();
        renderAllBarcodes();
      });

      this.$watch('activeTab', (tab) => {
        if (tab === 'laptops') this.refreshLaptopSidebar();
        if (tab === 'instellingen') this.$nextTick(() => this._computeStuCounts());
        if (tab === 'fotos') {
          if (!this.photoSearch.trim()) this.loadLatestPhotos();
          this.$nextTick(() => this.focusPhotoSearch());
        }
      });
      if (this.activeTab === 'laptops') this.refreshLaptopSidebar();
      if (this.activeTab === 'fotos') {
        if (!this.photoSearch.trim()) this.loadLatestPhotos();
        this.$nextTick(() => this.focusPhotoSearch());
      }

      document.body.addEventListener('htmx:beforeRequest', (e) => {
        const id = e.detail.target?.id;
        if (id === 'lt-sidebar-list' || id === 'lt-detail') {
          e.detail.target.innerHTML = '<div class="lt-loading"><div class="lt-spinner"></div></div>';
        }
      });

      // Global scanbar keyboard shortcut
      const sc = document.getElementById('globalScan');
      const scIn = document.getElementById('globalScanInput');
      if (sc && scIn) {
        scIn.addEventListener('focus', () => sc.classList.add('active'));
        scIn.addEventListener('blur', () => sc.classList.remove('active'));
      }
      document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
          e.preventDefault();
          scIn?.focus();
        }
      });
    },

    // ── Tabs ───────────────────────────────────────────────
    setTab(tab) {
      this.activeTab = tab;
      sessionStorage.setItem('activeTab', tab);
    },

    // ── Global scanbar ─────────────────────────────────────
    handleGlobalScan() {
      const val = this.globalScanValue.trim();
      if (!val) return;
      this.openNewIssueModal(val);
      this.globalScanValue = '';
    },

    // ── Student list filtering ─────────────────────────────
    filterStudents() {
      const q = this.laptopSearch.trim().toLowerCase();
      let count = 0;
      document.querySelectorAll('.student-option').forEach(el => {
        const match = !q || el.dataset.filter.toLowerCase().includes(q);
        el.hidden = !match;
        if (match) count++;
      });
      this._visibleCount = count;
    },

    get filterSummary() { return `${this._visibleCount} leerling(en) zichtbaar`; },

    _countVisible() {
      this._visibleCount = document.querySelectorAll('.student-option:not([hidden])').length;
    },

    // ── Student selection ──────────────────────────────────
    selectStudent(stamnummer, label) {
      document.querySelectorAll('.student-option.active').forEach(el => {
        el.classList.remove('active'); el.setAttribute('aria-selected', 'false');
      });
      const option = document.querySelector(`.student-option[data-stamnummer="${stamnummer}"]`);
      if (option) {
        option.classList.add('active'); option.setAttribute('aria-selected', 'true');
      }
      this.selectedStamnummer = stamnummer;
      this.selectedLaptopId   = option?.dataset.laptopId ? parseInt(option.dataset.laptopId) : null;
      this.selectedLabel      = `Geselecteerd: ${label}`;
      this.$nextTick(() => document.getElementById('serial_number').focus());
    },

    // ── Navigation barcode handling ────────────────────────
    handleScanInput() {
      const val = this.serialValue.trim().replace(/\s+/g, ' ').toUpperCase();
      if (val.endsWith('1UP'))               { this.moveSelection(-1); this.serialValue = ''; }
      else if (val.endsWith('1DOWN'))        { this.moveSelection(1);  this.serialValue = ''; }
      else if (val.endsWith('EIGEN LAPTOP')) { this.serialValue = 'eigen laptop'; }
      else if (val.endsWith('CLEAR'))        { this.serialValue = ''; }
      else if (val.endsWith('INLEVEREN')) {
        this.serialValue = '';
        if (this.selectedLaptopId) this.unlinkLaptop(this.selectedLaptopId);
        else this.linkStatus = { text: 'Geen laptop gekoppeld om in te leveren.', type: 'error' };
      }
    },

    moveSelection(step) {
      const opts = [...document.querySelectorAll('.student-option:not([hidden])')];
      if (!opts.length) return;
      const idx = opts.findIndex(o => o.dataset.stamnummer === this.selectedStamnummer);
      const next = idx === -1
        ? opts[step > 0 ? 0 : opts.length - 1]
        : opts[Math.min(Math.max(idx + step, 0), opts.length - 1)];
      this.selectStudent(next.dataset.stamnummer, next.dataset.label);
      next.scrollIntoView({ block: 'nearest' });
    },

    // ── Laptop linking ─────────────────────────────────────
    async submitLink() {
      if (!this.selectedStamnummer) {
        this.linkStatus = { text: 'Selecteer eerst een leerling.', type: 'error' }; return;
      }
      const serial = this.serialValue.trim();
      if (!serial) {
        this.linkStatus = { text: 'Voer een serienummer in.', type: 'error' }; return;
      }
      const upper = serial.toUpperCase();
      if (['1UP', '1DOWN', 'CLEAR', 'INLEVEREN'].includes(upper)) {
        this.handleScanInput(); return;
      }
      await this._doLink(false);
    },

    async _doLink(overwrite) {
      this.linkStatus = { text: 'Bezig met koppelen…', type: '' };
      const res = await fetch('/api/laptops/link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stamnummer: this.selectedStamnummer,
          serial_number: this.serialValue.trim(),
          overwrite_existing: overwrite,
        }),
      });
      const data = await res.json();

      if (!res.ok) {
        const detail = data.detail;
        if (detail?.requires_confirmation) {
          const serials = (detail.existing_serials || []).join(', ');
          if (confirm(`Leerling heeft al laptop(s): ${serials}.\nOverschrijven met "${this.serialValue.trim()}"?`)) {
            await this._doLink(true); return;
          }
          this.linkStatus = { text: 'Koppeling geannuleerd.', type: '' };
          document.getElementById('serial_number').focus(); return;
        }
        this.linkStatus = { text: detail?.message || detail || 'Koppelen mislukt.', type: 'error' }; return;
      }

      // Update student row
      const option = document.querySelector(`.student-option[data-stamnummer="${data.stamnummer}"]`);
      if (option) {
        const serialEl = option.querySelector('.student-option-serial');
        if (serialEl) {
          const display = data.eigen_laptop ? 'Eigen laptop' : (data.serial_number || 'Niet gekoppeld');
          serialEl.textContent = `Laptop serienummer: ${display}`;
        }
        let ownBadge = option.querySelector('.badge-own');
        if (data.eigen_laptop && !ownBadge) {
          ownBadge = document.createElement('span');
          ownBadge.className = 'badge badge-own'; ownBadge.textContent = 'Eigen laptop';
          option.appendChild(ownBadge);
        } else if (!data.eigen_laptop && ownBadge) { ownBadge.remove(); }
        const baseFilter = option.dataset.baseFilter || '';
        const serialStr = data.eigen_laptop ? 'eigen laptop eigen toestel' : (data.serial_number || '');
        option.dataset.filter = `${baseFilter} ${serialStr}`.trim();
        option.dataset.laptopId = data.id || '';
      }
      this.selectedLaptopId = data.id || null;

      const statusSerial = data.eigen_laptop ? 'eigen laptop' : data.serial_number;
      this.linkStatus = { text: `✓ Laptop "${statusSerial}" gekoppeld.`, type: 'success' };

      // Add to recent links
      this.recentLinks.unshift({
        serial: data.eigen_laptop ? null : data.serial_number,
        label: this.selectedLabel.replace('Geselecteerd: ', ''),
        eigen: !!data.eigen_laptop,
        ts: Date.now(),
      });
      if (this.recentLinks.length > 10) this.recentLinks.length = 10;

      // Auto-advance
      const visible = [...document.querySelectorAll('.student-option:not([hidden])')];
      const currentIdx = visible.findIndex(o => o.dataset.stamnummer === this.selectedStamnummer);
      if (currentIdx !== -1 && currentIdx < visible.length - 1) {
        const next = visible[currentIdx + 1];
        this.selectStudent(next.dataset.stamnummer, next.dataset.label);
        next.scrollIntoView({ block: 'nearest' });
      }

      this.serialValue = '';
      this.$nextTick(() => document.getElementById('serial_number').focus());
    },

    // ── Time helper ────────────────────────────────────────
    timeAgo(ts) {
      const s = Math.floor((Date.now() - ts) / 1000);
      if (s < 60) return `${s}s geleden`;
      if (s < 3600) return `${Math.floor(s/60)}m geleden`;
      return `${Math.floor(s/3600)}u geleden`;
    },

    // ── HTMX import callback ───────────────────────────────
    onImportComplete(event) {
      if (event.detail.successful) {
        htmx.ajax('GET', '/ui/students/list',   { target: '#student-list',        swap: 'innerHTML' });
        htmx.ajax('GET', '/ui/students/manage', { target: '#manage-student-list', swap: 'innerHTML' });
        this.$nextTick(() => { this._countVisible(); this.filterManage(); this._computeStuCounts(); });
      }
    },

    // ── Manage tab filtering ───────────────────────────────
    filterManage() {
      const q = this.manageSearch.trim().toLowerCase();
      sessionStorage.setItem('manageSearch', this.manageSearch);
      sessionStorage.setItem('showUitgeschreven', String(this.showUitgeschreven));

      const specialTokens = ['__met_laptop__', '__zonder_laptop__', '__eigen_laptop__'];
      const isSpecial = specialTokens.includes(q);

      document.querySelectorAll('.manage-row').forEach(row => {
        let matchesQ;
        if (!q) {
          matchesQ = true;
        } else if (q === '__met_laptop__') {
          matchesQ = (row.dataset.laptop || '').includes('met');
        } else if (q === '__zonder_laptop__') {
          matchesQ = (row.dataset.laptop || '') === 'zonder';
        } else if (q === '__eigen_laptop__') {
          matchesQ = (row.dataset.laptop || '').includes('eigen');
        } else {
          matchesQ = row.dataset.manageFilter.toLowerCase().includes(q);
        }
        const matchesOld = !this.showUitgeschreven || row.dataset.oldImport === 'true';
        row.hidden = !(matchesQ && matchesOld);
      });
    },

    toggleUitgeschreven() {
      this.showUitgeschreven = !this.showUitgeschreven;
      this.stuSideFilter = this.showUitgeschreven ? 'oud' : 'all';
      this.filterManage();
    },

    // ── Studenten sidebar filters ──────────────────────────
    setStuFilter(key, specialFilter) {
      this.stuSideFilter = key;
      this.showUitgeschreven = false;
      if (specialFilter === '__met_laptop__') {
        this.manageSearch = '__met_laptop__';
      } else if (specialFilter === '__zonder_laptop__') {
        this.manageSearch = '__zonder_laptop__';
      } else if (specialFilter === '__eigen_laptop__') {
        this.manageSearch = '__eigen_laptop__';
      } else {
        this.manageSearch = '';
      }
      this.filterManage();
    },

    setStuFilterUitgeschreven() {
      this.stuSideFilter = 'oud';
      this.manageSearch = '';
      this.showUitgeschreven = true;
      this.filterManage();
    },

    _computeStuCounts() {
      const rows = [...document.querySelectorAll('.manage-row')];
      this.stuCounts.all    = rows.length;
      this.stuCounts.oud    = rows.filter(r => r.dataset.oldImport === 'true').length;
      this.stuCounts.met    = rows.filter(r => (r.dataset.laptop || '').includes('met')).length;
      this.stuCounts.zonder = rows.filter(r => r.dataset.laptop === 'zonder').length;
      this.stuCounts.eigen  = rows.filter(r => (r.dataset.laptop || '').includes('eigen')).length;
    },

    // ── Manage: select all visible ─────────────────────────
    selectAllVisible() {
      document.querySelectorAll('.manage-row:not([hidden]) .manage-checkbox').forEach(cb => { cb.checked = true; });
    },

    // ── Manage: delete selected ────────────────────────────
    async deleteSelected() {
      const checked = [...document.querySelectorAll('.manage-checkbox:checked')];
      const stamnummers = checked.map(cb => cb.value);
      if (!stamnummers.length) {
        this.manageStatus = { text: 'Selecteer eerst minstens één leerling.', type: 'error' }; return;
      }
      if (!confirm(`Wil je ${stamnummers.length} leerling(en) verwijderen?`)) return;
      this.manageStatus = { text: 'Verwijderen…', type: '' };

      const res = await fetch('/api/students', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stamnummers }),
      });
      const data = await res.json();

      if (!res.ok) {
        this.manageStatus = { text: data.detail || 'Verwijderen mislukt.', type: 'error' }; return;
      }
      this.manageStatus = { text: `✓ ${data.deleted} leerling(en) verwijderd.`, type: 'success' };
      htmx.ajax('GET', '/ui/students/list',   { target: '#student-list',        swap: 'innerHTML' });
      htmx.ajax('GET', '/ui/students/manage', { target: '#manage-student-list', swap: 'innerHTML' });
      this.$nextTick(() => { this._countVisible(); this.filterManage(); });
    },

    // ── Laptop unlink ──────────────────────────────────────
    async unlinkLaptop(laptopId) {
      if (!confirm('Weet je zeker dat je deze laptop wilt inleveren?')) return;
      const res = await fetch(`/api/laptops/${laptopId}/unlink`, { method: 'POST' });
      if (res.ok) {
        this.linkStatus = { text: '✓ Laptop ingeleverd.', type: 'success' };
        this.selectedLaptopId = null;
        // Update student row in-place to preserve filter and selection
        const option = document.querySelector(`.student-option[data-stamnummer="${this.selectedStamnummer}"]`);
        if (option) {
          const serialEl = option.querySelector('.student-option-serial');
          if (serialEl) serialEl.textContent = 'Laptop serienummer: Niet gekoppeld';
          option.querySelector('.badge-own')?.remove();
          option.dataset.laptopId = '';
          const baseFilter = option.dataset.baseFilter || '';
          option.dataset.filter = baseFilter;
        }
        this._countVisible();
        this.filterStudents();
        document.getElementById('serial_number').focus();
      } else {
        const data = await res.json();
        this.linkStatus = { text: data.detail || 'Inleveren mislukt.', type: 'error' };
      }
    },

    // ── Laptop tracker ─────────────────────────────────────
    toggleStatusFilter(status) {
      const idx = this.ltStatusFilter.indexOf(status);
      if (idx === -1) this.ltStatusFilter.push(status);
      else this.ltStatusFilter.splice(idx, 1);
      this.refreshLaptopSidebar();
    },

    refreshLaptopSidebar() {
      const params = new URLSearchParams({ search: this.ltSearch });
      this.ltStatusFilter.forEach(s => params.append('statuses', s));
      htmx.ajax('GET', `/ui/laptop-tracker/sidebar?${params}`, {
        target: '#lt-sidebar-list', swap: 'innerHTML',
      });
    },

    selectLaptop(serial) {
      this.ltSelectedSerial = serial;
      document.querySelectorAll('.lt-item').forEach(el => el.classList.remove('lt-item-active'));
      const item = document.querySelector(`.lt-item[data-serial="${CSS.escape(serial)}"]`);
      if (item) item.classList.add('lt-item-active');
      htmx.ajax('GET', `/ui/laptop-tracker/detail?serial=${encodeURIComponent(serial)}`, {
        target: '#lt-detail', swap: 'innerHTML',
      });
      // Load student info for context pane
      this._loadStudentInfo(serial);
    },

    async _loadStudentInfo(serial) {
      this.ltStudentInfo = null;
      this.ltLaptopType = null;
      try {
        const [searchRes, infoRes] = await Promise.all([
          fetch(`/api/laptops/search?q=${encodeURIComponent(serial)}`),
          fetch(`/api/laptops/info?serial=${encodeURIComponent(serial)}`),
        ]);
        if (searchRes.ok) {
          const list = await searchRes.json();
          const match = list.find(s => s.serial_number === serial);
          if (match) {
            this.ltStudentInfo = {
              naam_volledig: `${match.voornaam || ''} ${match.naam || ''}`.trim(),
              klas: match.klas || '',
            };
          }
        }
        if (infoRes.ok) {
          const info = await infoRes.json();
          this.ltLaptopType = info.laptop_type || null;
        }
      } catch(e) {}
    },

    get ltStudentInitials() {
      if (!this.ltStudentInfo) return '??';
      const parts = (this.ltStudentInfo.naam_volledig || '').split(' ');
      return parts.filter(Boolean).map(p => p[0]).join('').slice(0,2).toUpperCase() || '??';
    },

    refreshLaptopDetail() {
      if (this.ltSelectedSerial) {
        htmx.ajax('GET', `/ui/laptop-tracker/detail?serial=${encodeURIComponent(this.ltSelectedSerial)}`, {
          target: '#lt-detail', swap: 'innerHTML',
        });
      }
    },

    openNewIssueModal(serial = '') {
      this.newIssueSerial            = serial || '';
      this.newIssueDescription       = '';
      this.newIssueDate              = new Date().toISOString().slice(0, 10);
      this.newIssueCategory          = '';
      this.newIssueSuggestions       = [];
      this.newIssueReserveLaptopId   = '';
      this.showNewIssueModal         = true;
      this.loadAvailableReserves();
      this.$nextTick(() => document.getElementById('new-issue-serial').focus());
    },

    async loadAvailableReserves() {
      try {
        const res = await fetch('/api/laptops/reserves/available');
        this.availableReserves = res.ok ? await res.json() : [];
      } catch (e) {
        this.availableReserves = [];
      }
    },

    reserveOptionLabel(r, currentIssueId) {
      const base = r.alias
        ? (r.serial_number ? `${r.alias} (${r.serial_number})` : r.alias)
        : (r.serial_number || `#${r.id}`);
      if (
        r.in_use_by_issue_id !== null &&
        r.in_use_by_issue_id !== undefined &&
        r.in_use_by_issue_id !== currentIssueId
      ) {
        return `${base} · in gebruik bij ${r.in_use_by_student || 'andere leerling'}`;
      }
      return base;
    },

    closeNewIssueModal() { this.showNewIssueModal = false; },

    async fetchLaptopSuggestions() {
      const q = this.newIssueSerial.trim();
      if (q.length < 2) { this.newIssueSuggestions = []; return; }
      const res = await fetch(`/api/laptops/search?q=${encodeURIComponent(q)}`);
      this.newIssueSuggestions = res.ok ? await res.json() : [];
    },

    async submitNewIssue() {
      const serial = this.newIssueSerial.trim();
      const desc   = this.newIssueDescription.trim();
      if (!serial) { this.issueStatus = { text: 'Serienummer is verplicht.', type: 'error' }; return; }
      if (!desc)   { this.issueStatus = { text: 'Beschrijving is verplicht.', type: 'error' }; return; }

      const reserveId = this.newIssueReserveLaptopId
        ? parseInt(this.newIssueReserveLaptopId, 10) : null;
      const res = await fetch('/api/laptop-issues', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          serial_number: serial, description: desc,
          reported_date: this.newIssueDate,
          category: this.newIssueCategory || null,
          reserve_laptop_id: reserveId,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        this.issueStatus = { text: data.detail || 'Opslaan mislukt.', type: 'error' }; return;
      }
      this.issueStatus = { text: '✓ Probleem gemeld.', type: 'success' };
      this.closeNewIssueModal();
      this.refreshLaptopDetail();
      this.refreshLaptopSidebar();
      // Also clear global scan value
      this.globalScanValue = '';
    },

    startEditIssue(dataset) {
      this.editIssueId               = parseInt(dataset.issueId);
      this.editIssueSerial           = dataset.serial;
      this.editIssueDescription      = dataset.description;
      this.editIssueDate             = dataset.date;
      this.editIssueStatus           = dataset.status;
      this.editIssueSolution         = dataset.solution || '';
      this.editIssueCategory         = dataset.category || '';
      this.editIssueReserveLaptopId  = dataset.reserveLaptopId || '';
      this.showEditIssueModal        = true;
      this.loadAvailableReserves();
    },

    closeEditIssueModal() { this.showEditIssueModal = false; },

    async submitEditIssue() {
      const reserveId = this.editIssueReserveLaptopId
        ? parseInt(this.editIssueReserveLaptopId, 10) : null;
      const res = await fetch(`/api/laptop-issues/${this.editIssueId}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description:        this.editIssueDescription.trim(),
          reported_date:      this.editIssueDate,
          status:             this.editIssueStatus,
          category:           this.editIssueCategory || null,
          solution:           this.editIssueStatus === 'gesloten'
                                ? (this.editIssueSolution.trim() || null) : null,
          reserve_laptop_id:  reserveId,
        }),
      });
      if (!res.ok) {
        const data = await res.json();
        this.issueStatus = { text: data.detail || 'Opslaan mislukt.', type: 'error' }; return;
      }
      this.issueStatus = { text: '✓ Probleem opgeslagen.', type: 'success' };
      this.closeEditIssueModal();
      this.refreshLaptopDetail();
      this.refreshLaptopSidebar();
    },

    async deleteIssue(id) {
      if (!confirm('Wil je dit probleem verwijderen?')) return;
      const res = await fetch(`/api/laptop-issues/${id}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) {
        this.issueStatus = { text: 'Verwijderen mislukt.', type: 'error' }; return;
      }
      this.issueStatus = { text: '✓ Probleem verwijderd.', type: 'success' };
      this.refreshLaptopDetail();
      this.refreshLaptopSidebar();
    },

    // ── Photo tab ──────────────────────────────────────────
    async fetchPhotoSuggestions() {
      const q = this.photoSearch.trim();
      if (q.length < 2) { this.photoSuggestions = []; return; }
      const res = await fetch(`/api/laptops/search?q=${encodeURIComponent(q)}`);
      this.photoSuggestions = res.ok ? await res.json() : [];
    },

    loadPhotoGallery() {
      const serial = this.photoSearch.trim();
      if (!serial) { this.photoStatus = { text: 'Voer een serienummer in.', type: 'error' }; return; }
      this.photoStatus = { text: '', type: '' };
      htmx.ajax('GET', `/ui/photos/gallery?serial=${encodeURIComponent(serial)}`, {
        target: '#photo-gallery', swap: 'innerHTML',
      });
    },

    focusPhotoSearch() {
      const el = document.getElementById('photo-search-input');
      if (!el) return;
      el.focus();
      el.select();
    },

    async loadLatestPhotos() {
      try {
        const res = await fetch('/api/photos/latest/serial');
        if (!res.ok) return;
        const data = await res.json();
        if (data.serial_number) {
          this.photoSearch = data.serial_number;
          this.loadPhotoGallery();
          this.$nextTick(() => this.focusPhotoSearch());
        }
      } catch (_) { /* ignore */ }
    },

    // ── Laptop management (Instellingen) ───────────────────
    refreshLaptopManage() {
      const params = new URLSearchParams({
        active: this.laptopManageFilter,
        kind:   this.laptopManageKind || 'all',
      });
      if (this.laptopManageSearch.trim()) params.set('q', this.laptopManageSearch.trim());
      htmx.ajax('GET', `/ui/laptops/manage?${params}`, {
        target: '#manage-laptop-list', swap: 'innerHTML',
      });
    },

    onLaptopImportComplete(event) {
      if (event.detail.successful) this.refreshLaptopManage();
    },

    async createLaptop() {
      const serial = this.newLaptopSerial.trim();
      const type = this.newLaptopType || 'normal';
      const alias = this.newLaptopAlias.trim();
      const stamnummer = this.newLaptopStamnummer.trim();
      const cabinetId = this.newLaptopCabinetId;

      let payload;
      let label;
      if (type === 'reserve') {
        if (!alias) {
          this.newLaptopStatus = { text: 'Alias is verplicht voor een reserve-laptop.', type: 'error' }; return;
        }
        payload = { serial_number: serial || null, is_reserve: true, alias };
        label = alias;
      } else if (type === 'cabinet') {
        if (!serial || !cabinetId) {
          this.newLaptopStatus = { text: 'Serienummer en kast zijn verplicht voor een kast-laptop.', type: 'error' }; return;
        }
        payload = { serial_number: serial, storage_cabinet_id: Number(cabinetId) };
        label = serial;
      } else {
        if (!serial || !stamnummer) {
          this.newLaptopStatus = { text: 'Serienummer en stamnummer zijn verplicht.', type: 'error' }; return;
        }
        payload = { serial_number: serial, stamnummer };
        label = serial;
      }

      this.newLaptopStatus = { text: 'Bezig…', type: '' };
      const res = await fetch('/api/laptops', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        this.newLaptopStatus = { text: data.detail || 'Aanmaken mislukt.', type: 'error' }; return;
      }
      this.newLaptopStatus = { text: `✓ Laptop "${label}" aangemaakt.`, type: 'success' };
      this.newLaptopSerial = '';
      this.newLaptopStamnummer = '';
      this.newLaptopAlias = '';
      this.newLaptopCabinetId = '';
      this.newLaptopType = 'normal';
      this.refreshLaptopManage();
    },

    // ── Uitleenkasten CRUD (Instellingen) ──────────────────
    async ensureCabinetsLoaded() {
      if (this.cabinetOptions.length > 0) return;
      const res = await fetch('/api/storage-cabinets');
      this.cabinetOptions = res.ok ? await res.json() : [];
    },

    refreshCabinetManage() {
      const params = new URLSearchParams();
      const q = (this.cabinetSearch || '').trim();
      if (q) params.set('q', q);
      const url = params.toString()
        ? `/ui/storage-cabinets/manage?${params}`
        : '/ui/storage-cabinets/manage';
      htmx.ajax('GET', url, {
        target: '#manage-cabinet-list', swap: 'innerHTML',
      });
      // Refresh dropdown options too
      fetch('/api/storage-cabinets').then(r => r.ok ? r.json() : []).then(d => { this.cabinetOptions = d; });
    },

    async createCabinet() {
      const name = (this.newCabinet.name || '').trim();
      if (!name) {
        this.newCabinetStatus = { text: 'Naam is verplicht.', type: 'error' }; return;
      }
      this.newCabinetStatus = { text: 'Bezig…', type: '' };
      const payload = {
        name,
        location: (this.newCabinet.location || '').trim() || null,
        description: (this.newCabinet.description || '').trim() || null,
        capacity: this.newCabinet.capacity === '' || this.newCabinet.capacity === null
          ? null : Number(this.newCabinet.capacity),
      };
      const res = await fetch('/api/storage-cabinets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        this.newCabinetStatus = { text: data.detail || 'Aanmaken mislukt.', type: 'error' }; return;
      }
      this.newCabinetStatus = { text: `✓ Kast "${name}" aangemaakt.`, type: 'success' };
      this.newCabinet = { name: '', location: '', description: '', capacity: '' };
      this.refreshCabinetManage();
    },

    openEditCabinetModal(row) {
      const d = row.dataset;
      this.editCabinet = {
        id: Number(d.id),
        name: d.name || '',
        location: d.location || '',
        description: d.description || '',
        capacity: d.capacity === '' ? '' : Number(d.capacity),
      };
      this.editCabinetStatus = { text: '', type: '' };
      this.showEditCabinetModal = true;
    },

    async submitEditCabinet() {
      const id = this.editCabinet.id;
      if (!id) return;
      this.editCabinetStatus = { text: 'Bezig…', type: '' };
      const payload = {
        name: (this.editCabinet.name || '').trim(),
        location: (this.editCabinet.location || '').trim() || null,
        description: (this.editCabinet.description || '').trim() || null,
        capacity: this.editCabinet.capacity === '' || this.editCabinet.capacity === null
          ? null : Number(this.editCabinet.capacity),
      };
      const res = await fetch(`/api/storage-cabinets/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        this.editCabinetStatus = { text: data.detail || 'Opslaan mislukt.', type: 'error' }; return;
      }
      this.editCabinetStatus = { text: '✓ Opgeslagen.', type: 'success' };
      this.showEditCabinetModal = false;
      this.refreshCabinetManage();
    },

    async deleteCabinet(id, label) {
      if (!confirm(`Uitleenkast "${label}" verwijderen?`)) return;
      const res = await fetch('/api/storage-cabinets', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: [id] }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.detail || 'Verwijderen mislukt.');
        return;
      }
      this.refreshCabinetManage();
    },

    // ── Studenten CRUD (Instellingen) ──────────────────────
    refreshManageStudentList() {
      Promise.all([
        htmx.ajax('GET', '/ui/students/manage', {
          target: '#manage-student-list', swap: 'innerHTML',
        }),
        htmx.ajax('GET', '/ui/students/list', {
          target: '#student-list', swap: 'innerHTML',
        }),
      ]).then(() => {
        this.$nextTick(() => {
          this.filterManage();
          this.filterStudents();
          this._countVisible();
          this._computeStuCounts();
        });
      });
    },

    async createStudent() {
      const stam = (this.newStudent.stamnummer || '').trim();
      if (!stam) {
        this.newStudentStatus = { text: 'Stamnummer is verplicht.', type: 'error' };
        return;
      }
      this.newStudentStatus = { text: 'Bezig…', type: '' };
      const res = await fetch('/api/students', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.newStudent),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        this.newStudentStatus = { text: data.detail || 'Aanmaken mislukt.', type: 'error' };
        return;
      }
      this.newStudentStatus = { text: `✓ Leerling ${stam} aangemaakt.`, type: 'success' };
      this.newStudent = { stamnummer: '', voornaam: '', naam: '', klas: '', klasnummer: '', klascode: '', gebruikersnaam: '', instellingsnummer: '' };
      this.refreshManageStudentList();
    },

    openEditStudentModal(row) {
      const d = row.dataset;
      this.editStudent = {
        stamnummer:        d.stamnummer || '',
        voornaam:          d.voornaam || '',
        naam:              d.naam || '',
        klas:              d.klas || '',
        klasnummer:        d.klasnummer || '',
        klascode:          d.klascode || '',
        gebruikersnaam:    d.gebruikersnaam || '',
        instellingsnummer: d.instellingsnummer || '',
        pointer:           d.pointer || '',
      };
      this.editStudentStatus = { text: '', type: '' };
      this.showEditStudentModal = true;
    },

    async submitEditStudent() {
      const stam = this.editStudent.stamnummer;
      if (!stam) return;
      this.editStudentStatus = { text: 'Bezig…', type: '' };
      const { stamnummer, ...payload } = this.editStudent;
      const res = await fetch(`/api/students/${encodeURIComponent(stam)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        this.editStudentStatus = { text: data.detail || 'Opslaan mislukt.', type: 'error' };
        return;
      }
      this.editStudentStatus = { text: '✓ Opgeslagen.', type: 'success' };
      this.showEditStudentModal = false;
      this.refreshManageStudentList();
    },

    async deleteStudentByStamnummer(stamnummer, label) {
      if (!confirm(`Leerling "${label}" definitief verwijderen?`)) return;
      const res = await fetch('/api/students', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stamnummers: [stamnummer] }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.detail || 'Verwijderen mislukt.');
        return;
      }
      this.manageStatus = { text: `✓ ${label} verwijderd.`, type: 'success' };
      this.refreshManageStudentList();
    },
  };
}

// ── Studenten manage row helpers (used via inline onclick) ───
function stuManageEdit(btn) {
  const row = btn.closest('.manage-row');
  const app = window.Alpine && Alpine.$data(document.querySelector('[x-data]'));
  if (app) app.openEditStudentModal(row);
}

function stuManageDelete(stamnummer, label) {
  const app = window.Alpine && Alpine.$data(document.querySelector('[x-data]'));
  if (app) app.deleteStudentByStamnummer(stamnummer, label);
}

// ── Uitleenkast manage row helpers ────────────────────────────
function cabinetManageEdit(btn) {
  const row = btn.closest('.manage-row');
  const app = window.Alpine && Alpine.$data(document.querySelector('[x-data]'));
  if (app) app.openEditCabinetModal(row);
}

function cabinetManageDelete(id, label) {
  const app = window.Alpine && Alpine.$data(document.querySelector('[x-data]'));
  if (app) app.deleteCabinet(id, label);
}

// ── Laptop manage table: inline edit/delete ───────────────────
function ltManageEdit(btn) {
  const row = btn.closest('tr');
  const isReserve = row.dataset.isReserve === '1';
  const inCabinet = row.dataset.inCabinet === '1';
  row.querySelectorAll('.lt-manage-display').forEach(el => el.style.display = 'none');
  row.querySelectorAll('.lt-manage-edit-serial').forEach(el => el.style.display = '');
  if (isReserve) {
    row.querySelectorAll('.lt-manage-edit-alias').forEach(el => el.style.display = '');
  } else if (!inCabinet) {
    row.querySelectorAll('.lt-manage-edit-stamnummer').forEach(el => el.style.display = '');
  }
  row.querySelector('.lt-manage-btn-edit').style.display = 'none';
  row.querySelector('.lt-manage-btn-delete').style.display = 'none';
  row.querySelector('.lt-manage-btn-save').style.display = '';
  row.querySelector('.lt-manage-btn-cancel').style.display = '';
}

function ltManageCancel(btn) {
  const row = btn.closest('tr');
  row.querySelectorAll('.lt-manage-display').forEach(el => el.style.display = '');
  row.querySelectorAll('.lt-manage-edit-serial, .lt-manage-edit-stamnummer, .lt-manage-edit-alias')
     .forEach(el => el.style.display = 'none');
  row.querySelector('.lt-manage-btn-edit').style.display = '';
  row.querySelector('.lt-manage-btn-delete').style.display = '';
  row.querySelector('.lt-manage-btn-save').style.display = 'none';
  row.querySelector('.lt-manage-btn-cancel').style.display = 'none';
}

async function ltManageSave(btn, laptopId) {
  const row = btn.closest('tr');
  const isReserve = row.dataset.isReserve === '1';
  const inCabinet = row.dataset.inCabinet === '1';
  const serial = row.querySelector('.lt-manage-edit-serial').value.trim();
  const aliasEl = row.querySelector('.lt-manage-edit-alias');
  const stamnummerEl = row.querySelector('.lt-manage-edit-stamnummer');
  const alias = aliasEl ? aliasEl.value.trim() : null;
  const stamnummer = stamnummerEl ? stamnummerEl.value.trim() : null;
  btn.textContent = '…';
  btn.disabled = true;
  let payload;
  if (isReserve) {
    payload = { serial_number: serial || null, alias: alias || null };
  } else if (inCabinet) {
    payload = { serial_number: serial || null };
  } else {
    payload = { serial_number: serial || null, stamnummer: stamnummer || null };
  }
  const res = await fetch(`/api/laptops/${laptopId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  btn.textContent = 'Opslaan';
  btn.disabled = false;
  if (!res.ok) {
    const data = await res.json();
    alert(data.detail || 'Opslaan mislukt.');
    return;
  }
  htmx.ajax('GET', '/ui/laptops/manage', { target: '#manage-laptop-list', swap: 'innerHTML' });
}

async function ltManageDelete(btn, laptopId, serial) {
  if (!confirm(`Laptop "${serial}" permanent verwijderen?`)) return;
  btn.disabled = true;
  const res = await fetch(`/api/laptops/${laptopId}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({}));
    alert(data.detail || 'Verwijderen mislukt.');
    btn.disabled = false;
    return;
  }
  htmx.ajax('GET', '/ui/laptops/manage', { target: '#manage-laptop-list', swap: 'innerHTML' });
}

function deleteGalleryPhoto(photoId, serial) {
  if (!confirm('Foto verwijderen?')) return;
  fetch(`/api/photos/${photoId}`, { method: 'DELETE' }).then(res => {
    if (res.ok || res.status === 204) {
      htmx.ajax('GET', `/ui/photos/gallery?serial=${encodeURIComponent(serial)}`, {
        target: '#photo-gallery', swap: 'innerHTML',
      });
    }
  });
}

// ── Lightbox ─────────────────────────────────────────────────
// Listeners are only attached while the lightbox is open, so background
// scrolling/clicking pays no overhead.
var _lb = { scale: 1, panX: 0, panY: 0, dragging: false, didDrag: false, startX: 0, startY: 0, startPanX: 0, startPanY: 0 };

function _lbTransform() {
  document.getElementById('lightbox-img').style.transform =
    'scale(' + _lb.scale + ') translate(' + _lb.panX + 'px, ' + _lb.panY + 'px)';
}

function _lbOnKey(e) {
  if (e.key === 'Escape') closeLightbox(true);
}
function _lbOnWheel(e) {
  e.preventDefault();
  _lb.scale = Math.max(0.5, Math.min(_lb.scale + (e.deltaY < 0 ? 0.2 : -0.2), 8));
  if (_lb.scale <= 1) { _lb.panX = 0; _lb.panY = 0; }
  _lbTransform();
}
function _lbOnMouseDown(e) {
  if (_lb.scale <= 1) return;
  if (!document.querySelector('.lightbox-content').contains(e.target)) return;
  e.preventDefault(); _lb.dragging = true; _lb.didDrag = false;
  _lb.startX = e.clientX; _lb.startY = e.clientY;
  _lb.startPanX = _lb.panX; _lb.startPanY = _lb.panY;
  document.getElementById('lightbox-img').style.cursor = 'grabbing';
}
function _lbOnMouseMove(e) {
  if (!_lb.dragging) return; e.preventDefault(); _lb.didDrag = true;
  _lb.panX = _lb.startPanX + (e.clientX - _lb.startX) / _lb.scale;
  _lb.panY = _lb.startPanY + (e.clientY - _lb.startY) / _lb.scale;
  _lbTransform();
}
function _lbOnMouseUp() {
  if (_lb.dragging) { _lb.dragging = false; document.getElementById('lightbox-img').style.cursor = ''; }
}
function _lbOnTouchStart(e) {
  if (_lb.scale <= 1 || e.touches.length !== 1) return;
  if (!document.querySelector('.lightbox-content').contains(e.target)) return;
  _lb.dragging = true; _lb.startX = e.touches[0].clientX; _lb.startY = e.touches[0].clientY;
  _lb.startPanX = _lb.panX; _lb.startPanY = _lb.panY;
}
function _lbOnTouchMove(e) {
  if (!_lb.dragging || e.touches.length !== 1) return; e.preventDefault();
  _lb.panX = _lb.startPanX + (e.touches[0].clientX - _lb.startX) / _lb.scale;
  _lb.panY = _lb.startPanY + (e.touches[0].clientY - _lb.startY) / _lb.scale;
  _lbTransform();
}
function _lbOnTouchEnd() { _lb.dragging = false; }

function _lbAttachListeners() {
  document.addEventListener('keydown', _lbOnKey);
  document.addEventListener('wheel', _lbOnWheel, { passive: false });
  document.addEventListener('mousedown', _lbOnMouseDown);
  document.addEventListener('mousemove', _lbOnMouseMove);
  document.addEventListener('mouseup', _lbOnMouseUp);
  document.addEventListener('touchstart', _lbOnTouchStart, { passive: true });
  document.addEventListener('touchmove', _lbOnTouchMove, { passive: false });
  document.addEventListener('touchend', _lbOnTouchEnd);
}
function _lbDetachListeners() {
  document.removeEventListener('keydown', _lbOnKey);
  document.removeEventListener('wheel', _lbOnWheel);
  document.removeEventListener('mousedown', _lbOnMouseDown);
  document.removeEventListener('mousemove', _lbOnMouseMove);
  document.removeEventListener('mouseup', _lbOnMouseUp);
  document.removeEventListener('touchstart', _lbOnTouchStart);
  document.removeEventListener('touchmove', _lbOnTouchMove);
  document.removeEventListener('touchend', _lbOnTouchEnd);
}

function openLightbox(url) {
  document.getElementById('lightbox-img').src = url;
  _lb.scale = 1; _lb.panX = 0; _lb.panY = 0; _lb.dragging = false;
  _lbTransform();
  document.getElementById('photo-lightbox').style.display = 'flex';
  document.body.style.overflow = 'hidden';
  _lbAttachListeners();
}
function closeLightbox(force) {
  if (!force && (_lb.dragging || _lb.didDrag)) { _lb.didDrag = false; return; }
  _lb.dragging = false;
  document.getElementById('photo-lightbox').style.display = 'none';
  document.body.style.overflow = '';
  _lbDetachListeners();
}
