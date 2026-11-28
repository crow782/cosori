/* Food Diary Aurora — dependency-free Home Assistant custom card. */
class FoodDiaryAuroraCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._period = "day";
    this._anchorDate = null;
    this._data = null;
    this._status = null;
    this._loading = false;
    this._error = null;
    this._notice = null;
    this._offProducts = [];
    this._lastSignature = null;
    this.shadowRoot.addEventListener("click", (event) => this._onClick(event));
    this.shadowRoot.addEventListener("submit", (event) => this._onSubmit(event));
  }

  setConfig(config) {
    this._config = config || {};
    this._anchorDate = this._today();
    this._render();
    this._refresh();
  }

  set hass(hass) {
    this._hass = hass;
    const status = hass.states[this._config?.status_entity || "sensor.food_diary_status"];
    const count = hass.states[this._config?.scan_count_entity || "sensor.food_diary_scan_count"];
    const signature = [
      status?.state || "missing",
      status?.attributes?.last_entry_id || "",
      count?.state || "missing"
    ].join("|");
    if (signature !== this._lastSignature) {
      this._lastSignature = signature;
      this._refresh();
    }
  }

  getCardSize() { return 9; }
  _timezone() { return this._hass?.config?.time_zone || "Europe/Rome"; }

  _today() {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: this._timezone(), year: "numeric", month: "2-digit", day: "2-digit"
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return values.year + "-" + values.month + "-" + values.day;
  }

  async _call(service, data, response = true) {
    if (!this._hass) throw new Error("Home Assistant non è ancora pronto");
    const result = await this._hass.callService(
      "food_diary", service, data || {}, undefined, false, response
    );
    return result?.response ?? result;
  }

  async _refresh() {
    if (!this._hass || !this._config || this._loading) return;
    this._loading = true;
    this._render();
    try {
      const results = await Promise.all([
        this._call("get_dashboard_data", {
          period: this._period,
          anchor_date: this._anchorDate || this._today(),
          timezone: this._timezone()
        }),
        this._call("get_status", {})
      ]);
      this._data = results[0];
      this._status = results[1];
      this._error = null;
    } catch (error) {
      this._error = error?.message || String(error);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  _number(value, digits = 0) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
    return new Intl.NumberFormat(this._hass?.locale?.language || "it-IT", {
      maximumFractionDigits: digits
    }).format(Number(value));
  }

  _dateLabel(value) {
    return new Intl.DateTimeFormat(this._hass?.locale?.language || "it-IT", {
      timeZone: this._timezone(), day: "numeric", month: "short", year: "numeric"
    }).format(new Date(value + "T12:00:00Z"));
  }

  _shiftDate(amount) {
    const [year, month, day] = this._anchorDate.split("-").map(Number);
    const next = this._period === "month"
      ? new Date(Date.UTC(year, month - 1 + amount, 1, 12))
      : new Date(Date.UTC(year, month - 1, day + amount * (this._period === "week" ? 7 : 1), 12));
    this._anchorDate = next.toISOString().slice(0, 10);
    this._refresh();
  }

  _periodTitle(summary) {
    if (!summary) return this._dateLabel(this._anchorDate);
    if (this._period === "day") return this._dateLabel(summary.start_date);
    const last = new Date(summary.end_date_exclusive + "T12:00:00Z");
    last.setUTCDate(last.getUTCDate() - 1);
    return this._dateLabel(summary.start_date) + " – " + this._dateLabel(last.toISOString().slice(0, 10));
  }

  _macro(label, value) {
    return '<div class="macro"><span>' + label + '</span><strong>' + this._number(value, 1) + ' g</strong></div>';
  }

  _entry(entry, showDate) {
    const name = entry.food_name_snapshot || entry.food_name || "Alimento";
    const kcal = entry.energy_kcal == null ? "kcal n/d" : this._number(entry.energy_kcal) + " kcal";
    const date = showDate ? this._dateLabel(String(entry.consumed_at).slice(0, 10)) + " · " : "";
    const meal = ({breakfast:"Colazione",lunch:"Pranzo",dinner:"Cena",snack:"Spuntino"}[entry.meal_type] || entry.meal_type);
    return '<div class="entry"><div><strong>' + this._escape(name) + '</strong><small>' +
      date + this._escape(meal) + ' · ' + this._number(entry.weight_g, 1) + ' g · ' + kcal +
      '</small></div><button class="delete" data-delete="' + this._escape(entry.id) + '" aria-label="Elimina registrazione">×</button></div>';
  }

  _chart(summary) {
    if (!summary) return '<p class="muted">Nessun dato caricato</p>';
    const start = new Date(summary.start_date + "T12:00:00Z");
    const end = new Date(summary.end_date_exclusive + "T12:00:00Z");
    const days = summary.by_day || [];
    const count = Math.round((end - start) / 86400000);
    const max = Math.max(1, ...days.map((day) => Number(day.totals.energy_kcal) || 0));
    let html = '<div class="bars">';
    for (let index = 0; index < count; index++) {
      const date = new Date(start);
      date.setUTCDate(date.getUTCDate() + index);
      const key = date.toISOString().slice(0, 10);
      const day = days.find((item) => item.date === key);
      const kcal = day?.totals?.energy_kcal;
      const height = kcal == null ? 4 : Math.max(5, Number(kcal) / max * 100);
      const label = this._period === "month" ? String(date.getUTCDate()) :
        new Intl.DateTimeFormat("it-IT", { weekday: "short", timeZone: "UTC" }).format(date);
      html += '<div class="bar-wrap"><div class="bar ' + (!day ? "nodata" : kcal == null ? "unknown" : "") +
        '" style="height:' + height + '%" title="' + (day ? this._number(kcal) + " kcal" : "Nessun dato") +
        '"></div><small>' + label + '</small></div>';
    }
    return html + '</div>';
  }

  _foodOptions(foods) {
    return foods.map((food) => '<option value="' + this._escape(food.id) + '">' +
      this._escape(food.name) + (food.brand ? " · " + this._escape(food.brand) : "") + '</option>').join("");
  }

  _nutrientInput(name, label) {
    return '<label>' + label + '<input name="' + name + '" type="number" min="0" step="0.01"></label>';
  }

  _render() {
    const data = this._data;
    const summary = data?.summary;
    const totals = summary?.totals || {};
    const coverage = summary?.nutrient_coverage || {};
    const entries = data?.entries || [];
    const foods = data?.foods || [];
    const meals = [["breakfast","Colazione"],["lunch","Pranzo"],["dinner","Cena"],["snack","Spuntino"]];
    const entryMarkup = this._period === "day"
      ? meals.map(([key,label]) => {
          const rows = entries.filter((entry) => entry.meal_type === key);
          return '<section class="meal"><div class="meal-head"><h3>' + label +
            '</h3><span>' + rows.length + ' registrazioni</span></div>' +
            (rows.length ? rows.map((entry) => this._entry(entry, false)).join("") :
              '<p class="empty">Nessuna registrazione</p>') + '</section>';
        }).join("")
      : entries.slice(0, 40).map((entry) => this._entry(entry, true)).join("");
    const status = this._status || {};
    const pending = status.pending_barcode
      ? '<div class="pending"><strong>Scansione in attesa</strong><span>' +
        this._escape(status.pending_product || status.pending_barcode) + '</span><small>' +
        this._escape(status.state || "") +
        (status.pending_weight_g ? " · " + this._number(status.pending_weight_g, 1) + " g" : "") +
        '</small><div class="actions"><button data-action="save-pending">Registra</button>' +
        '<button class="ghost" data-action="discard-pending">Annulla</button></div></div>'
      : '<p class="muted">Nessuna scansione in attesa</p>';
    this.shadowRoot.innerHTML =
      '<style>' + this._styles() + '</style><div class="card-shell"><div class="shell">' +
      '<header><div><div class="eyebrow">AURORA · FOOD DIARY</div><h1>Diario alimentare</h1>' +
      '<p>Il riepilogo dei tuoi pasti, senza trasformare i dati mancanti in zero.</p></div>' +
      '<div class="status">' + this._escape(status.state || "Connessione…") + '</div></header>' +
      '<nav class="periods">' + ["day","week","month"].map((p) =>
        '<button data-period="' + p + '" class="' + (this._period === p ? "active" : "") + '">' +
        ({day:"Giorno",week:"Settimana",month:"Mese"}[p]) + '</button>').join("") + '</nav>' +
      '<div class="date-nav"><button data-action="prev" aria-label="Periodo precedente">‹</button><strong>' +
      this._periodTitle(summary) + '</strong><button data-action="next" aria-label="Periodo successivo">›</button></div>' +
      (this._error ? '<div class="error">' + this._escape(this._error) + '</div>' : "") +
      (this._notice ? '<div class="notice">' + this._escape(this._notice) + '</div>' : "") +
      '<div class="metrics"><article class="metric hero"><span>Energia registrata</span><strong>' +
      this._number(totals.energy_kcal) + '<small> kcal</small></strong><em>' +
      (totals.energy_kcal == null ? "Dati nutrizionali non disponibili" :
        coverage.energy_kcal?.complete === false ? "Totale parziale · valori mancanti" : "Dati disponibili") +
      '</em></article><article class="metric"><span>Registrazioni</span><strong>' +
      this._number(summary?.entry_count || 0) + '</strong><em>' +
      this._number(summary?.days_with_entries || 0) + ' giorni con dati</em></article>' +
      '<article class="metric"><span>Media giornaliera</span><strong>' +
      this._number(summary?.average_daily_energy_kcal) + '<small> kcal</small></strong>' +
      '<em>Solo giorni con energia disponibile</em></article></div>' +
      '<div class="macros">' + this._macro("Proteine",totals.protein_g) +
      this._macro("Carboidrati",totals.carbohydrates_g) + this._macro("Grassi",totals.fat_g) +
      this._macro("Fibre",totals.fiber_g) + '</div>' +
      '<section class="panel"><div class="section-head"><div><h2>Andamento</h2>' +
      '<p>I giorni senza registrazioni sono indicati come N/D</p></div></div>' + this._chart(summary) + '</section>' +
      '<section class="panel"><div class="section-head"><div><h2>' +
      (this._period === "day" ? "Pasti" : "Registrazioni del periodo") +
      '</h2><p>Valori nutrizionali sconosciuti restano non disponibili</p></div></div>' +
      (entryMarkup || '<p class="empty">Nessuna registrazione in questo periodo</p>') + '</section>' +
      '<section class="panel"><div class="section-head"><div><h2>Acquisizione</h2><p>Scanner e bilancia</p></div></div>' +
      pending + '</section>' +
      '<details class="form-panel"><summary>＋ Aggiungi una porzione</summary><form data-form="portion">' +
      '<label>Alimento<select name="food_id" required><option value="">Seleziona alimento</option>' +
      this._foodOptions(foods) + '</select></label><div class="form-grid">' +
      '<label>Peso (g)<input name="weight_g" type="number" min="0.1" step="0.1" required></label>' +
      '<label>Pasto<select name="meal_type"><option value="breakfast">Colazione</option><option value="lunch">Pranzo</option>' +
      '<option value="dinner">Cena</option><option value="snack" selected>Spuntino</option></select></label></div>' +
      '<button type="submit">Registra porzione</button></form></details>' +
      '<details class="form-panel"><summary>＋ Nuovo alimento manuale</summary><form data-form="food">' +
      '<div class="form-grid"><label>Nome<input name="name" required maxlength="160"></label>' +
      '<label>Marca<input name="brand" maxlength="120"></label></div><label>Barcode<input name="barcode" maxlength="64" value="' + this._escape(status.pending_barcode || "") + '"></label>' +
      '<p class="hint">Valori per 100 g · lascia vuoti quelli sconosciuti</p><div class="form-grid nutrients">' +
      this._nutrientInput("energy_kcal","Energia (kcal)") + this._nutrientInput("protein_g","Proteine (g)") +
      this._nutrientInput("carbohydrates_g","Carboidrati (g)") + this._nutrientInput("sugars_g","Zuccheri (g)") +
      this._nutrientInput("fat_g","Grassi (g)") + this._nutrientInput("saturated_fat_g","Saturi (g)") +
      this._nutrientInput("fiber_g","Fibre (g)") + this._nutrientInput("salt_g","Sale (g)") +
      '</div><button type="submit">Salva alimento</button></form></details>' +
      '<details class="form-panel"><summary>⌕ Cerca alternative Open Food Facts</summary><form data-form="off-search">' +
      '<label>Nome prodotto<input name="query" minlength="2" maxlength="100" required></label>' +
      '<button type="submit">Cerca prodotti</button></form><div id="off-results">' + this._offResultsMarkup() + '</div></details>' +
      '<footer>Food Diary · Aurora interface · Home Assistant</footer>' +
      (this._loading ? '<div class="loading">Aggiornamento…</div>' : '') + '</div></div>';
  }

  _offResultsMarkup() {
    if (!this._offProducts.length) return '<p class="muted">Nessun risultato caricato</p>';
    return this._offProducts.map((product,index) =>
      '<div class="candidate"><div><strong>' + this._escape(product.name) + '</strong><small>' +
      this._escape(product.brand || "Marca non indicata") + ' · ' + this._escape(product.barcode) +
      '</small></div><button data-off-index="' + index + '">Aggiungi</button></div>').join("");
  }

  _styles() {
    return [
      ':host{display:block;color:#f3f1fa;font-family:Arial,sans-serif}',
      '.card-shell{overflow:hidden;border:1px solid rgba(139,120,213,.24);border-radius:22px;background:linear-gradient(145deg,#191a25,#20212d 55%,#191e2a);color:#f3f1fa;box-shadow:0 10px 24px rgba(0,0,0,.16)}',
      '.shell{padding:clamp(13px,3vw,25px);display:grid;gap:16px}',
      'header,.section-head,.date-nav,.meal-head,.entry,.candidate{display:flex;align-items:center;justify-content:space-between;gap:12px}',
      'header{align-items:flex-start}h1{font-size:clamp(23px,4vw,32px);margin:4px 0;font-weight:650}h2{font-size:18px;margin:0}h3{font-size:15px;margin:0}p{margin:5px 0;color:#a8a8b8;font-size:13px}',
      '.eyebrow{font-size:10px;letter-spacing:2px;color:#b5a5ef;font-weight:700}.status{font-size:12px;color:#55aebc}',
      'button{border:0;border-radius:10px;padding:10px 14px;background:#8b78d5;color:white;font-weight:650;cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid #55aebc;outline-offset:2px}',
      'button.ghost,.periods button,.date-nav button{background:#303140;color:#d9d4e8}.periods{display:flex;gap:7px}.periods button{flex:1}.periods button.active{background:#8b78d5;color:white}',
      '.date-nav{justify-content:center}.date-nav button{font-size:22px;line-height:1;padding:5px 13px}.date-nav strong{min-width:180px;text-align:center;font-size:14px}',
      '.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.metric{padding:14px;border:1px solid #383848;background:rgba(255,255,255,.035);border-radius:15px;min-width:0}.metric span,.macro span{display:block;color:#a8a8b8;font-size:12px}.metric strong{display:block;font-size:clamp(20px,3vw,27px);margin:8px 0}.metric small{font-size:12px;color:#b8b2c8}.metric em{font-size:11px;color:#a8a8b8;font-style:normal}.metric.hero{background:linear-gradient(135deg,rgba(139,120,213,.2),rgba(85,174,188,.08));border-color:#5a507f}',
      '.macros{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.macro{padding:11px;border-radius:12px;background:#292a38}.macro strong{display:block;margin-top:5px;font-size:15px}',
      '.panel{padding:15px;border:1px solid #353545;background:rgba(255,255,255,.025);border-radius:16px}.bars{height:110px;display:flex;align-items:flex-end;gap:4px;overflow-x:auto;padding:12px 2px 0}.bar-wrap{height:100%;min-width:18px;flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:5px}.bar{width:min(100%,22px);min-height:3px;border-radius:6px 6px 2px 2px;background:linear-gradient(180deg,#55aebc,#8b78d5)}.bar.nodata{background:#484957;opacity:.5}.bar.unknown{background:#d99a5b}.bar-wrap small{font-size:9px;color:#a8a8b8;white-space:nowrap}',
      '.meal{padding:12px 0;border-bottom:1px solid #353545}.meal:last-child{border-bottom:0}.meal-head span{font-size:11px;color:#9292a2}.entry,.candidate{padding:10px 0;border-bottom:1px solid #343443}.entry:last-child,.candidate:last-child{border-bottom:0}.entry strong,.candidate strong{display:block;font-size:13px}.entry small,.candidate small{display:block;color:#a8a8b8;font-size:11px;margin-top:4px}.delete{background:transparent;color:#aaa;font-size:20px;padding:4px 9px}',
      '.pending{padding:13px;border-radius:14px;background:rgba(217,154,91,.09);border:1px solid rgba(217,154,91,.35);display:grid;gap:5px}.pending small,.muted,.empty,.hint{color:#a8a8b8;font-size:12px}.actions{display:flex;gap:8px;margin-top:7px}',
      '.form-panel{border:1px solid #383848;border-radius:15px;background:#222330;padding:13px}.form-panel summary{cursor:pointer;font-weight:650;color:#d9d1f6;padding:4px}form{display:grid;gap:12px;padding-top:14px}label{display:grid;gap:6px;font-size:12px;color:#bcb9c9}',
      'input,select{width:100%;box-sizing:border-box;border:1px solid #454557;border-radius:10px;background:#171822;color:#f5f2fb;padding:10px;font:inherit;min-width:0}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.nutrients{grid-template-columns:repeat(4,minmax(0,1fr))}',
      '.error{background:#572e37;color:#ffd9df;padding:11px;border-radius:10px;font-size:12px}.notice{background:#24444a;color:#c9f4f4;padding:11px;border-radius:10px;font-size:12px}footer{text-align:center;color:#777889;font-size:10px;padding:8px}.loading{text-align:center;background:#292a38;padding:7px;border-radius:9px;font-size:11px}',
      '@media(max-width:600px){.shell{padding:13px;gap:13px}.metrics{grid-template-columns:1fr 1fr}.metric.hero{grid-column:span 2}.macros{grid-template-columns:repeat(2,minmax(0,1fr))}.nutrients,.form-grid{grid-template-columns:repeat(2,minmax(0,1fr))}header{display:grid}.status{justify-self:start}}',
      '@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}'
    ].join("");
  }

  async _onClick(event) {
    const button = event.target.closest("button");
    if (!button) return;
    try {
      if (button.dataset.period) {
        this._period = button.dataset.period;
        this._refresh();
      } else if (button.dataset.action === "prev") this._shiftDate(-1);
      else if (button.dataset.action === "next") this._shiftDate(1);
      else if (button.dataset.delete) {
        await this._call("delete_entry", { entry_id: button.dataset.delete }, false);
        this._notice = "Registrazione eliminata";
        this._refresh();
      } else if (button.dataset.action === "save-pending") {
        await this._call("save_pending", {});
        this._notice = "Porzione registrata";
        this._refresh();
      } else if (button.dataset.action === "discard-pending") {
        await this._call("discard_pending", {}, false);
        this._notice = "Scansione annullata";
        this._refresh();
      } else if (button.dataset.offIndex !== undefined) {
        const product = this._offProducts[Number(button.dataset.offIndex)];
        if (!product) return;
        await this._call("add_food", {
          name: product.name, brand: product.brand, barcode: product.barcode,
          nutrients_per_100g: product.nutrients_per_100g, source: "openfoodfacts"
        });
        this._offProducts = [];
        this._notice = "Alimento aggiunto al catalogo";
        this._refresh();
      }
    } catch (error) {
      this._error = error?.message || String(error);
      this._render();
    }
  }

  async _onSubmit(event) {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form).entries());
    try {
      if (form.dataset.form === "portion") {
        await this._call("add_entry", {
          food_id: values.food_id, weight_g: Number(values.weight_g),
          meal_type: values.meal_type, source: "manual"
        });
        this._notice = "Porzione registrata";
      } else if (form.dataset.form === "food") {
        const keys = ["energy_kcal","protein_g","carbohydrates_g","sugars_g","fat_g","saturated_fat_g","fiber_g","salt_g"];
        const nutrients = {};
        keys.forEach((key) => { if (values[key] !== "") nutrients[key] = Number(values[key]); });
        await this._call("add_food", {
          name: values.name, brand: values.brand || null, barcode: values.barcode || null,
          nutrients_per_100g: nutrients, source: "manual"
        });
        this._notice = "Alimento salvato";
      } else if (form.dataset.form === "off-search") {
        const result = await this._call("search_openfoodfacts", { query: values.query, limit: 20 });
        this._offProducts = result?.products || [];
        this._notice = this._offProducts.length + " alternative trovate";
      }
      form.reset();
      this._refresh();
    } catch (error) {
      this._error = error?.message || String(error);
      this._render();
    }
  }
}

customElements.define("food-diary-aurora", FoodDiaryAuroraCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "food-diary-aurora",
  name: "Food Diary Aurora",
  description: "Diario alimentare con bilancia, barcode e statistiche",
  preview: false
});
